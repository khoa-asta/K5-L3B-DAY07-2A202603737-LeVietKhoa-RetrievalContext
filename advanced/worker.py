"""One question, one finite model stage, one process. Default only displays status."""
import argparse
import json
import math
from pathlib import Path
import time

from advanced.safety import (ROOT,apply_limits,atomic_json,claim_model,guard,
                             profile,rest,single_worker,stop_requested)


def finish_action(job,action,usage):
    """Validate a model action against the evidence actually supplied to it."""
    job['events'].append({'event':'model','action':action,'usage':usage})
    if action['action']=='search':
        query=action.get('query','').strip()
        if not query:raise ValueError('Model requested an empty search')
        if job['searches']>=2:
            # Exhaustion is a failure, never count it as a correct abstention.
            raise RuntimeError('Search budget exhausted without a final model answer')
        job.update(query=query,next_stage='retrieve')
        return
    sources=usage['sources_supplied'];valid={s['alias']:s for s in sources}
    answer=action.get('answer','').strip()
    if not answer:raise ValueError('Model returned an empty answer')
    citations=[]
    if action['action']=='answer':
        aliases=action.get('citations',[])
        if not isinstance(aliases,list) or not aliases or any(a not in valid for a in aliases):
            raise ValueError('Model answer has missing/unknown citations')
        for alias in dict.fromkeys(aliases):
            s=valid[alias]
            citations.append({k:s[k] for k in ('alias','id','kind','page','bbox','label','source','source_pages','page_image')})
        status='answered'
    elif action['action']=='abstain':status='abstain'
    else:raise ValueError('Unsupported model action')
    job.update(status=status,next_stage='done',answer=answer,citations=citations,
               answer_sources=sources)


def retrieve(job):
    from advanced.retriever import IPCCRetriever
    retriever=IPCCRetriever()
    sources,trace=retriever.search(job['query'])
    job['sources']=sources;job['trace']=trace;job['searches']+=1
    job['events'].append({'event':'search','query':job['query'],'results':sources,
                          'retrieval_trace':trace,'source':'policy_required' if job['searches']==1 else 'model_requested'})
    job['next_stage']='rerank'


def rerank(job):
    from advanced.index import ART
    from advanced.retriever import pack_sources
    from setup_retrieval import MODEL_PATH
    cfg=profile();guard();claim_model('reranker')
    import torch
    from sentence_transformers import CrossEncoder
    torch.set_num_threads(1)
    model=CrossEncoder(str(MODEL_PATH),device='cpu',local_files_only=True,
                       trust_remote_code=False,max_length=256,activation_fn=torch.nn.Identity())
    guard();started=time.monotonic();rows=[]
    candidates=job['trace']['ranked_candidates'][:cfg['candidate_k']]
    for candidate in candidates:
        if stop_requested():raise InterruptedError('STOP requested during rerank')
        if time.monotonic()-started>=cfg['max_work_seconds']:raise TimeoutError('Reranking work budget reached')
        guard()
        score=float(model.predict([(job['query'],candidate['text'])],batch_size=1,show_progress_bar=False)[0])
        if not math.isfinite(score):raise ValueError('Non-finite reranker score')
        rows.append({**candidate,'retrieval_score':candidate['score'],'score':score})
        rest()
    rows.sort(key=lambda r:(-r['score'],r['id']))
    units={u['id']:u for u in json.loads((ART/'units.json').read_text(encoding='utf-8'))}
    sources,packing=pack_sources(job['query'],rows,units,cfg['top_k'],cfg['context_chars'])
    artifact=json.loads((MODEL_PATH/'artifact.json').read_text(encoding='utf-8'))
    info={'model':artifact['model'],'revision':artifact['revision'],'max_length':256,
          'batch_size':1,'truncation':'longest_first','ranked_candidates':rows,**packing}
    job['events'].append({'event':'rerank','results':sources,'trace':info})
    job.update(sources=sources,next_stage='answer')


def answer(job):
    from advanced.agent import LocalAgent
    model=LocalAgent()
    try:
        action,usage=model.decide(job['question'],job['sources'],[])
    except Exception:
        if hasattr(model,'last_usage'):job['events'].append({'event':'model_error','usage':model.last_usage})
        raise
    finish_action(job,action,usage)


def job_path(name):
    # Names cannot traverse outside this workspace or overwrite arbitrary files.
    import re
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}',name):
        raise ValueError('Job name must use 1..64 ASCII letters, digits, hyphens or underscores')
    return ROOT/'advanced/artifacts/jobs'/f'{name}.json'


def main():
    limits=apply_limits()
    import os
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    os.environ['ANONYMIZED_TELEMETRY']='False'
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job',required=True,help='A new or existing checkpoint name')
    parser.add_argument('--question',help='Only for creating a new job; never pass answer labels')
    parser.add_argument('--stage',choices=['status','next','retrieve','rerank','answer'],default='status')
    args=parser.parse_args();path=job_path(args.job)
    with single_worker():
        if path.exists():
            job=json.loads(path.read_text(encoding='utf-8'))
            if args.question is not None and args.question!=job['question']:
                parser.error('Existing job has a different question; choose a new name')
        else:
            if not args.question or not args.question.strip():parser.error('New job requires --question')
            if len(args.question)>1000:parser.error('Question must be at most 1000 characters')
            job={'question':args.question.strip(),'query':args.question.strip(),'status':'pending',
                 'next_stage':'retrieve','searches':0,'events':[],'resource_profile':profile()}
            atomic_json(path,job)
        if args.stage=='status':
            print(json.dumps({'checkpoint':str(path),'status':job['status'],'next_stage':job['next_stage'],
                              'searches':job['searches'],'model_weights_loaded':False},indent=2));return
        if stop_requested():print('STOP requested; no model loaded.');return
        if job['status']!='pending':
            print(f'Job is {job["status"]}; checkpoint retained. Use a new job name to retry.');return
        stage=job['next_stage'] if args.stage=='next' else args.stage
        if stage!=job['next_stage']:parser.error(f'Next permitted stage is {job["next_stage"]}')
        started=time.monotonic()
        try:
            guard(llm=stage=='answer')
            {'retrieve':retrieve,'rerank':rerank,'answer':answer}[stage](job)
        except Exception as exc:
            # Failure remains in the denominator of any later benchmark evaluation.
            job.update(status='error',failed_stage=stage,error={'type':type(exc).__name__,'message':str(exc)})
        job['events'].append({'event':'stage_finished','stage':stage,'elapsed_seconds':round(time.monotonic()-started,3),
                              'resource_limits':limits})
        atomic_json(path,job)
        print(json.dumps({'checkpoint':str(path),'status':job['status'],'next_stage':job['next_stage'],
                          'error':job.get('error')},indent=2))
        if job['status']=='error':raise SystemExit(1)


if __name__=='__main__':main()

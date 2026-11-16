"""One bounded demo stage. Model weights never live in the HTTP server."""
import argparse
import json
import math
from pathlib import Path
import sys
import time

from advanced.safety import (ROOT,apply_limits,atomic_json,claim_model,guard,
                             memory_mb,profile,rest,single_worker,stop_requested)

sys.path.insert(0,str(ROOT/'starter'))
from baseline import pack_context
from lexical_retrieval import LexicalRetriever
from hybrid_retrieval import reciprocal_rank_fusion

CHUNKS=ROOT/'starter/data/day6/chunks.json'
STORE=ROOT/'starter/data/day6/chroma'
METHODS=('tfidf-syllable','tfidf-word','dense','hybrid','rerank')


def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def check():
    if stop_requested():raise InterruptedError('Đã nhận yêu cầu dừng; checkpoint được giữ nguyên.')
    return guard()


def dense_search(query,filters,top_k,chunks):
    """Use the frozen Day 6 encoding/index with a single-thread, batch-one loader."""
    import chromadb
    from chromadb.config import Settings
    from day6_retriever import Day6Retriever
    run=load(STORE/'run.json');stats=load(STORE/'strategy_stats.json')
    if run['status']!='success' or run['metric']!='cosine':raise ValueError('Invalid Day 6 snapshot')
    collection=chromadb.PersistentClient(path=str(STORE),settings=Settings(anonymized_telemetry=False)).get_collection(
        run['collections'][run['selected_on_dev']],embedding_function=None)
    collection.modify(configuration={'hnsw':{'num_threads':1}})
    raw=collection.get(include=['documents','metadatas'])
    stored=[Day6Retriever._chunk(cid,text,meta) for cid,text,meta in zip(raw['ids'],raw['documents'],raw['metadatas'])]
    if sorted(stored,key=lambda c:c['id'])!=sorted(chunks,key=lambda c:c['id']):
        raise ValueError('Corpus differs from Chroma; refusing a mixed demo')
    if collection.count()!=stats[run['selected_on_dev']]['chunk_count']:raise ValueError('Snapshot count differs')
    check();claim_model('embedding')
    from local_embeddings import LocalEmbedder
    model=LocalEmbedder(batch_size=1,cpu_threads=1)
    if (model.model_name,model.revision,model.dimensions)!=(run['model'],run['revision'],run['dimensions']):
        raise ValueError('Embedding model differs from snapshot')
    check();vector=model.embed_query(query);check()
    raw=collection.query(query_embeddings=[vector],n_results=min(top_k,len(chunks)),where=filters or None,
                         include=['documents','metadatas','distances'])
    return [{**Day6Retriever._chunk(cid,text,meta),'score':1-float(distance),'distance':float(distance)}
            for cid,text,meta,distance in zip(raw['ids'][0],raw['documents'][0],raw['metadatas'][0],raw['distances'][0])]


def basic_retrieve(payload):
    chunks=load(CHUNKS);query=payload['query'];method=payload['method'];k=payload['top_k']
    filters={'category':payload['category']} if payload.get('category') else None
    started=time.monotonic();info={}
    if method.startswith('tfidf-'):
        index=LexicalRetriever(chunks,method.split('-')[1])
        check();rows=index.search(query,filters=filters,top_k=k)
        info={'query_terms':index.tokenizer(query),'vocabulary_size':len(index.idf)}
    else:
        dense=dense_search(query,filters,12 if method in ('hybrid','rerank') else k,chunks)
        rows=dense
        if method in ('hybrid','rerank'):
            index=LexicalRetriever(chunks,'word');check()
            lexical=index.search(query,filters=filters,top_k=12)
            rows=reciprocal_rank_fusion({'dense':dense,'lexical':lexical},constant=60)
            info={'dense_candidates':dense,'lexical_candidates':lexical,'rrf_constant':60,
                  'query_terms':index.tokenizer(query)}
        rows=rows[:12 if method=='rerank' else k]
    check()
    context,ids=pack_context(rows[:k],budget=payload['budget'])
    return {'kind':'basic','method':method,'query':query,'top_k':k,'filters':filters,
            'results':rows,'context':context,'context_ids':ids,'stages':info,
            'elapsed_seconds':round(time.monotonic()-started,3),'score_type':
            'RRF' if method in ('hybrid','rerank') else 'cosine',
            'demo_profile':{'candidate_k':12,'cpu_threads':1,'batch_size':1,'budget':payload['budget']}}


def basic_rerank(payload,retrieved):
    from setup_retrieval import MODEL_PATH
    check();claim_model('reranker')
    import torch
    from sentence_transformers import CrossEncoder
    torch.set_num_threads(1)
    model=CrossEncoder(str(MODEL_PATH),device='cpu',local_files_only=True,trust_remote_code=False,
                       max_length=256,activation_fn=torch.nn.Identity())
    check();start=time.monotonic();ranked=[]
    for rank,row in enumerate(retrieved['results'],1):
        check()
        if time.monotonic()-start>=30:raise TimeoutError('Rerank vượt ngân sách xử lý 30 giây')
        score=float(model.predict([(payload['query'],row['text'])],batch_size=1,show_progress_bar=False)[0])
        if not math.isfinite(score):raise ValueError('Non-finite rerank score')
        ranked.append({**row,'retrieval_score':row['score'],'pre_rerank_rank':rank,'score':score});rest()
    ranked.sort(key=lambda r:(-r['score'],r['id']))
    rows=ranked[:payload['top_k']];context,ids=pack_context(rows,budget=payload['budget'])
    return {**retrieved,'results':rows,'context':context,'context_ids':ids,'score_type':'CrossEncoder logit',
            'reranker':{'model':load(MODEL_PATH/'artifact.json')['model'],'batch_size':1,'max_length':256},
            'rerank_seconds':round(time.monotonic()-start,3)}


def compare(payload):
    outputs=[]
    for method in ('tfidf-syllable','tfidf-word'):
        check();outputs.append(basic_retrieve({**payload,'method':method}))
    return {'kind':'compare','query':payload['query'],'outputs':outputs,
            'note':'So sánh trực tiếp cùng query/filter. Đây không phải một lần chạy lại benchmark.'}


def ipcc_lexical(payload):
    from advanced.index import ART
    from advanced.retriever import pack_sources
    from baseline import TfidfIndex
    units={u['id']:u for u in load(ART/'units.json')}
    kind=payload.get('content_kind','all')
    if kind!='all':units={uid:u for uid,u in units.items() if u['kind']==kind}
    chunks=[c for c in load(ART/'chunks.json') if c['unit_id'] in units]
    check();start=time.monotonic()
    candidates=TfidfIndex(chunks).search(payload['query'],top_k=12) if chunks else []
    sources,info=pack_sources(payload['query'],candidates,units,4,3600)
    return {'kind':'ipcc','method':'tfidf-syllable','query':payload['query'],'sources':sources,
            'candidates':candidates,'packing':info,'content_kind':kind,
            'elapsed_seconds':round(time.monotonic()-start,3),'answer_generated':False,
            'note':'Native text, bảng và nhãn/caption. Chưa đọc giá trị chỉ nằm trong pixel/màu ảnh.'}


def main():
    limits=apply_limits()
    import os
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1';os.environ['ANONYMIZED_TELEMETRY']='False'
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task-dir',required=True,type=Path)
    parser.add_argument('--stage',choices=['retrieve','rerank','compare','ipcc'],required=True)
    args=parser.parse_args();folder=args.task_dir.resolve()
    if not folder.is_relative_to((ROOT/'demo/artifacts/tasks').resolve()):parser.error('Task directory must stay in demo/artifacts/tasks')
    with single_worker():
        check();payload=load(folder/'request.json')
        if args.stage=='rerank':result=basic_rerank(payload,load(folder/'retrieval.json'))
        elif args.stage=='compare':result=compare(payload)
        elif args.stage=='ipcc':result=ipcc_lexical(payload)
        else:result=basic_retrieve(payload)
        result['resource_limits']=limits;result['memory_mb']=memory_mb()
        atomic_json(folder/('retrieval.json' if args.stage=='retrieve' else 'result.json'),result)


if __name__=='__main__':main()

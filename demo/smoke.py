"""Check ONE real web operation at a time against an already running demo."""
import argparse
import json
from pathlib import Path
import time
from urllib.request import Request,urlopen

from advanced.safety import ROOT,atomic_json,apply_limits


def main():
    apply_limits()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=['lexical','word','filter','compare','ipcc','ipcc-table','dense','hybrid','rerank','index'],default='lexical')
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args();base=f'http://127.0.0.1:{args.port}'
    def api(path,body=None):
        data=json.dumps(body,ensure_ascii=False).encode('utf-8') if body is not None else None
        headers={'Content-Type':'application/json','Origin':base}
        if body is not None:headers['X-Demo-Token']=token
        with urlopen(Request(base+path,data=data,headers=headers),timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))
    token=api('/api/session')['token']
    before=api('/api/status')
    payload={'kind':'basic','method':{'lexical':'tfidf-syllable','filter':'tfidf-syllable','word':'tfidf-word'}.get(args.case,args.case),
             'query':'Dữ liệu dùng chung là gì?','top_k':9,'budget':2000,'category':'du_lieu' if args.case=='filter' else ''}
    if args.case=='compare':payload['kind']='compare';payload.pop('method')
    if args.case in ('ipcc','ipcc-table'):
        payload={'kind':'ipcc','query':'Figure SPM.7 demand-side mitigation potential' if args.case=='ipcc' else 'Table SPM.1 emissions reductions 2030',
                 'content_kind':'figure' if args.case=='ipcc' else 'table'}
    if args.case=='index':payload={'kind':'index','stage':'embed','limit':2}
    start=time.monotonic();task=api('/api/tasks',payload);tid=task['id'];last_phase=None
    while time.monotonic()-start<300:
        task=api('/api/tasks/'+tid)
        if task['phase']!=last_phase:
            print(task['phase'],flush=True);last_phase=task['phase']
        if task['status'] not in ('queued','running'):break
        time.sleep(1)
    if task['status']!='success':raise RuntimeError(task.get('error',task['status']))
    result=task['result']
    if payload['kind']=='basic':
        assert 0<len(result['results'])<=9
        assert len(result['context'])<=2000
        assert all(row['metadata']['category']=='du_lieu' for row in result['results']) if args.case=='filter' else True
    elif payload['kind']=='compare':
        assert len(result['outputs'])==2
        assert any('_' in term for term in result['outputs'][1]['stages']['query_terms'])
    elif payload['kind']=='ipcc':
        assert result['sources']
        assert all(source['kind']==payload['content_kind'] for source in result['sources'])
        page=result['sources'][0]['page']
        assert result['sources'][0]['label']==('Figure SPM.7' if args.case=='ipcc' else 'Table SPM.1')
        with urlopen(base+f'/files/ipcc.pdf',timeout=10) as response:assert response.read(4)==b'%PDF'
        image=ROOT/f'advanced/artifacts/document/pages/page-{page:03}.png'
        if image.exists():
            with urlopen(base+f'/files/pages/{page:03}.png',timeout=10) as response:assert response.read(4)==b'\x89PNG'
    else:assert result['index']['stored_embeddings']>=before['advanced']['indexed_chunks']
    verified={'case':args.case,'task_id':tid,'status':task['status'],'elapsed_seconds':task['elapsed_seconds'],
              'rows':len(result.get('results',result.get('sources',result.get('outputs',[])))),
              'memory_mb':result.get('memory_mb'),'stages':task['events']}
    path=ROOT/'demo/artifacts/verification.json'
    previous=json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    atomic_json(path,previous+[verified])
    print(json.dumps(verified,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()

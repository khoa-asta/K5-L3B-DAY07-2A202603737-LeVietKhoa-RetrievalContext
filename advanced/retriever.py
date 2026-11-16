"""Hybrid IPCC retrieval with generic figure/table reference lookup and page regions."""
import json
import os
from pathlib import Path
import re
import sys

from advanced.index import ART,ROOT,clean

sys.path.insert(0,str(ROOT/'starter'))
from baseline import TfidfIndex,tokenize
from hybrid_retrieval import reciprocal_rank_fusion
from advanced.safety import apply_limits,claim_model,guard,profile,stop_requested


def reference_key(text):
    return re.sub(r'[^a-z0-9]','',text.casefold())


def compact_text(unit,query,limit):
    text=re.sub(r'\bC(\d+):',r'column_\1:',unit['text'])
    if len(text)<=limit:return text
    lines=text.splitlines()
    terms=set(tokenize(query))-{'what','which','the','and','for','from','with','does','figure','table','report','are','that','this','how','in'}
    ranked=sorted(range(len(lines)),key=lambda i:(-len(terms & set(tokenize(lines[i]))),i))
    selected=set(range(min(3,len(lines))))
    for i in ranked:
        proposal=selected | set(range(max(0,i-1),min(len(lines),i+2)))
        if sum(len(lines[j])+1 for j in proposal)<=limit:selected=proposal
    return '\n'.join(lines[i] for i in sorted(selected))[:limit]


def pack_sources(query,candidates,units,top_k,budget):
    """Pack evidence without loading any model; shared by separate workers."""
    key=reference_key(query)
    named=[u for u in units.values() if u['kind'] in ('table','figure')
           and not u['label'].startswith('Layout') and reference_key(u['label']) in key]
    named.sort(key=lambda u:(u['label'],u['id']))
    selected=[];seen=set()
    for unit in named+[units[row['unit_id']] for row in candidates]:
        if unit['id'] not in seen:selected.append(unit);seen.add(unit['id'])
        if len(selected)>=top_k:break
    sources=[];used=0
    named_ids={u['id'] for u in named}
    for unit in selected:
        remaining=budget-used
        if remaining<150:break
        allowance=min(remaining,max(600,budget//max(1,len(named)))) if unit['id'] in named_ids else min(1200,remaining)
        text=compact_text(unit,query,allowance)
        source={k:unit[k] for k in ('id','kind','page','bbox','label','source','source_id','source_pages')}
        source.update(alias=f'S{len(sources)+1}',text=text,page_image=unit.get('page_image',
                     f'advanced/artifacts/document/pages/page-{unit["page"]:03}.png'))
        sources.append(source);used+=len(text)
    return sources,{'explicit_references':[u['label'] for u in named],'context_chars':used}


class IPCCRetriever:
    def __init__(self,rerank=False,candidate_k=None,top_k=None,budget=None):
        if rerank:
            raise ValueError('Use advanced.worker for reranking in a separate process; simultaneous models are disabled.')
        apply_limits();guard()
        cfg=profile()
        candidate_k=cfg['candidate_k'] if candidate_k is None else candidate_k
        top_k=cfg['top_k'] if top_k is None else top_k
        budget=cfg['context_chars'] if budget is None else budget
        if not 1<=candidate_k<=cfg['candidate_k'] or not 1<=top_k<=cfg['top_k'] or not 150<=budget<=cfg['context_chars']:
            raise ValueError('Requested retrieval exceeds the laptop resource profile.')
        os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
        os.environ['ANONYMIZED_TELEMETRY']='False'
        self.manifest=json.loads((ART/'manifest.json').read_text(encoding='utf-8'))
        if self.manifest.get('status')!='success':raise ValueError('Finish bounded embedding stages before retrieval. No model loaded.')
        self.units={u['id']:u for u in json.loads((ART/'units.json').read_text(encoding='utf-8'))}
        self.chunks=json.loads((ART/'chunks.json').read_text(encoding='utf-8'))
        self.by_id={c['id']:c for c in self.chunks}
        self.lexical=TfidfIndex(self.chunks)
        import chromadb
        from chromadb.config import Settings
        self.client=chromadb.PersistentClient(path=str(ART/'chroma'),settings=Settings(anonymized_telemetry=False))
        self.collection=self.client.get_collection(self.manifest['collection'],embedding_function=None)
        self.collection.modify(configuration={'hnsw':{'num_threads':1}})
        if self.collection.count()!=len(self.chunks):raise ValueError('IPCC index count differs')
        claim_model('embedding')
        from local_embeddings import LocalEmbedder
        self.embedder=LocalEmbedder(batch_size=1,cpu_threads=1)
        guard()
        self.reranker=None
        self.candidate_k,self.top_k,self.budget=candidate_k,top_k,budget

    def search(self,query):
        if not query.strip():raise ValueError('Empty search query')
        if stop_requested():raise InterruptedError('STOP requested')
        guard()
        vector=self.embedder.embed_query(query)
        raw=self.collection.query(query_embeddings=[vector],n_results=min(self.candidate_k,len(self.chunks)),
            include=['distances'])
        dense=[{**self.by_id[cid],'score':1-float(distance)} for cid,distance in zip(raw['ids'][0],raw['distances'][0])]
        lexical=self.lexical.search(query,top_k=self.candidate_k)
        fused=reciprocal_rank_fusion({'dense':dense,'lexical':lexical})
        candidates=fused[:self.candidate_k]
        sources,packing=pack_sources(query,candidates,self.units,self.top_k,self.budget)
        return sources,{'query':query,'dense_candidates':dense,'lexical_candidates':lexical,
                         'ranked_candidates':candidates,'reranker':None,**packing,
                         'index_signature':self.manifest['signature']}

"""Resume and process-isolation contracts; no neural model is loaded by tests."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import ModuleType,SimpleNamespace
from unittest.mock import patch

from advanced import index,safety
from advanced.retriever import pack_sources,IPCCRetriever
from advanced.worker import finish_action,job_path


class LowResourceTests(unittest.TestCase):
    def test_imports_do_not_load_neural_models(self):
        code="import sys; import advanced.index, advanced.worker, advanced.agent, advanced.retriever; assert 'torch' not in sys.modules; assert 'sentence_transformers' not in sys.modules"
        subprocess.run([sys.executable,'-B','-c',code],cwd=safety.ROOT,check=True,timeout=15)

    def test_multiple_models_are_blocked_including_same_kind(self):
        with patch.object(safety,'_ACTIVE_MODEL_KIND',None):
            safety.claim_model('embedding')
            with self.assertRaises(RuntimeError):safety.claim_model('llm')
            with self.assertRaises(RuntimeError):safety.claim_model('embedding')

    def test_low_ram_and_rss_are_rejected(self):
        with patch.object(safety,'memory_mb',return_value={'available':3000,'rss':100}):
            with self.assertRaises(MemoryError):safety.guard()
        with patch.object(safety,'memory_mb',return_value={'available':9000,'rss':2000}):
            with self.assertRaises(MemoryError):safety.guard()

    def test_worker_lock_blocks_another_process_and_releases(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(safety,'ROOT',Path(temp)):
            code="from pathlib import Path; from advanced import safety; safety.ROOT=Path("+repr(temp)+");\nwith safety.single_worker(): pass"
            with safety.single_worker():
                blocked=subprocess.run([sys.executable,'-B','-c',code],cwd=index.ROOT,capture_output=True,timeout=10)
                self.assertNotEqual(blocked.returncode,0)
            released=subprocess.run([sys.executable,'-B','-c',code],cwd=index.ROOT,capture_output=True,timeout=10)
            self.assertEqual(released.returncode,0,released.stderr)

    def test_prepare_resumes_and_preserves_completed_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);doc=root/'doc';art=root/'index';doc.mkdir()
            pages=[{'page':n,'text':'Climate report text','blocks':[{'bbox':[0,0,10,10],
                'text':f'Climate report evidence for physical page number {n}.'}],
                'tables':[],'captions':[],'drawing_count':0,'words':[],'width':10,'height':10} for n in range(1,4)]
            safety.atomic_json(doc/'manifest.json',{'source_sha256':'example-sha'})
            safety.atomic_json(doc/'pages.json',pages)
            with patch.object(index,'ART',art),patch.object(index,'OUT',doc),patch.object(safety,'guard'),patch.object(safety,'rest'),patch.object(safety,'stop_requested',return_value=False):
                first=index.prepare(1,30)
                self.assertEqual(first['prepared_pages'],1)
                saved=(art/'parts/page-001.json').read_bytes()
                second=index.prepare(2,30)
                self.assertTrue(second['complete'])
                self.assertEqual((art/'parts/page-001.json').read_bytes(),saved)
                from advanced.tokenizer_only import OfflineTokenizer
                tokenizer=OfflineTokenizer(index.ROOT/'starter/.models/paraphrase-multilingual-MiniLM-L12-v2/tokenizer.json')
                units=index.make_units(pages,'example-sha')
                expected=[c for u in units for c in index.split_unit(u,tokenizer)]
                self.assertEqual(json.loads((art/'chunks.json').read_text(encoding='utf-8')),expected)
                manifest=json.loads((art/'manifest.json').read_text(encoding='utf-8'))
                self.assertEqual(manifest['signature'],hashlib.sha256(json.dumps(expected,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
                manifest['status']='success';safety.atomic_json(art/'manifest.json',manifest)
                index.prepare(2,30)
                self.assertEqual(json.loads((art/'manifest.json').read_text())['status'],'success')

    def test_context_budget_and_source_count_apply_to_explicit_references(self):
        units={}
        for n in range(1,8):
            units[str(n)]={'id':str(n),'kind':'figure','label':f'Figure {n}.1','text':'Evidence '*2000,
                'page':n,'bbox':[0,0,10,10],'source':'ipcc.pdf','source_id':'ipcc','source_pages':[n]}
        sources,info=pack_sources(' '.join(u['label'] for u in units.values()),[],units,4,3600)
        self.assertLessEqual(len(sources),4)
        self.assertLessEqual(sum(len(s['text']) for s in sources),3600)
        self.assertEqual(info['context_chars'],sum(len(s['text']) for s in sources))

    def test_embedding_resumes_from_actual_ids_not_stale_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            art=Path(temp)
            safety.atomic_json(art/'manifest.json',{'collection':'test','status':'prepared'})
            chunks=[{'id':cid,'text':f'Text {cid}','metadata':{'page':1}} for cid in ('a','b','c')]
            safety.atomic_json(art/'chunks.json',chunks)
            safety.atomic_json(art/'embed-state.json',{'completed':1})
            existing={'a','b'};embedded=[]
            class Collection:
                name='test'
                def get(self,**kwargs):return {'ids':sorted(existing)}
                def modify(self,**kwargs):pass
                def count(self):return len(existing)
                def upsert(self,ids,**kwargs):existing.update(ids)
            class FakeEmbedder:
                def __init__(self,**kwargs):
                    if kwargs!={'batch_size':1,'cpu_threads':1}:raise AssertionError(kwargs)
                def embed_query(self,text):embedded.append(text);return [0.1]*384
            chroma=ModuleType('chromadb');chroma.PersistentClient=lambda **kwargs:SimpleNamespace(get_or_create_collection=lambda *a,**k:Collection())
            config=ModuleType('chromadb.config');config.Settings=lambda **kwargs:kwargs
            local=ModuleType('local_embeddings');local.LocalEmbedder=FakeEmbedder
            with patch.object(index,'ART',art),patch.dict(sys.modules,{'chromadb':chroma,'chromadb.config':config,'local_embeddings':local}),patch.object(safety,'claim_model'),patch.object(safety,'guard',return_value={'rss':100}),patch.object(safety,'rest'),patch.object(safety,'stop_requested',return_value=False):
                result=index.embed(1,30)
                self.assertTrue(result['complete'])
                self.assertEqual(result['embedded_this_run'],1)
                self.assertEqual(embedded,['Text c'])
                self.assertEqual(json.loads((art/'embed-state.json').read_text())['completed'],3)
                result=index.embed(1,30)
                self.assertEqual(result['embedded_this_run'],0)
                self.assertEqual(embedded,['Text c'])

    def test_retriever_rejects_simultaneous_reranking(self):
        with self.assertRaises(ValueError):IPCCRetriever(rerank=True)

    def test_no_answer_or_abstention_is_invented_on_search_exhaustion(self):
        job={'events':[],'searches':2}
        with self.assertRaises(RuntimeError):finish_action(job,{'action':'search','query':'more evidence'},{})
        self.assertNotIn('answer',job)
        self.assertNotIn('status',job)

    def test_answer_cannot_cite_trimmed_out_sources(self):
        job={'events':[],'searches':1}
        with self.assertRaises(ValueError):
            finish_action(job,{'action':'answer','answer':'Something','citations':['S2']},
                          {'sources_supplied':[{'alias':'S1'}]})

    def test_job_path_cannot_escape_workspace(self):
        for name in ('../outside','..','C:\\outside','a/b',''):
            with self.assertRaises(ValueError):job_path(name)


if __name__=='__main__':unittest.main()

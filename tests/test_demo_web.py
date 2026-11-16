"""HTTP and task boundaries. Neural inference is exercised separately, one stage at a time."""
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch,Mock
from urllib.error import HTTPError
from urllib.request import Request,urlopen

from demo import server


class DemoContracts(unittest.TestCase):
    def test_bounded_inputs_and_category_validation(self):
        for bad in ({'kind':'shell'},{'kind':'basic','query':' '},
                    {'kind':'basic','query':'q','top_k':True},
                    {'kind':'basic','query':'q','top_k':100},
                    {'kind':'basic','query':'q','category':'../private'},
                    {'kind':'index','limit':64},
                    {'kind':'ipcc','query':'q','content_kind':'pixels'}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):server.validate_task(bad)

    def test_agent_cannot_run_on_incomplete_index(self):
        with patch.object(server,'index_status',return_value={'manifest.json':{'status':'embedding_partial','chunk_count':4455},'stored_embeddings':1090}):
            with self.assertRaisesRegex(ValueError,'index hoàn tất'):
                server.validate_task({'kind':'agent','query':'question'})

    def test_rerank_runs_in_another_process_after_retrieval(self):
        plan=server.stage_plan({'kind':'basic','method':'rerank'},Path('fixture'))
        self.assertEqual(len(plan),2)
        self.assertEqual(plan[0][1][-1],'retrieve')
        self.assertEqual(plan[1][1][-1],'rerank')
        self.assertNotIn('shell',str(plan))

    def test_busy_manager_rejects_second_task(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(server,'TASKS',Path(temp)):
            manager=server.TaskManager();manager.active='one'
            with self.assertRaisesRegex(RuntimeError,'một tác vụ'):manager.submit({'kind':'basic'})

    def test_timeout_preserves_failure_without_fabricating_result(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(server,'TASKS',Path(temp)):
            manager=server.TaskManager();tid='a'*32;folder=Path(temp)/tid;folder.mkdir()
            state={'id':tid,'request':{'kind':'basic','method':'dense'},'status':'queued','created_at':server.utc(),'events':[]}
            manager.tasks[tid]=state;manager.active=tid
            class Hanging:
                def __init__(self,*args,**kwargs):pass
                def wait(self,timeout):raise subprocess.TimeoutExpired('worker',timeout)
            with patch.object(server.subprocess,'Popen',Hanging),patch.object(server,'terminate_owned') as terminate,patch.object(server,'stop_requested',return_value=False):
                manager.run(tid)
            self.assertEqual(state['status'],'error')
            self.assertNotIn('result',state)
            self.assertIsNone(manager.active)
            terminate.assert_called_once()

    def test_restart_marks_inflight_task_interrupted(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(server,'TASKS',Path(temp)):
            tid='b'*32;path=Path(temp)/tid/'state.json'
            server.atomic_json(path,{'id':tid,'request':{'kind':'basic'},'status':'running','created_at':server.utc()})
            manager=server.TaskManager()
            self.assertEqual(manager.get(tid)['status'],'interrupted')
            self.assertIsNone(manager.active)


class DemoHTTP(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.tasks_patch=patch.object(server,'TASKS',Path(self.temp.name));self.tasks_patch.start()
        self.http=server.make_server(0);self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{self.http.server_port}'

    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join(timeout=2);self.tasks_patch.stop();self.temp.cleanup()

    def request(self,path,body=None,headers=None):
        data=json.dumps(body).encode() if body is not None else None
        return urlopen(Request(self.base+path,data=data,headers=headers or {}),timeout=5)

    def test_assets_and_status_are_available_without_models(self):
        for path in ('/','/app.css','/app.js','/api/status'):
            with self.subTest(path=path),self.request(path) as response:self.assertEqual(response.status,200)

    def test_mutations_need_session_token_and_same_origin(self):
        for headers in ({},{'X-Demo-Token':self.http.token,'Origin':'https://outside.invalid'}):
            with self.assertRaises(HTTPError) as error:self.request('/api/tasks',{'kind':'basic','query':'test'},headers)
            self.assertEqual(error.exception.code,403)
            error.exception.close()

    def test_unknown_file_and_traversal_cannot_read_arbitrary_files(self):
        for path in ('/files/../../.env','/files/report/../../demo/server.py','/.venv/pyvenv.cfg','/api/tasks/../../index'):
            with self.subTest(path=path),self.assertRaises(HTTPError) as error:self.request(path)
            self.assertEqual(error.exception.code,404)
            error.exception.close()

    def test_pdf_supports_bounded_range(self):
        with self.request('/files/ipcc.pdf',headers={'Range':'bytes=0-63'}) as response:
            self.assertEqual(response.status,206)
            self.assertEqual(len(response.read()),64)
        with self.request('/files/ipcc.pdf',headers={'Range':'bytes=-64'}) as response:
            self.assertEqual(response.status,206)
            self.assertEqual(len(response.read()),64)
        handler=server.Handler.__new__(server.Handler)
        handler.server=self.http;handler.path='/files/ipcc.pdf';handler.headers={'Host':f'127.0.0.1:{self.http.server_port}'}
        handler.file=Mock(side_effect=ConnectionAbortedError('Client closed PDF'));handler.json=Mock()
        handler.do_GET()
        handler.json.assert_not_called()

    def test_validation_error_is_http_400_not_a_queued_worker(self):
        with self.assertRaises(HTTPError) as error:
            self.request('/api/tasks',{'kind':'basic','query':'q','top_k':999},
                         {'X-Demo-Token':self.http.token,'Origin':self.base})
        self.assertEqual(error.exception.code,400)
        error.exception.close()
        self.assertIsNone(self.http.manager.active)


if __name__=='__main__':unittest.main()

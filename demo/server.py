"""Local, dependency-free demo server. python -B -m demo.server"""
import argparse
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs,urlsplit
import uuid

from advanced.index import ART,status as index_status
from advanced.safety import ROOT,apply_limits,atomic_json,memory_mb,profile,single_worker,stop_requested

STATIC=ROOT/'demo/static'
TASKS=ROOT/'demo/artifacts/tasks'
METHODS=('tfidf-syllable','tfidf-word','dense','hybrid','rerank')


def load(path,default=None):
    path=Path(path)
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def utc():return datetime.now(timezone.utc).isoformat()


def validate_task(body):
    if not isinstance(body,dict):raise ValueError('Nội dung yêu cầu phải là JSON object')
    kind=body.get('kind')
    if kind not in ('basic','compare','ipcc','index','agent'):raise ValueError('Chức năng không hợp lệ')
    out={'kind':kind}
    if kind in ('basic','compare','ipcc','agent'):
        query=body.get('query','')
        if not isinstance(query,str) or not query.strip() or len(query)>1000:
            raise ValueError('Nhập câu hỏi từ 1 đến 1.000 ký tự')
        out['query']=query.strip()
    if kind in ('basic','compare'):
        method=body.get('method','tfidf-syllable')
        if method not in METHODS:raise ValueError('Phương pháp không hợp lệ')
        category=body.get('category','')
        if category not in ('','du_lieu','giao_dich_dien_tu'):raise ValueError('Category không hợp lệ')
        for key,default,lo,hi in (('top_k',9,1,9),('budget',2000,500,4000)):
            value=body.get(key,default)
            if type(value) is not int or not lo<=value<=hi:raise ValueError(f'{key} phải nằm trong {lo}–{hi}')
            out[key]=value
        out.update(method=method,category=category)
    if kind=='ipcc':
        content_kind=body.get('content_kind','all')
        if content_kind not in ('all','text','table','figure'):raise ValueError('Loại nội dung không hợp lệ')
        if not (ART/'chunks.json').exists():raise ValueError('Chưa có catalog IPCC; chạy prepare trước')
        out['content_kind']=content_kind
    if kind=='index':
        stage=body.get('stage','embed');limit=body.get('limit',2)
        if stage not in ('prepare','embed') or type(limit) is not int or limit not in (2,8,16):
            raise ValueError('Chọn prepare/embed và lượt 2, 8 hoặc 16')
        if stage=='prepare' and limit>8:raise ValueError('Chuẩn bị tối đa 8 trang/lượt trên giao diện')
        if stage=='embed' and not (ART/'manifest.json').exists():raise ValueError('Chuẩn bị xong catalog trước khi embedding')
        out.update(stage=stage,limit=limit)
    if kind=='agent':
        state=index_status();manifest=state.get('manifest.json',{})
        if manifest.get('status')!='success' or state.get('stored_embeddings')!=manifest.get('chunk_count'):
            raise ValueError('Dense/agent IPCC cần index hoàn tất. Hiện có thể demo TF-IDF IPCC ở mục bên trái.')
        name=body.get('agent_id')
        if name is not None:
            if not isinstance(name,str) or not re.fullmatch(r'web-[a-f0-9]{20}',name):raise ValueError('Agent ID không hợp lệ')
            job=load(ROOT/f'advanced/artifacts/jobs/{name}.json')
            if not job or job['question']!=out['query'] or job['status']!='pending':raise ValueError('Job không còn bước đang chờ hoặc câu hỏi đã thay đổi')
        out['agent_id']=name or 'web-'+uuid.uuid4().hex[:20]
    return out


def stage_plan(payload,folder):
    """Only fixed argument arrays, no shell commands or user-specified paths."""
    base=[sys.executable,'-B','-m','demo.worker','--task-dir',str(folder),'--stage']
    kind=payload['kind']
    if kind=='basic':
        plan=[('Truy xuất evidence',base+['retrieve'])]
        if payload['method']=='rerank':plan.append(('Rerank bằng model riêng',base+['rerank']))
        return plan
    if kind in ('compare','ipcc'):return [('So sánh tokenizer' if kind=='compare' else 'Tìm evidence IPCC',base+[kind])]
    if kind=='index':return [('Xử lý một lượt index',[sys.executable,'-B','-m','advanced.index','--stage',payload['stage'],
                                '--limit',str(payload['limit']),'--max-seconds','30'])]
    name=payload['agent_id'];path=ROOT/f'advanced/artifacts/jobs/{name}.json'
    plan=[]
    if not path.exists():plan.append(('Tạo checkpoint câu hỏi',[sys.executable,'-B','-m','advanced.worker','--job',name,'--question',payload['query']]))
    plan.append(('Một bước agent IPCC',[sys.executable,'-B','-m','advanced.worker','--job',name,'--stage','next']))
    return plan


def terminate_owned(process):
    if process is None or process.poll() is not None:return
    if os.name=='nt':
        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    else:process.terminate()
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:process.kill()


class TaskManager:
    def __init__(self):
        TASKS.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.active=None;self.tasks={};self.process=None
        for path in sorted(TASKS.glob('*/state.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:30]:
            state=load(path)
            if state.get('status') in ('running','queued'):
                state.update(status='interrupted',error='Máy chủ đã dừng trước khi tác vụ kết thúc; checkpoint vẫn được giữ.')
                atomic_json(path,state)
            self.tasks[state['id']]=state

    def save(self,state):
        atomic_json(TASKS/state['id']/'state.json',state)

    def submit(self,payload):
        with self.lock:
            if self.active:raise RuntimeError('Đang có một tác vụ. Chờ hoàn tất rồi chạy tiếp.')
            if stop_requested():raise RuntimeError('Đang có tín hiệu dừng. Bấm Cho phép chạy tiếp trước.')
            # A manual CLI worker uses the same OS lock as all web workers.
            with single_worker():pass
            tid=uuid.uuid4().hex;folder=TASKS/tid;folder.mkdir()
            atomic_json(folder/'request.json',payload)
            state={'id':tid,'request':payload,'status':'queued','phase':'Chờ worker','created_at':utc(),'events':[]}
            self.tasks[tid]=state;self.active=tid;self.save(state)
            if len(self.tasks)>32:
                oldest=sorted(self.tasks,key=lambda key:self.tasks[key]['created_at'])
                for key in oldest[:-32]:
                    if key!=self.active:self.tasks.pop(key,None)
            threading.Thread(target=self.run,args=(tid,),daemon=True).start()
            return json.loads(json.dumps(state))

    def get(self,tid):
        if not re.fullmatch(r'[a-f0-9]{32}',tid):return None
        with self.lock:
            state=self.tasks.get(tid) or load(TASKS/tid/'state.json')
            return json.loads(json.dumps(state)) if state else None

    def run(self,tid):
        folder=TASKS/tid;state=self.tasks[tid];payload=state['request'];began=time.monotonic()
        try:
            with self.lock:state.update(status='running',started_at=utc());self.save(state)
            plan=stage_plan(payload,folder)
            for i,(label,command) in enumerate(plan):
                if stop_requested():raise InterruptedError('Đã dừng trước bước kế tiếp; checkpoint được giữ nguyên.')
                with self.lock:state['phase']=label;self.save(state)
                stage_start=time.monotonic()
                with (folder/f'stage-{i+1}.log').open('w',encoding='utf-8') as log:
                    env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
                    process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,
                                             creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    with self.lock:self.process=process
                    try:code=process.wait(timeout=240)
                    except subprocess.TimeoutExpired:
                        terminate_owned(process);raise TimeoutError('Bước chạy vượt 240 giây; worker đã dừng, checkpoint giữ nguyên.')
                    finally:
                        with self.lock:self.process=None
                with self.lock:
                    state['events'].append({'stage':label,'seconds':round(time.monotonic()-stage_start,3),'exit_code':code})
                    self.save(state)
                if code:
                    detail=(folder/f'stage-{i+1}.log').read_text(encoding='utf-8',errors='replace')[-3500:]
                    raise RuntimeError(detail)
                if stop_requested():raise InterruptedError('Đã nhận yêu cầu dừng; kết quả/checkpoint của bước hiện tại được giữ.')
                if i+1<len(plan) and payload['kind']=='basic':
                    with self.lock:state['phase']='Nghỉ 10 giây; model trước đã thoát';self.save(state)
                    for _ in range(10):
                        if stop_requested():raise InterruptedError('Đã dừng giữa hai model.')
                        time.sleep(1)
            if payload['kind']=='basic':
                result=load(folder/('result.json' if payload['method']=='rerank' else 'retrieval.json'))
            elif payload['kind']=='index':result={'kind':'index','index':index_status()}
            elif payload['kind']=='agent':result={'kind':'agent','agent_id':payload['agent_id'],**load(ROOT/f'advanced/artifacts/jobs/{payload["agent_id"]}.json')}
            else:result=load(folder/'result.json')
            if result is None:raise RuntimeError('Worker không ghi kết quả; không tạo kết quả thay thế.')
            atomic_json(folder/'result.json',result)
            with self.lock:state.update(status='success',phase='Hoàn tất',result=result)
        except Exception as exc:
            with self.lock:state.update(status='stopped' if isinstance(exc,InterruptedError) else 'error',
                                       phase='Đã dừng' if isinstance(exc,InterruptedError) else 'Lỗi xử lý',error=str(exc))
        finally:
            with self.lock:
                state.update(finished_at=utc(),elapsed_seconds=round(time.monotonic()-began,3))
                self.save(state);self.active=None

    def close(self):
        with self.lock:
            if self.active:(ROOT/'advanced/STOP').touch()
            process=self.process
        if process:
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:terminate_owned(process)


def bootstrap(manager):
    state=index_status();manifest=state.get('manifest.json',{})
    with manager.lock:
        active=manager.active
        recent=[{'id':s['id'],'status':s['status'],'kind':s['request']['kind'],
                 'query':s['request'].get('query','Một lượt index'),'created_at':s['created_at']}
                for s in sorted(manager.tasks.values(),key=lambda s:s['created_at'],reverse=True)[:8]]
    return {'basic':{'chunk_count':401,'content_pages':49,'documents':load(ROOT/'data/day6_manifest.json',{}).get('documents',[])},
            'advanced':{'prepared_pages':state.get('prepare-state.json',{}).get('prepared_pages',0),
                'total_pages':186,'indexed_chunks':state.get('stored_embeddings',0),'total_chunks':manifest.get('chunk_count',0),
                'ready':manifest.get('status')=='success' and state.get('stored_embeddings')==manifest.get('chunk_count'),
                'unit_counts':manifest.get('unit_counts',{}),'status':manifest.get('status','not_prepared')},
            'stopped':stop_requested(),'memory_mb':memory_mb(),'profile':profile(),'active_task':active,
            'recent_tasks':recent}


class Handler(BaseHTTPRequestHandler):
    server_version='Day7Demo/1.0'

    def log_message(self,format,*args):pass

    def handle(self):
        try:super().handle()
        except ConnectionError:pass  # A browser may close a PDF range or a polling request.

    def json(self,value,code=200):
        raw=json.dumps(value,ensure_ascii=False).encode('utf-8')
        self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(raw)

    def trusted_host(self):
        return self.headers.get('Host','') in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')

    def do_GET(self):
        if not self.trusted_host():return self.json({'error':'Invalid host'},403)
        url=urlsplit(self.path);path=url.path
        try:
            if path=='/api/status':return self.json(bootstrap(self.server.manager))
            if path=='/api/session':return self.json({'token':self.server.token})
            if path=='/api/benchmarks':
                split=parse_qs(url.query).get('split',['dev'])[0]
                if split not in ('dev','test'):return self.json({'error':'Invalid split'},400)
                value=load(ROOT/f'starter/results/benchmark-day7-local/{split}/summary.json')
                return self.json({'available':value is not None,'data':value,'origin':'saved_benchmark',
                    'note':'Kết quả đã lưu; cấu hình benchmark candidate_k=30, không phải lượt demo web candidate_k=12.'})
            if path.startswith('/api/tasks/'):
                tid=path.removeprefix('/api/tasks/');task=self.server.manager.get(tid)
                return self.json(task if task else {'error':'Task not found'},200 if task else 404)
            if path=='/api/references':
                units=load(ART/'units.json',[]);seen=set();rows=[]
                for u in units:
                    key=(u['label'],u['page'])
                    if u['kind'] in ('table','figure') and not u['label'].startswith('Layout') and key not in seen:
                        rows.append({k:u[k] for k in ('label','page','kind')});seen.add(key)
                return self.json(rows)
            files={'/':STATIC/'index.html','/app.css':STATIC/'app.css','/app.js':STATIC/'app.js',
                   '/files/ipcc.pdf':ROOT/'data/IPCC_AR6_SYR_FullVolume.pdf',
                   '/files/report.md':ROOT/'report/individual/2A202603737_LeVietKhoa.md',
                   '/files/guide.md':ROOT/'docs/DEMO_WEB.md'}
            for doc in load(ROOT/'data/day6_manifest.json',{}).get('documents',[]):
                target=(ROOT/doc['source_path']).resolve()
                if target.is_relative_to((ROOT/'data').resolve()):files[f'/files/{doc["source_id"]}.pdf']=target
            match=re.fullmatch(r'/files/pages/(\d{3})\.png',path)
            if match and 1<=int(match[1])<=186:files[path]=ROOT/f'advanced/artifacts/document/pages/page-{match[1]}.png'
            target=files.get(path)
            if not target or not target.is_file():return self.json({'error':'File not found'},404)
            return self.file(target)
        except ConnectionError:return  # Do not write a second response to a closed socket.
        except (ValueError,OSError) as exc:return self.json({'error':str(exc)},500)

    def file(self,path):
        size=path.stat().st_size;start=0;end=size-1;partial=False
        if self.headers.get('Range'):
            match=re.fullmatch(r'bytes=(\d*)-(\d*)',self.headers['Range'])
            if not match or not any(match.groups()):return self.json({'error':'Unsupported range'},416)
            if not match[1]:
                suffix=int(match[2])
                if suffix<1:return self.json({'error':'Invalid suffix range'},416)
                start=max(0,size-suffix)
            else:start=int(match[1]);end=min(int(match[2]) if match[2] else end,end)
            partial=True
            if start>end:return self.json({'error':'Range outside file'},416)
        self.send_response(206 if partial else 200)
        content_type=mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
        if path.suffix=='.md':content_type='text/plain; charset=utf-8'
        self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(end-start+1))
        self.send_header('Accept-Ranges','bytes');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Cache-Control','no-cache')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if partial:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers()
        with path.open('rb') as stream:
            stream.seek(start);remaining=end-start+1
            while remaining:
                block=stream.read(min(65536,remaining))
                if not block:break
                self.wfile.write(block);remaining-=len(block)

    def do_POST(self):
        origin=self.headers.get('Origin')
        valid_origin=origin in (None,f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}')
        if not self.trusted_host() or not valid_origin or not secrets.compare_digest(self.headers.get('X-Demo-Token',''),self.server.token):
            return self.json({'error':'Yêu cầu không đến từ giao diện demo local.'},403)
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=16384:raise ValueError('Request size invalid')
            body=json.loads(self.rfile.read(length))
            if self.path=='/api/tasks':
                payload=validate_task(body)
                return self.json(self.server.manager.submit(payload),202)
            if self.path=='/api/control':
                action=body.get('action')
                if action=='stop':(ROOT/'advanced/STOP').touch()
                elif action=='resume':
                    if self.server.manager.active:raise RuntimeError('Chờ tác vụ hiện tại kết thúc rồi chạy tiếp.')
                    (ROOT/'advanced/STOP').unlink(missing_ok=True)
                else:raise ValueError('Control action invalid')
                return self.json({'stopped':stop_requested()})
            return self.json({'error':'Not found'},404)
        except (ValueError,TypeError,json.JSONDecodeError) as exc:return self.json({'error':str(exc)},400)
        except RuntimeError as exc:return self.json({'error':str(exc)},409)


def make_server(port=8765):
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.token=secrets.token_hex(24);server.manager=TaskManager()
    return server


def main():
    apply_limits()
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    with single_worker('web-server.lock'):
        server=make_server(args.port)
        print(f'Day 7 demo: http://127.0.0.1:{server.server_port}\nCtrl+C to stop. Models load only after an explicit Run action.',flush=True)
        try:server.serve_forever(poll_interval=0.3)
        except KeyboardInterrupt:pass
        finally:server.manager.close();server.server_close()


if __name__=='__main__':main()

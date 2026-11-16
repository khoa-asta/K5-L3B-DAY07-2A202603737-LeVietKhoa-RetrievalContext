"""Bounded, single-worker execution and resource guards for the user's laptop."""
from contextlib import contextmanager
import ctypes
import json
import os
from pathlib import Path
import time

ROOT=Path(__file__).resolve().parents[1]
PROFILE_PATH=ROOT/'advanced/low_resource.json'
_ACTIVE_MODEL_KIND=None


def profile():
    return json.loads(PROFILE_PATH.read_text(encoding='utf-8'))


def apply_limits():
    for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS',
                 'NUMEXPR_NUM_THREADS','RAYON_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
        os.environ[name]='1'
    os.environ['TOKENIZERS_PARALLELISM']='false'
    os.environ['CUDA_VISIBLE_DEVICES']=''
    os.environ['PYTHONDONTWRITEBYTECODE']='1'
    result={'cpu_threads':1,'gpu':'disabled','priority':'unchanged','affinity':'unavailable'}
    if os.name=='nt':
        kernel=ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype=ctypes.c_void_p
        handle=kernel.GetCurrentProcess()
        kernel.SetPriorityClass.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
        if kernel.SetPriorityClass(handle,0x4000):result['priority']='below_normal'
        proc_mask=ctypes.c_size_t();system_mask=ctypes.c_size_t()
        kernel.GetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t)]
        kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
        if kernel.GetProcessAffinityMask(handle,ctypes.byref(proc_mask),ctypes.byref(system_mask)) and proc_mask.value:
            cpu=proc_mask.value.bit_length()-1
            if kernel.SetProcessAffinityMask(handle,1<<cpu):result['affinity']=[cpu]
    return result


def memory_mb():
    if os.name!='nt':return {'available':None,'rss':None}
    class Memory(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(name,ctypes.c_ulonglong) for name in
            ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]
    class ProcessMemory(ctypes.Structure):
        _fields_=[('cb',ctypes.c_ulong),('faults',ctypes.c_ulong)]+[(name,ctypes.c_size_t) for name in
            ('peak_rss','rss','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile')]
    state=Memory();state.length=ctypes.sizeof(state)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state))
    process=ProcessMemory();process.cb=ctypes.sizeof(process)
    kernel=ctypes.windll.kernel32;kernel.GetCurrentProcess.restype=ctypes.c_void_p
    fn=ctypes.windll.psapi.GetProcessMemoryInfo
    fn.argtypes=[ctypes.c_void_p,ctypes.POINTER(ProcessMemory),ctypes.c_ulong]
    ok=fn(kernel.GetCurrentProcess(),ctypes.byref(process),process.cb)
    return {'available':round(state.available/2**20,1),'rss':round(process.rss/2**20,1) if ok else None,
            'peak_rss':round(process.peak_rss/2**20,1) if ok else None}


def guard(llm=False,after_load=False):
    cfg=profile();m=memory_mb()
    minimum=cfg['llm_min_available_ram_mb'] if llm and not after_load else cfg['min_available_ram_mb']
    maximum=cfg['llm_max_process_rss_mb'] if llm else cfg['max_process_rss_mb']
    if m['available'] is not None and m['available']<minimum:
        raise MemoryError(f'Not enough free RAM for this stage: {m["available"]} MB < {minimum} MB; checkpoint preserved.')
    if m['rss'] is not None and m['rss']>maximum:
        raise MemoryError(f'Process memory limit exceeded: {m["rss"]} MB > {maximum} MB; checkpoint preserved.')
    return m


@contextmanager
def single_worker(lock_name='worker.lock'):
    path=ROOT/'advanced/artifacts'/lock_name;path.parent.mkdir(parents=True,exist_ok=True)
    stream=path.open('a+b')
    stream.seek(0)
    if path.stat().st_size==0:stream.write(b'0');stream.flush();stream.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            try:msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            except OSError as exc:raise RuntimeError('Another advanced worker is active; start only one stage at a time.') from exc
        else:
            import fcntl
            fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally:
        stream.close()


def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temp.replace(path)


def rest(seconds=None):
    time.sleep(profile()['cooldown_seconds'] if seconds is None else seconds)


def claim_model(kind):
    global _ACTIVE_MODEL_KIND
    if _ACTIVE_MODEL_KIND is not None:
        raise RuntimeError(f'{_ACTIVE_MODEL_KIND} is already loaded. Run {kind} in a separate worker process to avoid simultaneous models.')
    _ACTIVE_MODEL_KIND=kind


def stop_requested():
    return (ROOT/'advanced/STOP').exists()

"""Run at most a few finite stages, in series, with rest and durable checkpoints."""
import argparse
from datetime import datetime,timezone
import json
import subprocess
import sys

from advanced.index import ART,status
from advanced.safety import ROOT,apply_limits,profile,single_worker,rest,stop_requested


def next_stage():
    state=status()
    prepared=state.get('prepare-state.json',{}).get('prepared_pages',0)
    if prepared<186 or not (ART/'manifest.json').exists():return 'prepare'
    if state.get('manifest.json',{}).get('status')!='success':return 'embed'
    return 'done'


def main():
    cfg=profile();apply_limits()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--steps',type=int,default=1,help='1..5 finite jobs, no endless background loop')
    parser.add_argument('--stage',choices=['auto','prepare','embed','status'],default='auto')
    args=parser.parse_args()
    if not 1<=args.steps<=5:parser.error('--steps must be 1..5')
    with single_worker('runner.lock'):
        for step in range(args.steps):
            if stop_requested():
                print('STOP file detected; no new job started. Checkpoints retained.');return
            stage=next_stage() if args.stage=='auto' else args.stage
            if stage=='done':print('IPCC index complete. No model loaded.');return
            command=[sys.executable,'-B','-m','advanced.index','--stage',stage]
            print(f'Finite job {step+1}/{args.steps}: {stage}',flush=True)
            began=datetime.now(timezone.utc).isoformat()
            result=subprocess.run(command,cwd=ROOT)
            history=ART/'run-history.jsonl';history.parent.mkdir(parents=True,exist_ok=True)
            with history.open('a',encoding='utf-8') as out:
                out.write(json.dumps({'started_at_utc':began,'finished_at_utc':datetime.now(timezone.utc).isoformat(),
                    'stage':stage,'exit_code':result.returncode})+'\n')
            if result.returncode:raise SystemExit(result.returncode)
            if step+1<args.steps:
                print(f'Resting {cfg["between_jobs_seconds"]} seconds before next job.',flush=True)
                rest(cfg['between_jobs_seconds'])


if __name__=='__main__':main()

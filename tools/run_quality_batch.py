"""Drive quality batches through a running service; never access or copy its API key."""
import argparse
import json
import time
import urllib.request
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['start','status','resume','pause','export'])
    parser.add_argument('--port',type=int,default=8766)
    parser.add_argument('--mode',choices=['sample','scope','first_release'],default='sample')
    parser.add_argument('--max-tasks',type=int,default=8)
    parser.add_argument('--token-budget',type=int,default=200000)
    parser.add_argument('--batch-id');parser.add_argument('--wait',action='store_true')
    args=parser.parse_args();base=f'http://127.0.0.1:{args.port}/api/agent/'
    def api(path,value=None):
        request=urllib.request.Request(base+path,data=json.dumps(value).encode() if value is not None else None,headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=120 if path=='bundle/export' else 20) as response:return json.load(response)
    if args.action=='export':print(json.dumps(api('bundle/export',{})));return
    if args.action=='start':
        result=api('batch/start',{'mode':args.mode,'max_tasks':args.max_tasks,'token_budget':args.token_budget});id=result['batch_id']
    elif args.action in ('resume','pause'):
        if not args.batch_id:raise SystemExit('--batch-id is required')
        result=api('batch/'+args.action,{'batch_id':args.batch_id});id=result['batch_id']
    else:
        all_batches=api('batches')['batches'];result=next(x for x in all_batches if x['batch_id']==args.batch_id) if args.batch_id else (all_batches[-1] if all_batches else {});id=args.batch_id
    print(json.dumps({k:v for k,v in result.items() if k not in ('results','tasks')},ensure_ascii=False),flush=True)
    if args.wait and id:
        while True:
            b=next(x for x in api('batches')['batches'] if x['batch_id']==id)
            print(json.dumps({k:b[k] for k in ['batch_id','state','cursor','total_tasks','calls_used','tokens_used','reason']},ensure_ascii=False),flush=True)
            if b['state']!='running':
                folder=Path(__file__).resolve().parents[1]/'review/agent-v5';folder.mkdir(exist_ok=True)
                (folder/(id+'.json')).write_text(json.dumps(b,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');break
            time.sleep(5)

if __name__=='__main__':main()

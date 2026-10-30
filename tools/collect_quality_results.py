"""Collect generated diagnostics and facts for independent review, never private conversations."""
import argparse
import json
import urllib.request
import urllib.parse
from pathlib import Path

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8766);parser.add_argument('--batch-id');parser.add_argument('--output',required=True);args=parser.parse_args()
    base=f'http://127.0.0.1:{args.port}/api/agent/'
    def get(path):
        with urllib.request.urlopen(base+path,timeout=20) as r:return json.load(r)
    batches=get('batches')['batches'];b=next(x for x in batches if x['batch_id']==args.batch_id) if args.batch_id else batches[-1]
    records=[]
    for result in b['results']:
        binding={'subject_type':result['scope']['subject']['type'],'subject_id':result['scope']['subject']['id'],'scenario':result['scope']['scenario_id'],'audience':result['audience'],'node_id':result['node_id'] or ''}
        query=urllib.parse.urlencode(binding);state=get('state?'+query);snapshot=get('snapshot?'+query);artifact=state['artifact']
        ids=artifact['output']['cited_node_ids'] if artifact else []
        records.append({'task':result,'artifact':artifact,'facts':{k:snapshot['node_results'][k]['status'] for k in ids}})
    destination=Path(args.output);destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(json.dumps({'batch':b,'records':records},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'state':b['state'],'tasks':len(records),'successes':sum(r['task']['state'] in ('succeeded','reused') for r in records),'calls':b['calls_used'],'tokens':b['tokens_used']}))

if __name__=='__main__':main()

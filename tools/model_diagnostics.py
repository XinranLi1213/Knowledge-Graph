"""Bounded generation/export/validation of portable model diagnoses."""
from pathlib import Path
import argparse
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.engine import Engine
from agent.provider import Provider,load_env
from agent.bundles import export_bundle,load_bundle,BUNDLE_SCHEMA
from agent.contracts import write_schemas

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['generate','export','validate','schemas'])
    parser.add_argument('--db',default=str(ROOT/'.runtime/agent.sqlite3'))
    parser.add_argument('--bundle',default=str(ROOT/'review/model-diagnostics/bundle.json'))
    parser.add_argument('--max-tasks',type=int,default=4)
    args=parser.parse_args()
    if args.action=='schemas':
        folder=ROOT/'review/agent-v5/contracts';write_schemas(folder)
        (folder/'bundle.schema.json').write_text(json.dumps(BUNDLE_SCHEMA,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return
    load_env(ROOT/'.env');Path(args.db).parent.mkdir(parents=True,exist_ok=True)
    provider=Provider() if args.action=='generate' else Provider('rules')
    if args.action=='generate' and provider.origin!='model':raise SystemExit('未配置API；没有调用模型、没有生成模型成果。')
    engine=Engine(ROOT,args.db,provider,False)
    try:
        if args.action=='generate':
            if not 1<=args.max_tasks<=4:raise SystemExit('首批预算只允许1–4项任务，每项最多4次模型调用。')
            scope=engine.scope({'type':'student','id':'DEMO001'},'mixed_evidence')
            tasks=[('teacher',None),('teacher','C05'),('student',None),('student','C05')]
            performed=0
            for audience,target in tasks:
                fresh=engine.fresh_artifact(scope,audience,target)
                if fresh and fresh['origin']=='model':continue
                if performed>=args.max_tasks:break
                result=engine.ensure_diagnosis(scope,audience,target,'retry');performed+=1
                while True:
                    run=engine.store.get('agent_run',result['run']['run_id'])
                    if run['state'] not in ('queued','running'):break
                    engine.process_one(result['run']['run_id'])
                print(json.dumps({'audience':audience,'node_id':target,'state':run['state'],'usage':run['usage']},ensure_ascii=False))
                if run['state']!='succeeded':raise SystemExit('本批停止：'+str(run.get('error')))
        if args.action in ('generate','export'):
            count=export_bundle(engine,args.bundle)
            print(json.dumps({'exported_model_diagnoses':count}))
        if args.action=='validate':print(json.dumps({'valid_model_diagnoses':len(load_bundle(engine,args.bundle))}))
    finally:engine.close()

if __name__=='__main__':main()

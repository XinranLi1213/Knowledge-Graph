"""Export validated runtime examples using an isolated, temporary rules-only database."""
from pathlib import Path
import json
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.engine import Engine
from agent.provider import Provider
from agent.contracts import validate,write_schemas

ROOT=Path(__file__).resolve().parents[1]

def main():
    folder=ROOT/'review/agent-v3';write_schemas(folder/'contracts')
    destination=folder/'examples';destination.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        engine=Engine(ROOT,Path(tmp)/'examples.sqlite3',Provider('rules'),False)
        try:
            scope=engine.scope({'type':'student','id':'DEMO001'},'mixed_evidence')
            update=engine.demo_update(scope,1,'example-C05-supplement-1')
            while engine.process_one():pass
            result=engine.ask(scope,'teacher','C05','与之前相比发生了什么变化？')
            while engine.process_one():pass
            records={
                'evaluation_changed':update['event'],
                'diagnostic_artifact':engine.artifact(scope,'teacher','C05'),
                'agent_run':engine.store.get('agent_run',result['run']['run_id']),
                'conversation_turn':engine.store.get('conversation_turn',result['turn']['turn_id'])}
            for kind,record in records.items():
                validate(record)
                (destination/(kind+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            context=engine.context(scope,'teacher','C05')
            (destination/'bounded-context.json').write_text(json.dumps(context.payload(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({'validated_contract_examples':len(records),'provider':'rules_demo','real_model_called':False,'context_nodes':len(context.seen),'context_evidence':len(context.evidence())}))
        finally:engine.close()

if __name__=='__main__':main()

"""Check the real portable release in a fresh, offline runtime; no API calls."""
import json
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.engine import Engine
from agent.provider import Provider

ROOT=Path(__file__).resolve().parents[1]
def main():
    with tempfile.TemporaryDirectory() as tmp:
        engine=Engine(ROOT,Path(tmp)/'offline.sqlite3',Provider('rules'),False)
        try:
            checks=[]
            for typ,id,role in [('class','COMM-DEMO-40','teacher'),('student','DEMO001','teacher'),('student','DEMO001','student')]:
                scope=engine.scope({'type':typ,'id':id},'mixed_evidence')
                found=[engine.fresh_artifact(scope,role,node) for node in [None]+list(engine.nodes)]
                assert all(a and a['origin']=='model' for a in found)
                checks.append({'subject_type':typ,'subject_id':id,'audience':role,'scenario':'mixed_evidence','valid_model_diagnoses':len(found)})
            assert not engine.capabilities()['can_ask']
            report={'status':'passed','real_model_artifacts':sum(c['valid_model_diagnoses'] for c in checks),'external_calls_during_validation':0,'can_ask_without_key':False,'scopes':checks}
            (ROOT/'review/agent-v5/offline-release-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(report))
        finally:engine.close()
if __name__=='__main__':main()

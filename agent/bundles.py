"""Portable model diagnoses. No credentials, conversations or raw API logs."""
import json
from pathlib import Path
from jsonschema import validate as json_validate
from .contracts import SCHEMAS,validate
from .context import digest,ref

BUNDLE_SCHEMA={'type':'object','required':['bundle_version','entries'],'additionalProperties':False,'properties':{
    'bundle_version':{'const':'1.0'},'entries':{'type':'array','items':{'type':'object','required':['artifact','snapshot','previous','run'],'additionalProperties':False,'properties':{
        'artifact':SCHEMAS['diagnostic_artifact'],'snapshot':{'type':'object'},'previous':{'type':['object','null']},'run':SCHEMAS['agent_run']}}}}}

def load_bundle(engine,path,bootstrap=False):
    if not Path(path).is_file():return []
    value=json.loads(Path(path).read_text(encoding='utf-8'));json_validate(value,BUNDLE_SCHEMA)
    found=[];initial={};snapshots={};latest={}
    for entry in value['entries']:
        a=entry['artifact'];s=entry['snapshot'];scope=engine.scope(a['scope']['subject'],a['scope']['scenario_id'])
        scope_key=engine.key(scope)
        if scope_key not in initial:initial[scope_key]=engine.store.pointer('snapshot:'+scope_key)
        if a['origin']!='model' or 'generation' not in a or 'facts_fingerprint' not in a:raise ValueError('成果包只接受可追溯的模型诊断')
        current=engine.ensure(scope)
        # Validate complete facts using the same v2 semantic validator without importing them as current.
        probe={**s,'revision':current['revision']+1};engine._validate_snapshot(probe,current)
        if a['validated_against']!=ref(s):raise ValueError('成果与评价版本不匹配')
        previous=entry['previous']
        if previous and (previous['snapshot_id']!=s['snapshot_id'] or previous['revision']!=s['revision']-1):raise ValueError('前版绑定不匹配')
        if previous:engine._validate_snapshot({**previous,'revision':current['revision']+1},current)
        for candidate in [s]+([previous] if previous else []):
            identity=(candidate['snapshot_id'],candidate['revision'])
            old=snapshots.get(identity) or engine.store.get('snapshot',*identity)
            if old and digest(old)!=digest(candidate):raise ValueError('相同评价版本存在冲突事实')
            snapshots[identity]=candidate
        if scope_key not in latest or s['revision']>latest[scope_key]['revision']:latest[scope_key]=s
        ctx=engine.context(scope,a['audience'],a['target_node_id'],s,a['dependencies']);ctx.previous=previous
        ctx.validate_output(a['output'])
        if ctx.fingerprint(None)!=a['facts_fingerprint']:raise ValueError('成果包事实指纹不匹配')
        run=entry['run'];validate(run)
        if run['scope']!=scope or run['audience']!=a['audience'] or run['target_node_id']!=a['target_node_id'] or run['snapshot_ref']!=a['generated_against'] or run['generation']!=a['generation'] or run['state']!='succeeded' or run['usage']['model_calls']<1:raise ValueError('成果缺少成功模型生成记录')
        found.append(a)
    if bootstrap:
        # A fresh installation can display the facts shipped with the model result.
        # Existing local scopes are never rolled back or overwritten by a static package.
        with engine.store.transaction():
            for key,snapshot in latest.items():
                if initial[key]:continue
                for (sid,revision),candidate in snapshots.items():
                    if sid==snapshot['snapshot_id'] and not engine.store.get('snapshot',sid,revision):engine.store.put('snapshot',sid,candidate,revision)
                engine.store.pointer('snapshot:'+key,ref(snapshot))
    return found

def export_bundle(engine,path,max_items=100):
    path=Path(path)
    existing=json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'bundle_version':'1.0','entries':[]}
    json_validate(existing,BUNDLE_SCHEMA)
    entries=[]
    for a in engine.store.all('diagnostic_artifact'):
        if len(entries)>=max_items:break
        if a['origin']!='model' or not a.get('facts_fingerprint') or not a.get('generation'):continue
        scope=a['scope'];current=engine.ensure(scope)
        if a['validated_against']!=ref(current):continue
        if engine.artifact(scope,a['audience'],a['target_node_id'])['artifact_id']!=a['artifact_id']:continue
        ctx=engine.context(scope,a['audience'],a['target_node_id'],current,a['dependencies'])
        if ctx.fingerprint(None)!=a['facts_fingerprint']:continue
        runs=[r for r in engine.store.all('agent_run') if r.get('artifact_id')==a['artifact_id'] and r['state']=='succeeded']
        # Revalidated artifacts point to the original generation run by source fingerprint.
        if not runs:
            originals=[x for x in engine.store.all('diagnostic_artifact') if x['fingerprint']==a['fingerprint'] and x['scope']==a['scope'] and x['audience']==a['audience'] and x['target_node_id']==a['target_node_id']]
            ids={x['artifact_id'] for x in originals};runs=[r for r in engine.store.all('agent_run') if r.get('artifact_id') in ids and r['state']=='succeeded']
        if not runs:continue
        run=runs[-1]
        entries.append({'artifact':a,'snapshot':current,'previous':ctx.previous,'run':run})
    def key(entry):
        a=entry['artifact'];return digest([a['scope'],a['audience'],a['target_node_id'],a['facts_fingerprint']])
    ids={key(e) for e in entries}
    entries.extend(e for e in existing['entries'] if key(e) not in ids)
    value={'bundle_version':'1.0','entries':entries};json_validate(value,BUNDLE_SCHEMA)
    path.parent.mkdir(parents=True,exist_ok=True)
    pending=path.with_suffix('.tmp');pending.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');pending.replace(path)
    path.with_name('manifest.json').write_text(json.dumps({'bundle_version':'1.0','bundle_file':path.name,'entries':len(entries),'real_model_results_available':bool(entries)},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return len(entries)

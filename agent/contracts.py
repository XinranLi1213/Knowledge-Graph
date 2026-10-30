"""Four persisted runtime contracts and the narrow model output contract."""
from pathlib import Path
import json
from jsonschema import Draft202012Validator, FormatChecker

def obj(props):return {'type':'object','properties':props,'required':list(props),'additionalProperties':False}
def arr(t):return {'type':'array','items':t}
S={'type':'string','minLength':1};I={'type':'integer','minimum':1}
NULLS={'type':['string','null']}
SUB=obj({'type':{'enum':['student','class']},'id':S})
REF=obj({'snapshot_id':S,'revision':I})
SCOPE=obj({'subject':SUB,'scenario_id':S})
def record(kind,props):return obj({'schema_version':{'const':'3.0.0'},'record_type':{'const':kind},**props})
TRACE=obj({'tool':S,'arguments':{'type':'object'},'node_count':{'type':'integer','minimum':0}})
OUTPUT=obj({'explanation':S,'cited_node_ids':arr(S),'cited_evidence_ids':arr(S),'resource_ids':arr(S),'limitations':arr(S)})
SCHEMAS={
 'evaluation_changed':record('evaluation_changed',{'event_id':S,'scope':SCOPE,'before':REF,'after':REF,
  'request_hash':S,'changes':arr(obj({'node_id':S,'field':S,'before':{},'after':{}})),
  'affected_node_ids':arr(S),'created_at':S}),
 'diagnostic_artifact':record('diagnostic_artifact',{'artifact_id':S,'scope':SCOPE,'audience':{'enum':['teacher','student']},
  'target_node_id':NULLS,'generated_against':REF,'validated_against':REF,'fingerprint':S,
  'dependencies':obj({'read_nodes':arr(S),'queries':arr(obj({'tool':S,'arguments':{'type':'object'}}))}),
  'validity':{'enum':['fresh','historical']},'publication':{'const':'active'},
  'origin':{'enum':['rules_demo','model']},'output':OUTPUT,'created_at':S}),
 'agent_run':record('agent_run',{'run_id':S,'scope':SCOPE,'audience':{'enum':['teacher','student']},'target_node_id':NULLS,
  'snapshot_ref':REF,'trigger':{'enum':['view','evaluation_changed','question','retry']},
  'state':{'enum':['queued','running','succeeded','failed','superseded']},'mode':{'enum':['diagnosis','question']},
  'artifact_id':NULLS,'turn_id':NULLS,'error':NULLS,'tool_trace':arr(TRACE),
  'usage':obj({'model_calls':{'type':'integer','minimum':0},'input_tokens':{'type':'integer','minimum':0},'output_tokens':{'type':'integer','minimum':0}}),
  'created_at':S,'updated_at':S}),
 'conversation_turn':record('conversation_turn',{'turn_id':S,'session_id':S,'scope':SCOPE,'audience':{'enum':['teacher','student']},
  'target_node_id':NULLS,'snapshot_ref':REF,'discussed_artifact_id':NULLS,'question':S,
  'state':{'enum':['queued','running','succeeded','failed']},'answer':{'anyOf':[OUTPUT,{'type':'null'}]},
  'origin':{'enum':['rules_demo','model']},'created_at':S})}
# Optional extensions preserve existing v3 records; the fact fingerprint is independent of credentials/model.
GENERATION=obj({'provider':S,'model':S,'prompt_version':S,'elapsed_ms':{'type':'integer','minimum':0},'request_ids':arr(S)})
SCHEMAS['diagnostic_artifact']['properties'].update(facts_fingerprint=S,generation=GENERATION)
SCHEMAS['agent_run']['properties'].update(generation=GENERATION,error_code=NULLS)
SCHEMAS['conversation_turn']['properties'].update(generator=S)
VALIDATORS={k:Draft202012Validator(v,format_checker=FormatChecker()) for k,v in SCHEMAS.items()}
def validate(record):VALIDATORS[record['record_type']].validate(record)
def write_schemas(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    for k,v in SCHEMAS.items():(root/(k+'.schema.json')).write_text(json.dumps({'$schema':'https://json-schema.org/draft/2020-12/schema',**v},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (root/'model-output.schema.json').write_text(json.dumps(OUTPUT,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

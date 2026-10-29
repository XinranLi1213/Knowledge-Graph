"""Review-only validation and update-envelope checks. Never applies advice updates."""
from pathlib import Path
from collections import Counter, defaultdict
import copy, hashlib, json
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

ROOT=Path(__file__).resolve().parents[1];P=ROOT/'review'/'personalization-v2'
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def check(value,message):
    if not value:raise AssertionError(message)
schema=read(P/'contracts/contract.schema.json');Draft202012Validator.check_schema(schema)
validator=Draft202012Validator(schema,format_checker=FormatChecker())
manifest=read(P/'manifest.json');graph=read(P/manifest['graph_path']);registry=read(P/manifest['registry_path'])
catalog=read(P/manifest['resource_catalog_path']);policy=read(P/manifest['policy_path'])
for p in [graph,registry,catalog,policy]:validator.validate(p)
nodes={n['id']:n for n in graph['nodes']};profiles={s['student_id']:s for s in registry['students']}
check(len(nodes)==len(graph['nodes'])==138,'graph nodes')
check(len({e['id'] for e in graph['edges']})==285,'graph edges')
for n in graph['nodes']:
    check(not any(k in n for k in ['status','sidebar_info','remediation_advice','average_score']),'graph contains subject facts')
check(len(profiles)==40 and len({s['student_number'] for s in profiles.values()})==40,'roster IDs')
check(set(registry['classes'][0]['member_student_ids'])==set(profiles),'class membership')
for k,h in manifest['baseline_files_sha256'].items():check(hashlib.sha256((ROOT/k).read_bytes()).hexdigest()==h,'application baseline changed: '+k)
incoming=defaultdict(list)
for e in graph['edges']:
    check(e['source'] in nodes and e['target'] in nodes,'edge reference')
    if e['aggregation_weight'] is not None:incoming[e['target']].append(e)
for es in incoming.values():check(abs(sum(e['aggregation_weight'] for e in es)-1)<1e-9,'weight total')
resource_ids={r['resource_id'] for r in catalog['resources']}
for r in catalog['resources']:
    check(set(r['node_ids'])<=set(nodes),'resource node')
    path=(P/r['path']).resolve()
    check(path.is_relative_to((P/'resources').resolve()) and path.is_file(),'unavailable resource')

snapshots={};by_scenario=defaultdict(list)
for entry in manifest['snapshot_entries']:
    snap=read(P/entry['path']);validator.validate(snap)
    check(snap['snapshot_id']==entry['snapshot_id'] and snap['subject']==entry['subject'],'manifest subject binding')
    check(snap['graph_ref']==graph['graph_ref'],'snapshot graph revision')
    check(snap['registry_version']==registry['registry_version'],'roster revision')
    check(snap['policy_id']==policy['policy_id'] and snap['policy_version']==policy['policy_version'],'policy reference')
    check(set(snap['node_results'])==set(nodes),'full snapshot node set')
    ev={e['evidence_id']:e for e in snap['evidence']}
    check(len(ev)==len(snap['evidence']),'duplicate evidence')
    for e in ev.values():check(e['subject']==snap['subject'] and e['node_id'] in nodes,'cross-subject evidence')
    is_class=snap['subject']['type']=='class'
    if not is_class:check(snap['subject']['id'] in profiles,'unknown student')
    else:check(snap['subject']['id']==registry['classes'][0]['class_id'],'unknown class')
    for k,r in snap['node_results'].items():
        st=r['status'];val=st['achievement_rate'];cov=st['coverage_rate'];ls=st['learning_state'];pr=st['learning_progress']
        check(set(r['evidence_refs'])<=set(ev),'dangling evidence')
        check(set(r['input_node_ids'])<=set(nodes),'dangling result inputs')
        check(st['expected_count']==(40 if is_class else 1),'sample denominator')
        check(st['sample_count']==(st['expected_count'] if val is not None else 0),'sample numerator')
        expected='grey' if val is None or cov<.8 else 'green' if val>=80 else 'yellow' if val>=60 else 'red'
        check(st['health_color']==expected,'health mapping')
        check((expected=='grey')==(st['grey_reason'] is not None),'grey explanation')
        check(st['score_is_provisional']==(0<cov<1),'provisional mapping')
        if nodes[k]['level']=='L1_Ability':check(pr is None and r['progress_source']=='not_applicable','ability progress semantics')
        else:
            check(pr is not None,'course/knowledge progress missing')
            check((ls!='not_started' or pr==0) and (ls!='completed' or pr==1),'learning progress state')
        if val is None:check(cov==0 and not r['evidence_refs'],'unknown score evidence')
        else:check(bool(r['evidence_refs']),'missing basis for known score')
        if st['aggregation_basis']=='weighted_inputs':
            es=incoming[k];check(set(r['input_node_ids'])=={e['source'] for e in es},'aggregation inputs')
            c=sum(e['aggregation_weight']*snap['node_results'][e['source']]['status']['coverage_rate'] for e in es)
            check(abs(c-cov)<=2e-6,'coverage arithmetic')
            if c:
                score=sum(e['aggregation_weight']*snap['node_results'][e['source']]['status']['coverage_rate']*(snap['node_results'][e['source']]['status']['achievement_rate'] or 0) for e in es)/c
                check(abs(val-score)<=2e-6,'score arithmetic')
        elif st['aggregation_basis']=='course_total':
            check(nodes[k]['level']=='L2_Course' and not r['input_node_ids'],'course total aggregation boundary')
        if snap['evaluation_context']['scenario_id']=='course_totals_only' and nodes[k]['level']=='L3_Knowledge':
            check(val is None and cov==0 and st['health_color']=='grey','invented fine-grained score')
    check(snap['summary']['health_counts']=={c:Counter(r['status']['health_color'] for r in snap['node_results'].values())[c] for c in ['green','yellow','red','grey']},'summary count')
    snapshots[snap['snapshot_id']]=snap;by_scenario[snap['evaluation_context']['scenario_id']].append(snap)

for scenario,items in by_scenario.items():
    cls=next(s for s in items if s['subject']['type']=='class');people=[s for s in items if s['subject']['type']=='student']
    check(len(people)==40,'class member results incomplete')
    old=read(ROOT/'review'/'data'/(scenario+'.json'))
    old_nodes={n['id']:n for n in old['nodes']}
    for k,r in cls['node_results'].items():
        scores=[s['node_results'][k]['status']['achievement_rate'] for s in people]
        check(r['status']['achievement_rate']==old_nodes[k]['status']['achievement_rate'],'class score migration')
        if r['status']['achievement_rate'] is None:check(all(s is None for s in scores),'null class vs known students')
        else:check(all(s is not None for s in scores) and abs(sum(scores)/40-r['status']['achievement_rate'])<=2e-6,'personal vs class mean')

def recommendation_checks(rec,snap):
    results=snap['node_results'];ev={e['evidence_id'] for e in snap['evidence']}
    target=rec['target_node_id']
    check(target is None or target in nodes,'unknown recommendation node')
    for field in ['basis_node_ids','review_node_ids','prepare_node_ids']:check(set(rec[field])<=set(nodes),'unknown diagnostic node')
    check(set(rec['resource_ids'])<=resource_ids,'unknown resource')
    check(set(rec['evidence_refs'])<=ev,'foreign diagnostic evidence')
    available={e for k in rec['basis_node_ids'] for e in results[k]['evidence_refs']}
    check(set(rec['evidence_refs'])<=available,'evidence not in named basis')
    if target:
        st=results[target]['status'];val=st['achievement_rate']
        if rec['kind'] in ('low_score','provisional_low'):
            check(val is not None and val<60 and bool(rec['evidence_refs']),'low score without evidence')
        if rec['kind']=='provisional_low':check(st['score_is_provisional'],'non-provisional risk')
        if st['evidence_granularity']=='course_total':
            check(not any(nodes[k]['level']=='L3_Knowledge' for k in rec['review_node_ids']),'total inferred knowledge weakness')
        if rec['kind']=='not_started':check(st['learning_state']=='not_started','not-started claim')
        if rec['kind']=='missing_evidence':check(val is None and st['learning_state']!='not_started','missing evidence claim')

bundles={}
for row in manifest['recommendation_entries']:
    bundle=read(P/row['path']);validator.validate(bundle)
    snap=snapshots[bundle['basis_snapshot']['snapshot_id']]
    check(bundle['subject']==snap['subject'] and bundle['graph_ref']==snap['graph_ref'],'bundle object binding')
    check(bundle['basis_snapshot']['revision']==snap['revision'],'bundle basis revision')
    check(bundle['basis_profile_version']==profiles[bundle['subject']['id']]['profile_version'],'bundle profile revision')
    check(bundle['resource_catalog_version']==catalog['catalog_version'],'bundle resource catalog')
    check(len({r['recommendation_id'] for r in bundle['recommendations']})==len(bundle['recommendations'])==278,'recommendation identity')
    for r in bundle['recommendations']:recommendation_checks(r,snap)
    for role in ['teacher','student']:
        check({r['target_node_id'] for r in bundle['recommendations'] if r['audience']==role}==set(nodes)|{None},'role coverage')
    bundles[bundle['bundle_id']]=bundle

def validate_update(update):
    validator.validate(update)
    bundle=bundles[update['base_bundle_id']];snap=snapshots[bundle['basis_snapshot']['snapshot_id']]
    matches=[c for c in contexts if c['context_id']==update['context_id']]
    check(len(matches)==1,'unknown context')
    context=matches[0]
    check(update['subject']==context['subject'] and update['audience']==context['audience'],'context audience binding')
    check(update['subject']==snap['subject'],'wrong subject')
    check(update['graph_ref']==graph['graph_ref'],'stale graph')
    check(update['basis_snapshot']==bundle['basis_snapshot'],'stale snapshot')
    check(update['base_bundle_version']==bundle['version'],'stale recommendations')
    check(update['proposed_bundle_version']==bundle['version']+1,'non-sequential version')
    check(update['profile_version']==profiles[update['subject']['id']]['profile_version'],'stale profile')
    check(update['resource_catalog_version']==catalog['catalog_version'],'stale resource catalog')
    existing={r['recommendation_id']:r for r in bundle['recommendations']};seen=set()
    for op in update['operations']:
        rid=op['recommendation_id'];check(rid not in seen,'duplicate operation');seen.add(rid)
        if rid in existing:check(existing[rid]['audience']==update['audience'],'cross-role mutation')
        if op['op']=='remove':check(rid in existing,'unknown removal')
        else:
            r=op['recommendation'];check(r['recommendation_id']==rid and r['audience']==update['audience'],'operation audience/ID')
            if rid in existing:check(r['target_node_id']==existing[rid]['target_node_id'],'retargeted stable recommendation ID')
            check(r['origin']=='llm_candidate' and r['lifecycle']=='candidate','candidate lifecycle')
            recommendation_checks(r,snap)
            for field in ['basis_node_ids','review_node_ids','prepare_node_ids']:
                check(set(r[field])<=set(context['selected_results']),'node absent from supplied context')
            check(set(r['evidence_refs'])<={e['evidence_id'] for e in context['evidence']},'evidence absent from supplied context')
            check(set(r['resource_ids'])<={e['resource_id'] for e in context['resources']},'resource absent from supplied context')
        target=existing[rid]['target_node_id'] if op['op']=='remove' else op['recommendation']['target_node_id']
        check((target is None and context['task']['include_overview']) or target in context['task']['target_node_ids'],'outside requested node scope')
    return True

contexts=[]
for path in sorted((P/'examples').glob('llm-context-*.json')):
    c=read(path);validator.validate(c);contexts.append(c)
    snap=snapshots[c['basis_snapshot']['snapshot_id']]
    check(c['subject']==snap['subject'] and c['basis_snapshot']['revision']==snap['revision'],'context identity')
    check(c['graph_ref']==snap['graph_ref'] and c['profile_version']==profiles[c['subject']['id']]['profile_version'],'context revision')
    check('display_name' not in c and 'student_number' not in c,'unnecessary identity export')
    check(set(c['selected_results'])=={n['id'] for n in c['selected_nodes']},'selected result alignment')
    evidence_ids={e['evidence_id'] for e in c['evidence']};selected=set(c['selected_results'])
    for k,v in c['selected_results'].items():
        original=snap['node_results'][k]
        check(v['status']==original['status'] and v['progress_source']==original['progress_source'],'modified context facts')
        check(set(v['evidence_refs'])==set(original['evidence_refs'])&evidence_ids,'context evidence selection')
        check(v['omitted_evidence_count']==len(original['evidence_refs'])-len(v['evidence_refs']),'unlabelled evidence omission')
        check(v['omitted_input_count']==len(set(original['input_node_ids'])-selected),'unlabelled input omission')
    for n in c['selected_nodes']:check(n=={k:nodes[n['id']][k] for k in ['id','level','label','description']},'modified context graph')
    original_evidence={e['evidence_id']:e for e in snap['evidence']}
    for e in c['evidence']:check(e==original_evidence[e['evidence_id']],'modified context evidence')
    check({e for r in c['selected_results'].values() for e in r['evidence_refs']}<={e['evidence_id'] for e in c['evidence']},'incomplete context evidence')
    for r in c['current_recommendations']:check(r['audience']==c['audience'],'context role contamination')
    check(all(e['source'] in selected and e['target'] in selected and e in graph['edges'] for e in c['selected_edges']),'context graph closure')
    check(all(e['node_id'] in selected for e in c['evidence']),'recursive evidence spill')
    limits=c['selection']['limits']
    for field,limit in [('selected_nodes','max_nodes'),('selected_edges','max_edges'),('evidence','max_evidence'),('resources','max_resources')]:
        check(len(c[field])<=limits[limit],'context count budget')
    check(len(json.dumps(c,ensure_ascii=False))<=limits['max_characters'],'context character budget')
    if c['selection']['mode']=='node_neighborhood':
        expected={'C05'}
        for edge in graph['edges']:
            if edge['source']=='C05' or edge['target']=='C05':expected.update([edge['source'],edge['target']])
        check(selected==expected and 'C02' in selected and 'C04' not in selected,'true one-hop selection')
        check(not c['task']['include_overview'],'local request should not edit global overview')
    else:
        check(all(k in selected for k in nodes if nodes[k]['level']=='L1_Ability'),'overview lacks ability profile')
        check(c['task']['include_overview'] and not c['task']['target_node_ids'],'overview write scope')

candidate=read(P/'examples/recommendation-update-candidate.json');validate_update(candidate)
validate_update(read(P/'examples/recommendation-update-overview-candidate.json'))
negative=[]
def reject(label,mutate):
    value=copy.deepcopy(candidate);mutate(value)
    try:validate_update(value)
    except (AssertionError,KeyError,TypeError,ValidationError):
        # ValidationError and domain failures are expected rejection outcomes.
        negative.append(label);return
    raise AssertionError('accepted invalid update: '+label)
reject('wrong student',lambda x:x['subject'].update(id='DEMO002'))
reject('unknown context',lambda x:x.update(context_id='MISSING'))
reject('stale snapshot',lambda x:x['basis_snapshot'].update(revision=2))
reject('stale advice version',lambda x:x.update(base_bundle_version=99))
reject('stale profile',lambda x:x.update(profile_version=99))
reject('stale resource catalog',lambda x:x.update(resource_catalog_version=99))
reject('score overwrite prohibited',lambda x:x.update(node_results={'C05':{'score':100}}))
reject('unknown node',lambda x:x['operations'][0]['recommendation'].update(target_node_id='UNKNOWN'))
reject('foreign evidence',lambda x:x['operations'][0]['recommendation'].update(evidence_refs=['EV-DEMO002-foreign']))
reject('unknown resource',lambda x:x['operations'][0]['recommendation'].update(resource_ids=['MISSING']))
reject('cross-role update',lambda x:x.update(audience='student'))
reject('unknown removal',lambda x:x.update(operations=[{'op':'remove','recommendation_id':'MISSING'}]))
reject('active LLM output prohibited',lambda x:x['operations'][0]['recommendation'].update(lifecycle='active'))
reject('outside requested task scope',lambda x:x['operations'][0].update(recommendation_id='NEW-OUTSIDE',recommendation={**x['operations'][0]['recommendation'],'recommendation_id':'NEW-OUTSIDE','target_node_id':'C01'}))
reject('known node absent from context',lambda x:x['operations'][0]['recommendation'].update(basis_node_ids=['C05','C17']))
reject('same student evidence absent from context',lambda x:x['operations'][0]['recommendation'].update(
    basis_node_ids=['C05','C02'],evidence_refs=['EV-DEMO001-mixed_evidence-C02.K01']))
reject('known resource absent from context',lambda x:x['operations'][0]['recommendation'].update(resource_ids=['RES-C09']))

wire_schema=read(P/'contracts/recommendation-update.provider.schema.json')
Draft202012Validator.check_schema(wire_schema);wire=Draft202012Validator(wire_schema)
wire.validate(candidate);wire.validate(read(P/'examples/recommendation-update-overview-candidate.json'))
def wire_structure(value):
    if isinstance(value,dict):
        check(not set(value)&{'allOf','oneOf','not','if','then','else'},'unsupported wire composition')
        if value.get('type')=='object':
            check(value.get('additionalProperties') is False,'wire object must be closed')
            check(set(value['required'])==set(value['properties']),'wire fields must be required')
        for child in value.values():wire_structure(child)
    elif isinstance(value,list):
        for child in value:wire_structure(child)
wire_structure(wire_schema)
check(wire_schema.get('type')=='object' and 'anyOf' not in wire_schema,'wire root object')

report={'status':'passed','scope':'contracts/data only; frontend and LLM not executed',
    'counts':manifest['counts'],'schema_record_count':4+len(snapshots)+len(bundles)+len(contexts)+2,
    'checks':['schema types and date formats','public vs subject separation','stable node IDs','roster references',
    'complete snapshot coverage','independent learning progress','weighted score/coverage consistency',
    'all 40 students vs legacy class means','course-total fallback','dual-role advice/evidence references',
    'local resources exist','LLM context binding','task-specific one-hop and overview contexts',
    'context evidence omissions and count budgets','provider output schema offline shape',
    'candidate-only update protocol','baseline application files unchanged'],
    'negative_update_cases_rejected':negative,'max_numeric_tolerance':.000002,
    'context_counts':[{ 'file':p.name,'mode':read(p)['selection']['mode'],
        'nodes':len(read(p)['selected_nodes']),'edges':len(read(p)['selected_edges']),'evidence':len(read(p)['evidence'])}
        for p in sorted((P/'examples').glob('llm-context-*.json'))],
    'provider_schema_check':'offline subset and sample checks passed; API acceptance not tested'}
(P/'validation-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
overview=['# 个性化图谱数据审查概览','',
    '本包仅用于数据契约与方案审查，现有应用仍读取旧版JSON。','',
    '公共图谱138节点/285条边；40名模拟学生；120份学生快照、3份班级快照。DEMO001–DEMO003具备两个角色、三个场景的完整建议。','',
    '每个建议包包含教师和学生各139条建议（总体1条+节点138条），共2502条预置建议；没有调用LLM。','',
    '| 演示身份 | 姓名 | 模拟学号 | 阶段C05得分 | 学习进度 | 评价覆盖率 |','|---|---|---|---:|---:|---:|']
for sid in manifest['demo_student_ids']:
    p=profiles[sid];st=snapshots[f'student-{sid}-mixed_evidence']['node_results']['C05']['status']
    overview.append(f"| {sid} | {p['display_name']} | {p['student_number']} | {st['achievement_rate']:.2f} | {st['learning_progress']:.0%} | {st['coverage_rate']:.0%} |")
overview += ['', '班级C05仍为49.65（显示精度2位）；个人值直接来自自己的已评价知识点，不能复制班均分。', '',
    '阶段场景：C05学习进度60%，评价覆盖50%；C05.K04学习中但未评价；C05.K05/K06未开始；C07/C08/C10只有课程总评；六至八学期课程尚未开始。','',
    '## 数据一致性','', '全部40人的各层均分与原班级预置值在0.000002容差内一致。旧图谱、旧场景JSON与前端文件哈希未改变。','',
    '## 文件入口','', '- manifest.json：按对象/场景定位快照和建议；仅前三名学生建议齐全，后续演示选择器默认启用这三人。',
    '- data/graph.json：唯一公共图谱；data/students.json：模拟名册与学习背景。',
    '- data/snapshots/student/DEMO001/mixed_evidence.json：重点审查的个人快照。',
    '- data/recommendations/DEMO001/mixed_evidence.json：教师/学生的总体与节点建议。',
    '- examples/：教师/学生局部诊断、学生总体画像三份LLM输入，以及两个未应用的更新候选。',
    '- resources/：18份实际存在的本地复习任务单，不是虚构外链。',
    '- contracts/contract.schema.json：8类记录与共享字段定义。','',
    '建议候选只通过校验，未写回任何现有建议包、图谱、侧栏或页面。','']
(P/'数据审查概览.md').write_text('\n'.join(overview),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))

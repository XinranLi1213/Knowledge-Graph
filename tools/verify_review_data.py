"""Offline semantic checks; no browser or UI implementation."""
from pathlib import Path
from collections import Counter, defaultdict
import json
from jsonschema import Draft202012Validator

BASE=Path(__file__).resolve().parents[1]
DATA=BASE/'review'/'data'
def read(name): return json.loads((DATA/name).read_text(encoding='utf-8'))
def require(condition,message):
    if not condition: raise AssertionError(message)

schema=read('graph.schema.json')
Draft202012Validator.check_schema(schema)
validator=Draft202012Validator(schema)
reports=[]
graphs=[]
for scenario in ['knowledge_full','mixed_evidence','course_totals_only']:
    graph=read(scenario+'.json'); graphs.append(graph)
    validator.validate(graph)
    nodes={n['id']:n for n in graph['nodes']}
    require(len(nodes)==len(graph['nodes'])==138,'duplicate/missing node')
    require(len({e['id'] for e in graph['edges']})==len(graph['edges']),'duplicate edge ID')
    sources={s['id'] for s in graph['sources']}
    incoming=defaultdict(list); seen=set()
    dag=defaultdict(list)
    for e in graph['edges']:
        s,t=e['source'],e['target']; typ=e['relation_type']
        require(s in nodes and t in nodes and s!=t,'invalid endpoint')
        key=(typ,s,t) if e['directed'] else (typ,*sorted([s,t]))
        require(key not in seen,'duplicate semantic edge'); seen.add(key)
        require(set(e['source_refs'])<=sources,'invalid source')
        sl,tl=nodes[s]['level'],nodes[t]['level']
        if typ=='supports': require((sl,tl)==('L2_Course','L1_Ability'),'supports direction')
        if typ=='belongs_to':
            require((sl,tl)==('L3_Knowledge','L2_Course'),'belongs_to direction')
            require(nodes[s]['course_id']==t,'course mismatch')
        if typ in ('prerequisite','similar','parallel'): require(sl==tl,'peer levels')
        require(e['directed']==(typ not in ('similar','parallel')),'arrow type')
        if typ in ('supports','belongs_to'):
            require(e['relation_category']=='hierarchical' and e['aggregation_weight'] is not None,'aggregation type')
            incoming[t].append(e)
        else: require(e['aggregation_weight'] is None,'peer must not aggregate')
        if typ=='prerequisite': dag[s].append(t)
    visited=set(); stack=set()
    def walk(n):
        require(n not in stack,'prerequisite cycle')
        if n in visited: return
        stack.add(n)
        for t in dag[n]: walk(t)
        stack.remove(n); visited.add(n)
    for n in nodes: walk(n)
    for n in nodes.values():
        require(set(n['source_refs'])<=sources,'invalid node source')
        st=n['status']; val=st['achievement_rate']; cov=st['coverage_rate']
        expected='grey' if val is None or cov<.8 else 'green' if val>=80 else 'yellow' if val>=60 else 'red'
        require(st['health_color']==expected,'color mismatch '+n['id'])
        require(st['score_is_provisional']==(0<cov<1),'provisional mismatch')
        require(st['sample_count']<=st['expected_count']==40,'sample size')
        require((st['grey_reason'] is not None)==(expected=='grey'),'grey reason')
        if val is None: require(cov==0,'null with coverage')
        if n['level']=='L3_Knowledge':
            require(sum(e['source']==n['id'] and e['relation_type']=='belongs_to' for e in graph['edges'])==1,'knowledge membership')
        else:
            ins=incoming[n['id']]
            require(ins and abs(sum(e['aggregation_weight'] for e in ins)-1)<1e-9,'weight sum '+n['id'])
            if st['aggregation_basis']=='weighted_inputs':
                c=sum(e['aggregation_weight']*nodes[e['source']]['status']['coverage_rate'] for e in ins)
                require(abs(c-cov)<=2e-6,'coverage mismatch')
                if c:
                    s=sum(e['aggregation_weight']*nodes[e['source']]['status']['coverage_rate']*(nodes[e['source']]['status']['achievement_rate'] or 0) for e in ins)/c
                    require(val is not None and abs(s-val)<=2e-6,'score mismatch '+n['id'])
                else: require(val is None,'empty aggregate must be null')
        if n['level']=='L2_Course':
            covered=[]
            for obj in n['course_objectives']:
                require(set(obj['ability_ids'])<=set(nodes),'objective ability references')
                for k in obj['knowledge_ids']:
                    require(nodes[k]['course_id']==n['id'],'objective knowledge scope'); covered.append(k)
            require(len(covered)==len(set(covered))==6,'objective knowledge coverage')
    if scenario=='course_totals_only':
        require(all(n['status']['achievement_rate'] is None and n['status']['health_color']=='grey' for n in nodes.values() if n['level']=='L3_Knowledge'),'fabricated knowledge')
        require(all(n['status']['achievement_rate'] is not None for n in nodes.values() if n['level']!='L3_Knowledge'),'missing course fallback')
    if scenario=='mixed_evidence':
        require(nodes['C05']['status']['coverage_rate']==.5,'partial scenario')
        require(nodes['C05']['status']['grey_reason']=='insufficient_coverage','partial label')
        require(nodes['C14']['status']['learning_state']=='not_started','planned scenario')
        require(nodes['C08']['status']['evidence_granularity']=='course_total','course total scenario')
        require(nodes['C08.K01']['status']['achievement_rate'] is None,'reverse inference')
    require(graph['summary']['health_counts']==dict(Counter(n['status']['health_color'] for n in nodes.values())),'summary mismatch')
    reports.append({'scenario':scenario,'schema':'passed','semantic_checks':'passed','node_count':len(nodes),
                    'edge_count':len(graph['edges']),'max_score_error_tolerance':.000002,
                    'health_counts':graph['summary']['health_counts']})

for graph in graphs[1:]:
    require([n['id'] for n in graph['nodes']]==[n['id'] for n in graphs[0]['nodes']],'unstable node IDs')
    require(graph['edges']==graphs[0]['edges'],'unstable edges')

fixture=read('student_knowledge_fixture.json')
records=defaultdict(list); keys=set()
for r in fixture['records']:
    key=(r['student_id'],r['node_id']); require(key not in keys,'duplicate student observation'); keys.add(key)
    records[r['node_id']].append(r['score'])
require(len(fixture['students'])==40 and len(fixture['records'])==4320,'student fixture count')
for n in graphs[0]['nodes']:
    if n['level']=='L3_Knowledge':
        values=records[n['id']]
        require(len(values)==40 and abs(sum(values)/40-n['status']['achievement_rate'])<=2e-6,'class mean mismatch')

result={'status':'passed','scope':'offline data review only; UI not implemented or tested',
 'checks':['JSON Schema','unique IDs','valid endpoints and provenance','edge direction and category',
           'prerequisite DAG','aggregation weights','weighted scores and coverage','health labels',
           'objective links','student means','course-total fallback','scenario structural identity'],
 'scenarios':reports,'synthetic_students':40,'synthetic_student_observations':4320}
(DATA/'validation_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

lines=['# 预置数据审查概览','', '来源：2024级电子信息工程培养方案截图；知识点、教学关系与成绩为模拟。', '',
       '规模：12个能力、18门课程、108个知识/技能、54个课程目标、6个课程群、'+str(len(graphs[0]['edges']))+'条边。', '',
       '状态：离线数据校验通过；尚未实现或验证界面。', '',
       '| 场景 | 绿色 | 黄色 | 红色 | 灰色 |','|---|---:|---:|---:|---:|']
for report in reports:
    h=report['health_counts'];lines.append('| '+report['scenario']+' | '+' | '.join(str(h.get(c,0)) for c in ['green','yellow','red','grey'])+' |')
lines += ['', '下表单元格为“预设得分 / 评价覆盖率”；—表示null。课程总分场景知识点全部为空。', '',
          '| 课程 | 来源学分 | 全量知识点 | 混合证据 | 仅课程总分 |','|---|---:|---|---|---|']
for n in graphs[0]['nodes']:
    if n['level']!='L2_Course': continue
    values=[]
    for graph in graphs:
        st=next(x for x in graph['nodes'] if x['id']==n['id'])['status']
        score='—' if st['achievement_rate'] is None else f"{st['achievement_rate']:.2f}"
        values.append(f"{score} / {st['coverage_rate']:.0%}")
    credit=str(n['credits'])+('（模拟）' if n['id']=='C18' else '')
    lines.append('| '+n['label']+' | '+credit+' | '+' | '.join(values)+' |')
lines += ['', '## 能力预置结果', '', '| 能力 | 全量知识点 | 混合证据 | 仅课程总分 |','|---|---|---|---|']
for n in graphs[0]['nodes']:
    if n['level']!='L1_Ability': continue
    values=[]
    for graph in graphs:
        st=next(x for x in graph['nodes'] if x['id']==n['id'])['status']
        score='—' if st['achievement_rate'] is None else f"{st['achievement_rate']:.2f}"
        values.append(f"{score} / {st['coverage_rate']:.0%}")
    lines.append('| '+n['label']+' | '+' | '.join(values)+' |')
(BASE/'review'/'数据概览.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))

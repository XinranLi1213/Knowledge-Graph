"""Offline review fixtures only. Never import this module into the UI runtime."""
from pathlib import Path
from collections import Counter
import copy, hashlib, json, random

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'review' / 'data'
OUT.mkdir(parents=True, exist_ok=True)
SRC = Path(r'C:\Users\27725\Desktop\培养方案')

def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

sources = []
for i, path in enumerate(sorted(SRC.glob('*.png')), 1):
    sources.append({'id': f'S{i:02}', 'filename': path.name, 'local_path': str(path),
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                    'source_program': '电子信息工程', 'source_cohort': '2024',
                    'extraction_method': '人工逐图阅读', 'document_role': 'reference_only'})
sources.append({'id': 'SIM', 'title': '电子信息工程MVP合成教学数据',
                'kind': 'simulation', 'note': '知识点、目标、映射、关系、支撑权重、班级和全部成绩为模拟，不代表学校正式结论。'})

# Name, official course code, credits, semester, source, group, six simulated knowledge/skill points.
courses = [
('电路分析','242019',4,2,'S06','G1','电路变量与参考方向|基尔霍夫定律|节点电压法|戴维南等效|一阶电路暂态|交流电路测量'),
('模拟电子技术','243060',4,3,'S02','G1','半导体器件模型|晶体管偏置|小信号放大|负反馈|集成运算放大|放大器调试'),
('数字电子技术','242074',3.5,3,'S05','G1','逻辑代数|组合逻辑|触发器|时序逻辑|计数器|数字电路验证'),
('信号与系统','242015',4,4,'S04','G2','信号分类|线性时不变系统|卷积积分|傅里叶变换|采样定理|系统响应仿真'),
('通信电子线路','243115',3.5,5,'S02','G3','LC谐振|高频小信号放大|功率放大|振荡器|调幅与检波|混频电路调试'),
('数字信号处理','243116',3.5,5,'S02','G2','离散时间信号|Z变换|离散傅里叶变换|快速傅里叶变换|数字滤波器|滤波器实现'),
('电磁场与电磁波','243114',3.5,4,'S05','G3','矢量场|静电场|麦克斯韦方程组|平面电磁波|传输线|驻波测量'),
('通信原理','242020',4,5,'S02','G2','随机过程与噪声|模拟调制|脉冲编码调制|数字调制|误码率|通信链路仿真'),
('C语言程序设计','241003',3,2,'S02','G4','数据类型|程序控制|数组|函数|指针|通信数据处理编程'),
('微机原理与接口技术','244128',2,4,'S02','G4','处理器结构|寻址方式|中断机制|定时器|串行接口|接口联调'),
('嵌入式系统原理与应用','243219',3,5,'S04','G4','嵌入式体系结构|外设驱动|任务调度|数据采集|设备通信协议|嵌入式通信实验'),
('计算机网络','244147',2,6,'S08','G5','分层体系结构|以太网|IP编址|路由原理|传输层协议|网络抓包分析'),
('微波工程基础','243120',2,6,'S07','G3','微波网络参数|阻抗匹配|微带线|微波谐振器|微波器件|网络分析仪测量'),
('射频电路设计','244153',1,7,'S07','G3','射频指标预算|低噪声放大器|射频滤波器|锁相环|射频布局|射频链路联调'),
('电子系统设计','245048',1,6,'S02','G6','需求分解|系统方案比较|软硬件协同|测试方案|团队接口协作|设计文档与汇报'),
('电子系统工程实践','245036',2,7,'S03','G6','工程需求调研|原型集成|可靠性验证|工程伦理与安全|环境影响评估|工程项目复盘'),
('毕业设计','245004',16,8,'S05','G6','文献检索|研究问题定义|研究方法设计|实验数据分析|论文撰写|成果答辩'),
('工程设计与管理',None,2,7,'S02','G6','项目范围|工作分解|进度管理|成本估算|风险管理|技术经济决策'),
]
groups = [
 {'id':'G1','name':'电路与电子基础','description':'电路建模、模拟及数字电路基础'},
 {'id':'G2','name':'信号处理与通信理论','description':'信号表示、数字处理及通信性能分析'},
 {'id':'G3','name':'电磁场与射频技术','description':'电磁传播、通信电子线路和射频链路'},
 {'id':'G4','name':'编程与嵌入式平台','description':'程序设计、接口控制及嵌入式实现'},
 {'id':'G5','name':'网络与互联','description':'网络协议和通信系统互联'},
 {'id':'G6','name':'综合设计与工程实践','description':'系统设计、研究、职业素养和项目管理'},
]
abilities = [
 ('工程知识','运用数学与专业基础建立通信电路、信号和系统模型。',[(1,.25),(2,.15),(3,.15),(4,.25),(7,.2)]),
 ('问题分析','识别通信链路问题并用模型及证据分析关键因素。',[(4,.25),(5,.2),(6,.25),(8,.3)]),
 ('设计/开发解决方案','围绕通信需求提出并实现可验证的系统方案。',[(5,.15),(8,.2),(11,.2),(14,.2),(15,.25)]),
 ('复杂工程问题研究能力','通过文献、实验和数据分析形成通信工程研究结论。',[(6,.2),(8,.2),(16,.2),(17,.4)]),
 ('选择和使用现代工具能力','选择仿真、编程与测量工具并说明适用条件。',[(6,.2),(9,.2),(10,.15),(11,.2),(13,.25)]),
 ('工程与社会','分析通信系统对公共安全、隐私及社会的影响。',[(12,.25),(15,.25),(16,.5)]),
 ('环境和可持续发展','分析通信工程的能耗、资源和环境影响。',[(14,.2),(16,.5),(18,.3)]),
 ('职业规范','遵守工程安全、学术诚信及专业责任要求。',[(15,.2),(16,.4),(17,.4)]),
 ('个人和团队','在系统设计与联调中承担角色并协调接口。',[(11,.2),(15,.4),(16,.4)]),
 ('沟通与交流','用技术文档、实验报告和汇报表达工程结论。',[(12,.15),(15,.3),(17,.55)]),
 ('项目管理能力','在工程任务中应用进度、成本与风险管理方法。',[(15,.2),(16,.25),(18,.55)]),
 ('自主学习与终身学习','通过检索、比较和复盘掌握新通信技术。',[(11,.15),(12,.15),(17,.5),(18,.2)]),
]
nodes, edges = [], []
def add_edge(s,t,typ,w=None,**extra):
    edge={'id':f'E{len(edges)+1:04}', 'source':s,'target':t,'relation_type':typ,
          'relation_category':'hierarchical' if typ in ('supports','belongs_to','contains') else 'peer',
          'directed':typ not in ('similar','parallel'), 'aggregation_weight':w,
          'source_refs':['SIM'],'provenance':'simulated','review_status':'demo_unreviewed',**extra}
    edges.append(edge)

for i,(name,desc,supports) in enumerate(abilities,1):
    aid=f'A{i:02}'
    nodes.append({'id':aid,'level':'L1_Ability','label':name,'display_weight':1,
      'requirement_code':str(i),'indicator_code':f'{i}.demo.1','indicator_description':desc,
      'source_refs':['S01','SIM'],'provenance':{'label':'source_transcribed','indicator':'simulated'},
      'sidebar_info':{'description':desc+' 本节点为单一模拟指标点，非学校完整指标点体系。',
                      'remediation_advice':['教师核对支撑课程中的薄弱评价环节，结合任务量规组织复测。']}})
    for ci,w in supports: add_edge(f'C{ci:02}',aid,'supports',w)

kw=[.15,.15,.2,.2,.15,.15]
for ci,(name,code,credit,semester,src,gid,ktext) in enumerate(courses,1):
    cid=f'C{ci:02}'
    klabels=ktext.split('|')
    obj=[]
    linked=[f'A{a:02}' for a,(_,_,sup) in enumerate(abilities,1) if any(x==ci for x,_ in sup)]
    for oi,(title,desc) in enumerate([
      ('原理理解',f'解释{name}的基本概念、模型和适用条件。'),
      ('分析与设计',f'使用{name}的方法分析问题并比较解决方案。'),
      ('实践与验证',f'完成{name}相关实现、测试与结果表达。')],1):
        obj.append({'id':f'{cid}.O{oi}','title':title,'description':desc,
                    'knowledge_ids':[f'{cid}.K{j:02}' for j in range((oi-1)*2+1,oi*2+1)],
                    'ability_ids':linked,'provenance':'simulated','participates_in_score_aggregation':False})
    nodes.append({'id':cid,'level':'L2_Course','label':name,'display_weight':credit,
      'credits':credit,'source_course_code':code,'semester':semester,
      'course_group_ids':[gid], 'course_nature':'选修' if ci in (13,14) else '必修',
      'source_refs':[src,'SIM'],'provenance':{'label':'source_transcribed',
       'credits':'simulated' if ci==18 else 'source_transcribed',
       'semester':'simulated' if ci==18 else 'source_transcribed','course_groups':'simulated','objectives':'simulated'},
      'course_objectives':obj,
      'sidebar_info':{'description':f'{name}用于电子信息工程演示课程群；目标与知识点为模拟。',
                      'remediation_advice':[f'教师检查{name}的薄弱知识点，安排分层练习与课堂复核。']}})
    for ki,(label,w) in enumerate(zip(klabels,kw),1):
      kid=f'{cid}.K{ki:02}'
      nodes.append({'id':kid,'level':'L3_Knowledge','label':label,
        'knowledge_kind':'experimental_skill' if ki==6 or (ci>=15 and ki>=4) else 'concept',
        'display_weight':w,'course_id':cid,'course_group_ids':[gid],
        'concept_id':kid,'source_refs':['SIM'],'provenance':{'all':'simulated'},
        'sidebar_info':{'description':f'在《{name}》语境下学习和评价“{label}”。',
          'remediation_advice':[f'教师使用一道概念辨析题和一个应用任务复核“{label}”。',
                               '若存在先修缺口，先补测对应基础节点，再安排后继任务。']}})
      add_edge(kid,cid,'belongs_to',w)
      if ki>1: add_edge(f'{cid}.K{ki-1:02}',kid,'prerequisite')

for s,t in [(1,2),(1,4),(2,5),(3,10),(4,6),(4,8),(5,14),(7,13),(9,10),(9,11),(10,11),(11,15),(12,15),(13,14),(15,16),(16,17),(18,17)]:
    add_edge(f'C{s:02}',f'C{t:02}','prerequisite')
for s,t in [('C01.K04','C02.K03'),('C04.K04','C06.K03'),('C04.K05','C08.K03'),('C05.K01','C13.K04'),('C07.K05','C13.K02'),('C06.K05','C08.K06'),('C09.K05','C11.K02'),('C10.K05','C11.K05'),('C08.K04','C12.K01'),('C13.K02','C14.K03')]:
    add_edge(s,t,'prerequisite')
for s,t,concept in [('C04.K04','C06.K03','fourier_methods'),('C05.K01','C13.K04','resonance'),('C05.K05','C08.K02','amplitude_modulation'),('C10.K05','C11.K05','device_communication'),('C15.K06','C17.K05','technical_writing')]:
    # Related concepts remain separate context-specific observations, not automatic equivalence.
    add_edge(s,t,'similar',similarity_score=.82,concept_family=concept)
for s,t in [('C02','C03'),('C06','C08'),('C15.K04','C15.K05'),('C18.K03','C18.K04')]:
    add_edge(s,t,'parallel')
for s,t in [('A01','A02'),('A02','A03')]:
    add_edge(s,t,'prerequisite')
for s,t in [('A03','A04'),('A06','A08'),('A09','A10'),('A11','A12')]:
    add_edge(s,t,'parallel')

index={n['id']:n for n in nodes}
incoming={n['id']:[e for e in edges if e['target']==n['id'] and e['aggregation_weight'] is not None] for n in nodes}
targets=[84,73,83,69,55,53,72,63,86,79,77,59,75,54,84,78,81,74]
rng=random.Random(20261029)
students=[f'DEMO{i:03}' for i in range(1,41)]
student_records=[]
full_scores={}
for ci in range(1,19):
  for ki in range(1,7):
    kid=f'C{ci:02}.K{ki:02}'
    target=targets[ci-1]+[-5,3,-9,5,0,4][ki-1]
    values=[round(max(0,min(100,target+rng.gauss(0,9))),2) for _ in students]
    full_scores[kid]=round(sum(values)/len(values),6)
    for sid,score in zip(students,values):
      student_records.append({'student_id':sid,'node_id':kid,'score':score,'source':'simulated_assessment'})

def color(score,coverage):
    return 'grey' if score is None or coverage<.8 else 'green' if score>=80 else 'yellow' if score>=60 else 'red'

base={
 'schema_version':'1.1.0','metadata':{'graph_id':'communication-engineering-demo','graph_version':1,
 'program_name':'电子信息工程（培养方案图谱演示）','source_program_name':'电子信息工程',
 'source_title':'2024级电子信息工程人才培养方案','is_official_communication_plan':False,
 'data_classification':'synthetic_demo','class_id':'COMM-DEMO-40','class_name':'电子信息工程演示班',
 'class_size':40,'as_of':'2026-10-29','score_mode':'precomputed_node_values',
 'requires_runtime_score_calculation':False,
 'notice':'培养方案图谱演示；知识点、关系及学情为模拟。'},
 'program_plan':{'name':'电子信息工程演示培养方案','degree':'工学学士（演示沿用）','duration_years':4,
   'source_total_credits':173,'source_total_credits_applies_to':'电子信息工程原方案，不是演示课程学分合计',
   'training_goals':[
    {'id':'P1','text':'运用数学、电子与通信知识分析和设计通信系统。','ability_ids':['A01','A02','A03','A04','A05']},
    {'id':'P2','text':'综合考虑安全、伦理和可持续发展开展工程实践。','ability_ids':['A06','A07','A08']},
    {'id':'P3','text':'承担团队职责，开展技术沟通和项目协作。','ability_ids':['A09','A10','A11']},
    {'id':'P4','text':'保持自主学习，持续适应通信技术发展。','ability_ids':['A12']}],
   'goals_provenance':'simulated_adaptation','scope':'18门演示课程，不是全量培养方案',
   'ability_scope':'12项毕业要求各设一个模拟可评价指标，不冒充正式指标点'},
 'policy':{'green_min':80,'yellow_min':60,'min_coverage':.8,'scale':[0,100],
  'thresholds_provenance':'demo_policy','score_precision':6,
  'coverage_definition':'按支撑权重递归累积的有效评价覆盖率，不是参评学生比例',
  'display_size_comparison':'within_level_only','partial_score_label':'已评价部分得分',
  'course_total_fallback':'use course total directly, never infer knowledge scores',
  'aggregation_types':['supports','belongs_to']},
 'sources':sources,'course_groups':groups,
 'nodes':nodes,'edges':edges}

audit=[]
for scenario in ['knowledge_full','mixed_evidence','course_totals_only']:
  data=copy.deepcopy(base)
  data['metadata']['scenario_id']=scenario
  data['metadata']['scenario_description']={
    'knowledge_full':'全培养周期教学回放：知识点证据齐全，成绩来自40名合成学生。',
    'mixed_evidence':'第五学期阶段演示：知识点、课程总分、部分证据和未开课并存。',
    'course_totals_only':'全培养周期教学回放：只有课程总分，不生成任何知识点成绩。'}[scenario]
  idx={n['id']:n for n in data['nodes']}
  for n in data['nodes']:
    score=None; coverage=0.; evidence='none'; state='completed'; reason='no_evidence'; sample=0
    if n['level']=='L3_Knowledge':
      ci=int(n['course_id'][1:]); ki=int(n['id'][-2:])
      planned=scenario=='mixed_evidence' and courses[ci-1][3]>5
      missing=scenario=='course_totals_only' or (scenario=='mixed_evidence' and (ci in (7,8,10) or (ci==5 and ki>3)))
      if planned: state='not_started'; reason='not_started'
      elif not missing:
        score=full_scores[n['id']]; coverage=1.; evidence='knowledge_assessment'; reason=None; sample=40
      elif scenario=='mixed_evidence' and ci==5: reason='no_evidence'; state='in_progress'
    n['status']={'achievement_rate':score,'health_color':color(score,coverage),
      'coverage_rate':coverage,'learning_state':state,'grey_reason':reason,
      'evidence_granularity':evidence,'sample_count':sample,'expected_count':40,
      'score_is_provisional':0<coverage<1,'score_provenance':'simulated_precomputed',
      'aggregation_basis':'knowledge_assessment' if score is not None else 'none'}
  for level in ['L2_Course','L1_Ability']:
    for n in data['nodes']:
      if n['level']!=level: continue
      cid=n['id']; direct_total=level=='L2_Course' and (scenario=='course_totals_only' or (scenario=='mixed_evidence' and cid in ('C07','C08','C10')))
      planned=level=='L2_Course' and scenario=='mixed_evidence' and n['semester']>5
      if planned:
        score=None; cov=0.; gran='none'; basis='none'; state='not_started'; reason='not_started'
      elif direct_total:
        score=round(targets[int(cid[1:])-1]+1.25,6); cov=1.; gran='course_total'; basis='course_total'; state='completed'; reason=None
      else:
        ins=incoming[cid]
        cov=round(sum(e['aggregation_weight']*idx[e['source']]['status']['coverage_rate'] for e in ins),6)
        score=round(sum(e['aggregation_weight']*idx[e['source']]['status']['coverage_rate']*(idx[e['source']]['status']['achievement_rate'] or 0) for e in ins)/cov,6) if cov else None
        gran='knowledge_aggregate' if level=='L2_Course' else 'course_aggregate'
        basis='weighted_inputs'; state='completed' if cov==1 else 'in_progress'
        reason=None if cov>=.8 else 'insufficient_coverage' if cov else 'no_evidence'
      n['status'].update(achievement_rate=score,coverage_rate=cov,health_color=color(score,cov),
          learning_state=state,grey_reason=reason,evidence_granularity=gran,aggregation_basis=basis,
          sample_count=40 if score is not None else 0,score_is_provisional=0<cov<1)
  for n in data['nodes']:
    st=n['status']; info=n['sidebar_info']
    # Ability aggregate is an attainment estimate, not a raw exam score.
    info['average_score']=st['achievement_rate'] if n['level']!='L1_Ability' else None
    info['assessment_sources']=[] if st['achievement_rate'] is None else [{
      'id':f"{scenario}:{n['id']}",'title':{'L3_Knowledge':'模拟知识点测评班均分','L2_Course':'模拟课程评价','L1_Ability':'模拟课程支撑证据'}[n['level']],
      'kind':st['evidence_granularity'],'is_simulated':True,'sample_count':40}]
    if st['evidence_granularity']=='course_total':
      info['remediation_advice']=['教师核对课程总分分布，并补充知识点评价证据；当前不能定位具体薄弱知识点。']
    elif st['achievement_rate'] is None:
      info['remediation_advice']=['尚未开始教学，暂不作薄弱判断。' if st['learning_state']=='not_started' else '当前缺少细粒度评价证据，建议教师安排诊断性测评。']
    info['diagnosis_scope']='teacher_class_only'
  data['summary']={'nodes_by_level':dict(Counter(n['level'] for n in data['nodes'])),
    'edges_by_type':dict(Counter(e['relation_type'] for e in data['edges'])),
    'health_counts':dict(Counter(n['status']['health_color'] for n in data['nodes'])),
    'course_evidence_counts':dict(Counter(n['status']['evidence_granularity'] for n in data['nodes'] if n['level']=='L2_Course'))}
  save(f'{scenario}.json',data)
  for n in data['nodes']:
    if n['level']!='L3_Knowledge':
      audit.append({'scenario':scenario,'node_id':n['id'],'label':n['label'],
        'score':n['status']['achievement_rate'],'coverage':n['status']['coverage_rate'],
        'basis':n['status']['aggregation_basis'],
        'inputs':[{'node_id':e['source'],'weight':e['aggregation_weight'],
          'score':idx[e['source']]['status']['achievement_rate'],
          'coverage':idx[e['source']]['status']['coverage_rate']} for e in incoming[n['id']]] if n['status']['aggregation_basis']=='weighted_inputs' else []})
save('student_knowledge_fixture.json',{'fixture_only':True,'runtime_required':False,
 'graph_id':base['metadata']['graph_id'],'graph_version':1,'scenario_id':'knowledge_full',
 'students':students,'records':student_records,'note':'仅用于核验班均预设值；本次前端不加载或聚合此文件，无真实学生信息。'})
save('aggregation_audit.json',{'runtime_required':False,'rows':audit})
save('source_register.json',{'sources':sources,'source_confirmation':'全部截图为2024级电子信息工程培养方案。',
 'transcription_scope':'转录12项要求名称与所选18门课程的可见字段；并未转录全部课程。',
 'simulated_fields':['通信工程培养目标改写','每项要求的具体指标描述','课程群','课程目标','知识点与技能','所有边','所有权重','所有学情','第18门课程学分及学期'],
 'course18_note':'截图S02实践环节列有工程设计与管理，但未见课程表代码/学分/学期；这些字段为模拟，课程代码保持null。'})
score_schema={'type':['number','null'],'minimum':0,'maximum':100}
schema={
 '$schema':'https://json-schema.org/draft/2020-12/schema',
 'title':'电子信息工程预置图谱展示契约1.1.0','type':'object',
 'required':['schema_version','metadata','program_plan','policy','sources','course_groups','nodes','edges','summary'],
 'properties':{
  'schema_version':{'const':'1.1.0'},
  'metadata':{'type':'object','required':['graph_id','graph_version','program_name','source_program_name','scenario_id','class_size','score_mode','requires_runtime_score_calculation'],
    'properties':{'graph_version':{'type':'integer','minimum':1},'class_size':{'type':'integer','minimum':1},
      'score_mode':{'const':'precomputed_node_values'},'requires_runtime_score_calculation':{'const':False},
      'scenario_id':{'enum':['knowledge_full','mixed_evidence','course_totals_only']}}},
  'program_plan':{'type':'object','required':['name','training_goals','scope']},
  'policy':{'type':'object','required':['green_min','yellow_min','min_coverage'],
    'properties':{'green_min':{'type':'number','minimum':0,'maximum':100},'yellow_min':{'type':'number','minimum':0,'maximum':100},'min_coverage':{'type':'number','minimum':0,'maximum':1}}},
  'sources':{'type':'array','minItems':1,'items':{'type':'object','required':['id'],'properties':{'id':{'type':'string','minLength':1}}}},
  'course_groups':{'type':'array','items':{'type':'object','required':['id','name']}},
  'nodes':{'type':'array','minItems':1,'items':{'$ref':'#/$defs/node'}},
  'edges':{'type':'array','items':{'$ref':'#/$defs/edge'}},'summary':{'type':'object'}},
 '$defs':{
  'refs':{'type':'array','minItems':1,'uniqueItems':True,'items':{'type':'string'}},
  'status':{'type':'object','additionalProperties':False,
    'required':['achievement_rate','health_color','coverage_rate','learning_state','grey_reason','evidence_granularity','sample_count','expected_count','score_is_provisional','score_provenance','aggregation_basis'],
    'properties':{'achievement_rate':score_schema,'health_color':{'enum':['green','yellow','red','grey']},
     'coverage_rate':{'type':'number','minimum':0,'maximum':1},
     'learning_state':{'enum':['not_started','in_progress','completed']},
     'grey_reason':{'enum':[None,'not_started','no_evidence','insufficient_coverage']},
     'evidence_granularity':{'enum':['none','knowledge_assessment','knowledge_aggregate','course_total','course_aggregate']},
     'sample_count':{'type':'integer','minimum':0},'expected_count':{'type':'integer','minimum':1},
     'score_is_provisional':{'type':'boolean'},'score_provenance':{'const':'simulated_precomputed'},
     'aggregation_basis':{'enum':['none','knowledge_assessment','weighted_inputs','course_total']}}},
  'node':{'type':'object','required':['id','label','level','display_weight','source_refs','provenance','status','sidebar_info'],
    'properties':{'id':{'type':'string','minLength':1},'label':{'type':'string','minLength':1},
     'level':{'enum':['L1_Ability','L2_Course','L3_Knowledge']},'display_weight':{'type':'number','exclusiveMinimum':0},
     'source_refs':{'$ref':'#/$defs/refs'},'provenance':{'type':'object'},'status':{'$ref':'#/$defs/status'},
     'sidebar_info':{'type':'object','required':['description','assessment_sources','remediation_advice','average_score','diagnosis_scope'],
       'properties':{'description':{'type':'string'},'assessment_sources':{'type':'array','items':{'type':'object','required':['id','title','kind','is_simulated','sample_count']}},
        'remediation_advice':{'type':'array','items':{'type':'string'}},'average_score':score_schema,'diagnosis_scope':{'const':'teacher_class_only'}}},
     'credits':{'type':'number','exclusiveMinimum':0},'semester':{'type':'integer','minimum':1,'maximum':8},
     'course_group_ids':{'type':'array','uniqueItems':True,'items':{'type':'string'}},
     'course_objectives':{'type':'array','items':{'type':'object','required':['id','title','description','knowledge_ids','ability_ids','provenance','participates_in_score_aggregation'],
        'properties':{'knowledge_ids':{'type':'array','items':{'type':'string'}},'ability_ids':{'type':'array','items':{'type':'string'}},'participates_in_score_aggregation':{'const':False}}}}},
    'allOf':[
      {'if':{'properties':{'level':{'const':'L1_Ability'}}},'then':{'required':['requirement_code','indicator_code','indicator_description']}},
      {'if':{'properties':{'level':{'const':'L2_Course'}}},'then':{'required':['credits','semester','source_course_code','course_objectives','course_group_ids','course_nature']}},
      {'if':{'properties':{'level':{'const':'L3_Knowledge'}}},'then':{'required':['course_id','concept_id','knowledge_kind']}}]},
  'edge':{'type':'object','required':['id','source','target','relation_type','relation_category','directed','aggregation_weight','source_refs','provenance','review_status'],
    'properties':{'id':{'type':'string'},'source':{'type':'string'},'target':{'type':'string'},
      'relation_type':{'enum':['supports','belongs_to','prerequisite','similar','parallel','contains']},
      'relation_category':{'enum':['hierarchical','peer']},'directed':{'type':'boolean'},
      'aggregation_weight':{'type':['number','null'],'exclusiveMinimum':0,'maximum':1},
      'similarity_score':{'type':'number','minimum':0,'maximum':1},'source_refs':{'$ref':'#/$defs/refs'},
      'provenance':{'const':'simulated'},'review_status':{'const':'demo_unreviewed'}}}}
}
save('graph.schema.json',schema)
print(json.dumps({'output':str(OUT),'nodes':len(nodes),'edges':len(edges),'student_records':len(student_records)},ensure_ascii=False))

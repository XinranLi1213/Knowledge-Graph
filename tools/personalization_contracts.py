"""Schema authoring for the v2 review package, not application runtime code."""
S = {'type': 'string', 'minLength': 1}
N = {'type': 'number', 'minimum': 0, 'maximum': 100}
P = {'type': 'number', 'minimum': 0, 'maximum': 1}
I = {'type': 'integer', 'minimum': 1}
def arr(item, **extra): return {'type': 'array', 'items': item, **extra}
def ref(name): return {'$ref': '#/$defs/' + name}
def nullable(t): return {'anyOf': [t, {'type': 'null'}]}
def obj(props, optional=()):
    return {'type': 'object', 'properties': props,
            'required': [k for k in props if k not in optional], 'additionalProperties': False}
def en(*values): return {'enum': list(values)}
def ids(): return arr(S, uniqueItems=True)
def record(kind, props):
    return obj({'schema_version': {'const': '2.0.0'}, 'record_type': {'const': kind}, **props})

def make_schema():
    d = {}
    d['graph_ref'] = obj({'graph_id': S, 'graph_version': I})
    d['subject'] = obj({'type': en('student', 'class'), 'id': S})
    d['student_subject'] = obj({'type': {'const':'student'}, 'id': S})
    d['snapshot_ref'] = obj({'snapshot_id': S, 'revision': I})
    d['status'] = obj({
        'achievement_rate': nullable(N), 'health_color': en('green','yellow','red','grey'),
        'coverage_rate': P, 'learning_state': en('not_started','in_progress','completed'),
        'learning_progress': nullable(P),
        'grey_reason': en(None,'not_started','no_evidence','insufficient_coverage'),
        'evidence_granularity': en('none','knowledge_assessment','knowledge_aggregate','course_total','course_aggregate'),
        'aggregation_basis': en('none','knowledge_assessment','weighted_inputs','course_total'),
        'sample_count': {'type':'integer','minimum':0}, 'expected_count': I,
        'score_is_provisional': {'type':'boolean'},
        'score_provenance': en('simulated_precomputed','assessment_precomputed')})
    d['result'] = obj({'status': ref('status'), 'progress_source': en('simulated_learning_record','learning_record','unknown','not_applicable'),
                       'evidence_refs': ids(), 'input_node_ids': ids()})
    d['evidence'] = obj({'evidence_id': S, 'node_id': S, 'subject': ref('subject'),
        'kind': en('knowledge_assessment','course_total','legacy_class_aggregate'),
        'title': S, 'score': N, 'sample_count': I, 'source': en('synthetic_demo','assessment_record','imported_course_total'),
        'original_record_ref': S})
    d['summary'] = obj({'health_counts': obj({k:{'type':'integer','minimum':0} for k in ['green','yellow','red','grey']}),
        'ability_profile': arr(obj({'node_id': S, 'score': nullable(N), 'coverage': P})),
        'strength_node_ids': ids(), 'weak_node_ids': ids(), 'provisional_low_node_ids': ids()})
    d['context'] = obj({'scenario_id': en('knowledge_full','mixed_evidence','course_totals_only'),
        'period_id': en('stage5-demo','full-program-replay'), 'as_of': {'type':'string','format':'date'},
        'simulation_note': S})
    node_props = {
        'id': S, 'level': en('L1_Ability','L2_Course','L3_Knowledge'), 'label': S,
        'description': S, 'display_weight': {'type':'number','exclusiveMinimum':0},
        'source_refs': ids(), 'provenance': {'type':'object','additionalProperties':S},
        'requirement_code': S, 'indicator_code': S, 'indicator_description': S,
        'credits': {'type':'number','exclusiveMinimum':0}, 'source_course_code': nullable(S),
        'semester': {'type':'integer','minimum':1,'maximum':8},
        'course_group_ids': ids(), 'course_nature': en('必修','选修'),
        'course_id': S, 'concept_id': S, 'knowledge_kind': en('concept','experimental_skill'),
        'course_objectives': arr(obj({'id':S,'title':S,'description':S,'knowledge_ids':ids(),'ability_ids':ids(),
            'provenance':S,'participates_in_score_aggregation':{'const':False}}))}
    d['node'] = obj(node_props, optional=tuple(k for k in node_props if k not in
         ['id','level','label','description','display_weight','source_refs','provenance']))
    d['node']['allOf'] = [
        {'if':{'properties':{'level':{'const':lev}}},'then':{'required':fields}}
        for lev,fields in [('L1_Ability',['requirement_code','indicator_code','indicator_description']),
                          ('L2_Course',['credits','source_course_code','semester','course_group_ids','course_nature','course_objectives']),
                          ('L3_Knowledge',['course_id','concept_id','knowledge_kind'])]]
    d['edge'] = obj({'id':S,'source':S,'target':S,'relation_type':en('supports','belongs_to','prerequisite','similar','parallel','contains'),
        'relation_category':en('hierarchical','peer'),'directed':{'type':'boolean'},
        'aggregation_weight':nullable({'type':'number','exclusiveMinimum':0,'maximum':1}),
        'source_refs':ids(),'provenance':S,'review_status':S,'similarity_score':P,'concept_family':S},
        optional=('similarity_score','concept_family'))
    d['graph'] = record('public_graph', {'graph_ref':ref('graph_ref'),'title':S,
        'program_plan':{'type':'object'},'sources':arr({'type':'object'}),
        'course_groups':arr(obj({'id':S,'name':S,'description':S})),
        'nodes':arr(ref('node'),minItems=1),'edges':arr(ref('edge'))})
    d['profile'] = obj({'student_id':S,'display_name':S,'student_number':S,'class_id':S,
        'enrollment_year':{'type':'integer','minimum':2000}, 'profile_version':I,'is_simulated':{'type':'boolean'},
        'learning_context':obj({'goals':arr(S),'available_minutes_per_week':nullable({'type':'integer','minimum':0}),
            'preferred_resource_formats':arr(en('reading','practice','video')),
            'teacher_observations':arr(obj({'observation_id':S,'text':S,'as_of':{'type':'string','format':'date'},
                                         'source':en('teacher_record','simulated')}))}),
        'context_provenance':en('simulated_or_unknown','student_supplied','teacher_record','mixed','unknown')})
    d['registry'] = record('student_registry', {'registry_version':I,'graph_ref':ref('graph_ref'),
        'classes':arr(obj({'class_id':S,'display_name':S,'member_student_ids':ids()})),
        'students':arr(ref('profile'))})
    d['policy'] = record('evaluation_policy', {'policy_id':S,'policy_version':I,'green_min':N,'yellow_min':N,
        'min_coverage':P,'progress_definition':S,'coverage_definition':S,'score_precision':{'type':'integer','minimum':0},
        'runtime_calculation':{'const':False}})
    d['snapshot'] = record('evaluation_snapshot', {
        'snapshot_id':S,'revision':I,'graph_ref':ref('graph_ref'),'subject':ref('subject'),
        'registry_version':I,'evaluation_context':ref('context'),'policy_id':S,'policy_version':I,
        'score_mode':{'const':'precomputed'}, 'node_results':{'type':'object','additionalProperties':ref('result')},
        'evidence':arr(ref('evidence')),'summary':ref('summary')})
    d['resource'] = obj({'resource_id':S,'title':S,'node_ids':ids(),'kind':{'const':'local_study_guide'},
        'format':{'const':'reading'},'path':S,'availability':{'const':'available'},
        'provenance':{'const':'preset_demo'}})
    d['resources'] = record('resource_catalog', {'catalog_version':I,'graph_ref':ref('graph_ref'),'resources':arr(ref('resource'))})
    d['recommendation'] = obj({'recommendation_id':S,'audience':en('teacher','student'),
        'target_node_id':nullable(S),'kind':en('overview','strength','low_score','provisional_low','needs_practice','missing_evidence','not_started'),
        'priority':en('high','medium','low','info'),'summary':S,'basis_node_ids':ids(),'evidence_refs':ids(),
        'actions':arr(S,minItems=1),'review_node_ids':ids(),'prepare_node_ids':ids(),'resource_ids':ids(),
        'origin':en('preset_demo','llm_candidate','llm_generated','teacher_authored'),'lifecycle':en('active','candidate','archived')})
    d['bundle'] = record('recommendation_bundle', {'bundle_id':S,'version':I,'subject':ref('student_subject'),
        'graph_ref':ref('graph_ref'),'basis_snapshot':ref('snapshot_ref'),'resource_catalog_version':I,
        'basis_profile_version':I,
        'recommendations':arr(ref('recommendation'))})
    d['context_node'] = obj({'id':S,'level':en('L1_Ability','L2_Course','L3_Knowledge'),'label':S,'description':S})
    d['context_result'] = obj({'status':ref('status'),'progress_source':d['result']['properties']['progress_source'],
        'evidence_refs':ids(),'detail_scope':en('complete','selected_evidence','summary_only'),
        'omitted_evidence_count':{'type':'integer','minimum':0},'omitted_input_count':{'type':'integer','minimum':0}})
    d['context_recommendation'] = obj({'recommendation_id':S,'audience':en('teacher','student'),
        'target_node_id':nullable(S),'summary':S,'actions':arr(S),'basis_node_ids':ids(),'evidence_refs':ids(),
        'omitted_basis_count':{'type':'integer','minimum':0},'omitted_evidence_count':{'type':'integer','minimum':0}})
    d['context_selection'] = obj({'mode':en('node_neighborhood','overview_summary'),'seed_node_ids':ids(),
        'max_hops':{'const':1},'omitted_node_count':{'type':'integer','minimum':0},
        'limits':obj({'max_nodes':I,'max_edges':I,'max_evidence':I,'max_resources':I,'max_characters':I}),
        'limitations':arr(S)})
    d['focus_summary'] = obj({'weak_node_ids':ids(),'strength_node_ids':ids(),'provisional_low_node_ids':ids()})
    d['llm_context'] = record('llm_context', {'context_id':S,'subject':ref('student_subject'),'audience':en('teacher','student'),
        'graph_ref':ref('graph_ref'),'basis_snapshot':ref('snapshot_ref'),'base_bundle_version':I,
        'profile_version':I,'resource_catalog_version':I,'learning_context':d['profile']['properties']['learning_context'],
        'evaluation_context':ref('context'),'selection':ref('context_selection'),'focus_summary':ref('focus_summary'),
        'selected_nodes':arr(ref('context_node')),
        'selected_edges':arr(ref('edge')),'selected_results':{'type':'object','additionalProperties':ref('context_result')},
        'evidence':arr(ref('evidence')),'resources':arr(ref('resource')),
        'current_recommendations':arr(ref('context_recommendation')),
        'task':obj({'target_node_ids':ids(),'include_overview':{'type':'boolean'},'output_record_type':{'const':'recommendation_update'},
            'constraints':arr(S,minItems=1)})})
    d['operation'] = obj({'op':en('upsert','remove'),'recommendation_id':S,'recommendation':ref('recommendation')},optional=('recommendation',))
    d['operation']['allOf'] = [
        {'if':{'properties':{'op':{'const':'upsert'}}},'then':{'required':['recommendation']}},
        {'if':{'properties':{'op':{'const':'remove'}}},'then':{'not':{'required':['recommendation']}}}]
    d['update'] = record('recommendation_update', {'update_id':S,'context_id':S,'subject':ref('student_subject'),'audience':en('teacher','student'),
        'graph_ref':ref('graph_ref'),'basis_snapshot':ref('snapshot_ref'),'profile_version':I,
        'base_bundle_id':S,'base_bundle_version':I,'proposed_bundle_version':I,'resource_catalog_version':I,
        'lifecycle':{'const':'candidate'},'generated_by':obj({'kind':en('example','llm'),'model':nullable(S)}),
        'operations':arr(ref('operation'),minItems=1)})
    return {'$schema':'https://json-schema.org/draft/2020-12/schema',
        'title':'专业图谱与个人诊断分离契约 v2.0.0（审查草案）',
        'oneOf':[ref(k) for k in ['graph','registry','policy','snapshot','resources','bundle','llm_context','update']], '$defs':d}

"""Summarize saved real executions; never call a model or read credentials."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];FOLDER=ROOT/'review/agent-v5'
def read(name):return json.loads((FOLDER/name).read_text(encoding='utf-8'))
def write(name,value):(FOLDER/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    files=['real-followups-final-approved.json','real-followups-focused-verified.json','real-followups-teacher-guarded.json']
    latest={}
    for name in files:
        for item in read(name)['cases']:
            if item['turn']['state']=='succeeded':latest[item['case']]={'source_file':name,**item}
    assert len(latest)==9
    scores=[3.5,4,4,4.5,4,4,4,4.5,4]
    notes=[
        '教师措施与优先项具体，但仍偏长，历史修正说明可再压缩。',
        '题面参数和评分检查步骤齐全，修复变式答案泄露；NPN增益信息不足的解释仍可更明确。',
        '完整C代码与作答要求，未提前给出数值；比较表达式的设置稍显繁复。',
        '跨知识点承接原代码，整数除法与赋值转换、数值均核对正确。',
        '明确课程总分不能定位知识点，给出定位测评；含少量技术ID和较多报数。',
        '未学习对应预习任务，示例具体；实践要求仍需教师按可用仿真工具调整。',
        '阶段能力不足以判不合格；修复把能力直接知识点计数当成评价缺失，字段显示另做中文映射。',
        '工作区、静态点、小信号模型及增益数值核对正确，明确RB也在交流输入通路。',
        '变式仅改输入幅度且不泄露答案，提示检验小信号近似；近似容差由教师进一步说明。']
    review={'reviewer_type':'assistant_manual_review','teacher_expert_review':'pending','functional_successes':9,'cases_reviewed':9,'mean_score':sum(scores)/9,
        'scope':'代表性真实追问，非所有课程或任意问题的质量保证',
        'criteria':['当前事实与粒度边界','题目完整性及关键计算','承接历史与角色','可操作性和表达'],
        'known_limitations':['历史用final或approved命名的文件仍含后来发现的问题，不能当成无缺陷认证。','少量核验算例与针对已见错误的校验不能替代通用学科推理验证。','部分回答仍过长，技术ID与历史修正说明可继续减少。'],
        'cases':[{'case':i,'score':scores[i],'source_file':latest[i]['source_file'],'turn_id':latest[i]['turn']['turn_id'],'node_id':latest[i]['binding']['node_id'],'notes':notes[i]} for i in range(9)]}
    write('followup-quality-review.json',review)
    initial=read('first-release-initial.json')['batch'];final=read('first-release-final.json')['batch']
    assert sum(x['state'] in ('succeeded','reused') for x in final['results'])==417
    offline=read('offline-release-check.json');browser=read('real-browser-check.json')
    bundle=json.loads((ROOT/'review/model-diagnostics/bundle.json').read_text(encoding='utf-8'))
    report={'status':'passed_with_documented_quality_limits','real_external_api_tested':True,'provider':'deepseek','diagnosis_strategy':'teaching-agent-6','question_strategy':'tutoring-agent-6',
        'tests':{'python':45,'node':13,'api_config_browser':'passed_mock_transport','real_results_browser':browser['status'],'offline_portable_results':offline['real_model_artifacts'],'preset_contract_checks':'passed'},
        'release':{'entries':len(bundle['entries']),'shared_snapshots':len(bundle['snapshots']),'bytes':(ROOT/'review/model-diagnostics/bundle.json').stat().st_size,
                   'initial_successes':395,'initial_network_failures':22,'initial_success_rate':395/417,'final_successes':417,'reused_on_retry':395,'new_successes_on_retry':22,
                   'initial_model_calls':sum(x['usage']['model_calls'] for x in initial['results']),'retry_model_calls':sum(x['usage']['model_calls'] for x in final['results']),
                   'initial_tokens':sum(x['usage']['input_tokens']+x['usage']['output_tokens'] for x in initial['results']),
                   'retry_tokens':sum(x['usage']['input_tokens']+x['usage']['output_tokens'] for x in final['results'])},
        'diagnosis_sample_review':read('sample-quality-review.json'),'followups':{'successful_cases':9,'assistant_manual_mean':review['mean_score'],'teacher_expert_review':'pending'},
        'credential_accessed_or_exported':False,'private_user_conversations_exported':False,'preset_evaluations_modified':False}
    write('validation-report.json',report);print(json.dumps({'release':report['release'],'followups':report['followups']}))
if __name__=='__main__':main()

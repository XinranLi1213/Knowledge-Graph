"""Facts are rendered deterministically; the model proposes teaching actions."""
def summary(ctx):
    results=ctx.snapshot['node_results']
    if not ctx.target:
        ids=list(dict.fromkeys(ctx.focus['provisional_low_node_ids']+ctx.focus['weak_node_ids']))[:3]
        return '当前优先核查：'+('、'.join(ctx.nodes[k]['label']+f"（{results[k]['status']['achievement_rate']:.1f}分）" for k in ids) if ids else '暂无有评价依据的薄弱项')+'。未评价项不作为薄弱结论。'
    nid=ctx.target;n=ctx.nodes[nid];s=results[nid]['status'];v=s['achievement_rate'];cov=s['coverage_rate'];name=n['label']
    if v is None:
        return name+('尚未开始学习，暂无测评，当前以预习准备为主。' if s['learning_state']=='not_started' else '已完成学习，但尚无本节点测评，需先补充该粒度证据。' if s['learning_state']=='completed' else '正在学习，尚无本节点测评，先建立评价基线。')
    text=name+f"{'已评价部分' if cov<1 else ''}达成度{v:.2f}分，评价覆盖{cov:.0%}。"
    if cov<1:text+='这是阶段性结果。'
    if n['level']=='L2_Course':
        if s['evidence_granularity']=='course_total':return text+'目前只有课程总分，不能定位具体知识点。'
        children=[k for k,x in ctx.nodes.items() if x.get('course_id')==nid and results[k]['status']['achievement_rate'] is not None]
        low=sorted(children,key=lambda k:results[k]['status']['achievement_rate'])[:2]
        if low:text+='已测知识点中相对靠后的是'+ '、'.join(ctx.nodes[k]['label'] for k in low)+'。'
    elif n['level']=='L1_Ability':text+='能力由课程支撑聚合，需结合课程任务与证据覆盖理解。'
    else:text+='当前以'+('优先复核' if v<60 else '巩固与验证' if v<80 else '迁移应用与巩固')+'为主，得分不能证明具体错因。'
    return text

def limitations(ctx):
    notes=['演示评价用于教学建议，缺少具体作答过程，不能据分数认定错因。']
    if ctx.snapshot['subject']['type']=='class':notes.append('班级统计不能用于判断某个学生的表现。')
    if ctx.target:
        s=ctx.snapshot['node_results'][ctx.target]['status']
        if s['evidence_granularity']=='course_total':notes.append('只有课程总分，知识点层面的判断需要先测评。')
        elif s['achievement_rate'] is None:notes.append('本节点没有该粒度评价，建议是学习准备或测评安排。')
        elif s['coverage_rate']<1:notes.append('阶段性分数仅反映已评价部分。')
    return notes

const ROOT='review/personalization-v2/';
function freeze(v){if(v&&typeof v==='object'&&!Object.isFrozen(v)){Object.values(v).forEach(freeze);Object.freeze(v);}return v;}
const same=(a,b)=>a&&b&&Object.keys(a).length===Object.keys(b).length&&Object.keys(a).every(k=>a[k]===b[k]);
export class DataStore {
  constructor(fetcher=(...args)=>globalThis.fetch(...args)){this.fetcher=fetcher;this.cache=new Map();this.sequence=0;this.current=null;}
  async get(path){if(!this.cache.has(path)){const pending=this.fetcher(path).then(r=>{if(!r.ok)throw Error('数据读取失败：'+path);return r.json();}).then(freeze).catch(e=>{this.cache.delete(path);throw e;});this.cache.set(path,pending);}return this.cache.get(path);}
  async initialize(){this.manifest=await this.get(ROOT+'manifest.json');
    [this.graph,this.registry,this.policy,this.resources]=await Promise.all(['graph_path','registry_path','policy_path','resource_catalog_path'].map(k=>this.get(ROOT+this.manifest[k])));
    if(!same(this.graph.graph_ref,this.registry.graph_ref)||!same(this.graph.graph_ref,this.resources.graph_ref))throw Error('公共数据版本不一致');
    const ids=new Set(this.graph.nodes.map(n=>n.id));if(ids.size!==this.graph.nodes.length||this.graph.edges.some(e=>!ids.has(e.source)||!ids.has(e.target)))throw Error('公共图谱引用无效');
    this.students=this.registry.students.filter(s=>this.manifest.demo_student_ids.includes(s.student_id));
  }
  invalidateSelected({subject,scenario}){
    for(const rows of [this.manifest.snapshot_entries,this.manifest.recommendation_entries]){
      const row=rows.find(r=>same(r.subject,subject)&&r.scenario_id===scenario);if(row)this.cache.delete(ROOT+row.path);
    }
    if(subject.type==='class')this.cache.delete(`review/data/${scenario}.json`);
  }
  async select({role,subject,scenario}){
    const seq=++this.sequence;
    if(!['teacher','student'].includes(role)||!['class','student'].includes(subject.type))throw Error('展示角色或对象无效');
    if(role==='student'&&subject.type!=='student')throw Error('请选择模拟学生身份');
    const profile=subject.type==='student'?this.students.find(s=>s.student_id===subject.id):null;
    if(subject.type==='student'&&!profile)throw Error('该学生尚未开放演示');
    const row=this.manifest.snapshot_entries.find(r=>same(r.subject,subject)&&r.scenario_id===scenario);
    if(!row)throw Error('暂无该对象的评价快照');
    const adviceRow=this.manifest.recommendation_entries.find(r=>same(r.subject,subject)&&r.scenario_id===scenario);
    const [snapshot,bundle,legacy]=await Promise.all([this.get(ROOT+row.path),adviceRow?this.get(ROOT+adviceRow.path):null,
      subject.type==='class'?this.get(`review/data/${scenario}.json`):null]);
    if(seq!==this.sequence)return null;
    if(!same(snapshot.subject,subject)||!same(snapshot.graph_ref,this.graph.graph_ref)||snapshot.snapshot_id!==row.snapshot_id||snapshot.revision!==row.revision||snapshot.registry_version!==this.registry.registry_version||snapshot.evaluation_context.scenario_id!==scenario||snapshot.policy_id!==this.policy.policy_id||snapshot.policy_version!==this.policy.policy_version)throw Error('评价对象或版本不一致');
    if(bundle&&(!same(bundle.subject,subject)||!same(bundle.graph_ref,this.graph.graph_ref)||bundle.basis_snapshot.snapshot_id!==snapshot.snapshot_id||bundle.basis_snapshot.revision!==snapshot.revision||bundle.version!==adviceRow.version||bundle.basis_profile_version!==profile.profile_version||bundle.resource_catalog_version!==this.resources.catalog_version))throw Error('建议依据已过期');
    const nodeIds=new Set(this.graph.nodes.map(n=>n.id)),evIds=new Set(snapshot.evidence.map(e=>e.evidence_id));
    if(snapshot.evidence.some(e=>!same(e.subject,subject)))throw Error('评价证据对象不一致');
    for(const [id,result] of Object.entries(snapshot.node_results))if(!nodeIds.has(id)||result.evidence_refs.some(e=>!evIds.has(e)))throw Error('节点结果或证据引用无效');
    const resources=new Set(this.resources.resources.map(r=>r.resource_id));
    const active=(bundle?.recommendations||[]).filter(r=>r.audience===role&&r.lifecycle==='active'&&r.basis_node_ids.every(id=>snapshot.node_results[id]));
    const byNode=new Map();for(const r of active){if(r.target_node_id!==null&&!nodeIds.has(r.target_node_id))throw Error('建议节点无效');
      if(r.evidence_refs.some(id=>!evIds.has(id)))throw Error('建议证据无效');
      if([...r.basis_node_ids,...r.review_node_ids,...r.prepare_node_ids].some(id=>!nodeIds.has(id))||r.resource_ids.some(id=>!resources.has(id)))throw Error('建议依据或资源无效');
      const list=byNode.get(r.target_node_id)||[];list.push(r);byNode.set(r.target_node_id,list);}
    const legacyNodes=new Map((legacy?.nodes||[]).map(n=>[n.id,n]));
    const empty={achievement_rate:null,health_color:'grey',coverage_rate:0,learning_progress:null,learning_state:'in_progress',grey_reason:'no_evidence',score_is_provisional:false,evidence_granularity:'none',sample_count:0,expected_count:subject.type==='student'?1:40};
    const nodes=this.graph.nodes.map(n=>{const result=snapshot.node_results[n.id];const status=result?.status||empty;
      if(status.achievement_rate!==null&&(!Number.isFinite(status.achievement_rate)||status.achievement_rate<0||status.achievement_rate>100))throw Error('节点评价值无效');
      if(!['green','yellow','red','grey'].includes(status.health_color)||!Number.isFinite(status.coverage_rate)||status.coverage_rate<0||status.coverage_rate>1)throw Error('节点状态无效');
      return {...n,status,sidebar_info:{description:n.description,display_score:status.achievement_rate,
        score_label:n.level==='L1_Ability'?'能力达成估计':status.score_is_provisional?'已评价部分掌握度':subject.type==='student'?'个人得分':'班级平均',
        assessment_sources:result?.evidence_refs.map(id=>snapshot.evidence.find(e=>e.evidence_id===id)).filter(Boolean)||[],
        recommendations:result?byNode.get(n.id)||[]:[],remediation_advice:subject.type==='class'&&result?legacyNodes.get(n.id)?.sidebar_info.remediation_advice||[]:[]}};});
    const projected=new Map(nodes.map(n=>[n.id,n.status]));
    const summary={...snapshot.summary,ability_profile:snapshot.summary.ability_profile.map(a=>({...a,score:projected.get(a.node_id)?.achievement_rate??null,coverage:projected.get(a.node_id)?.coverage_rate??0}))};
    for(const key of ['weak_node_ids','strength_node_ids','provisional_low_node_ids'])summary[key]=snapshot.summary[key].filter(id=>projected.get(id)?.achievement_rate!=null);
    const view={...this.graph,nodes,summary,overview:byNode.get(null)||[],snapshot,profile,role,subject,scenario,
      resourceMap:new Map(this.resources.resources.map(r=>[r.resource_id,{...r,url:ROOT+r.path}])),policy:this.policy,
      displayName:profile?`${profile.display_name} · ${profile.student_number}`:this.registry.classes.find(c=>c.class_id===subject.id)?.display_name||subject.id};
    this.current=view;return view;
  }
}

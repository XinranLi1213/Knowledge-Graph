import copy
import hashlib
import json

def digest(value):
    # JSON round trips through JavaScript turn 74.0 into 74; that is not a fact change.
    def canonical(v):
        if isinstance(v,float) and v.is_integer():return int(v)
        if isinstance(v,dict):return {k:canonical(x) for k,x in v.items()}
        if isinstance(v,list):return [canonical(x) for x in v]
        return v
    return hashlib.sha256(json.dumps(canonical(value),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def ref(snapshot):return {'snapshot_id':snapshot['snapshot_id'],'revision':snapshot['revision']}

class Context:
    def __init__(self,graph,snapshot,profile,resources,policy,audience,target,previous=None,dependencies=None):
        self.graph=graph;self.snapshot=snapshot;self.profile=profile;self.resources=resources;self.policy=policy
        self.audience=audience;self.target=target;self.previous=previous;self.discussion=None;self.nodes={n['id']:n for n in graph['nodes']}
        self.adj={k:[] for k in self.nodes};self.seen=set();self.queries=[];self.trace=[]
        for e in graph['edges']:self.adj[e['source']].append(e);self.adj[e['target']].append(e)
        self.focus={k:snapshot['summary'][k][:3] for k in ['weak_node_ids','strength_node_ids','provisional_low_node_ids']}
        seeds={target} if target else {k for k,n in self.nodes.items() if n['level']=='L1_Ability'}|{k for values in self.focus.values() for k in values}
        self.allowed=set(seeds)
        for _ in range(2):self.allowed|={e['target'] if e['source']==k else e['source'] for k in list(self.allowed) for e in self.adj[k]}
        self.seen=set(seeds)
        if target:self.seen|={e['target'] if e['source']==target else e['source'] for e in self.adj[target]}
        else:self.seen|={self.nodes[k]['course_id'] for k in list(self.seen) if self.nodes[k]['level']=='L3_Knowledge'}
        self.initial=set(self.seen)
        if dependencies:
            self.seen.update(dependencies['read_nodes'])
            for query in dependencies['queries']:self.call(query['tool'],query['arguments'],replay=True)
        self._check()
    def _check(self):
        if not self.seen<=self.allowed or len(self.seen)>32 or len(self.payload()['edges'])>64 or len(json.dumps(self.payload(),ensure_ascii=False))>48000:raise ValueError('上下文超出允许范围或预算')
    def evidence(self):
        wanted={i for k in self.seen for i in self.snapshot['node_results'][k]['evidence_refs']}
        return [e for e in self.snapshot['evidence'] if e['node_id'] in self.seen and e['evidence_id'] in wanted][:32]
    def resource_list(self):
        return [{k:r[k] for k in ['resource_id','title','kind','format']} for r in self.resources['resources'] if set(r['node_ids'])&self.seen][:8]
    def payload(self):
        evidence=self.evidence();provided={e['evidence_id'] for e in evidence}
        return {'subject':self.snapshot['subject'],'audience':self.audience,'target_node_id':self.target,
            'snapshot_ref':ref(self.snapshot),'graph_ref':self.graph['graph_ref'],'scenario':self.snapshot['evaluation_context'],'evaluation_policy':self.policy,
            'learning_context':self.profile.get('learning_context',{}),'discussed_diagnosis':self.discussion,
            'nodes':{k:{'label':self.nodes[k]['label'],'level':self.nodes[k]['level'],'description':self.nodes[k]['description'],'provenance':self.nodes[k]['provenance'],'status':self.snapshot['node_results'][k]['status'],'progress_source':self.snapshot['node_results'][k]['progress_source'],
                'evidence_refs':[i for i in self.snapshot['node_results'][k]['evidence_refs'] if i in provided],
                'omitted_evidence_count':len(set(self.snapshot['node_results'][k]['evidence_refs'])-provided)} for k in sorted(self.seen)},
            'edges':[{k:e[k] for k in ['id','source','target','relation_type','aggregation_weight']} for e in self.graph['edges'] if e['source'] in self.seen and e['target'] in self.seen],
            'evidence':evidence,'resources':self.resource_list(),'focus':self.focus if self.target is None else None,
            'target_course_objectives':self.nodes[self.target].get('course_objectives',[]) if self.target else [],
            'limitations':['仅使用已给出的事实；未评价不等于薄弱；省略的聚合证据不表示分数失效；不补造关系。']}
    def dependencies(self):return {'read_nodes':sorted(self.seen-self.initial),'queries':copy.deepcopy(self.queries)}
    def fingerprint(self,generator):
        p=self.payload();p.pop('snapshot_ref');p['scenario']={k:v for k,v in p['scenario'].items() if k!='as_of'}
        p['graph_ref']=self.graph['graph_ref'];p['policy']=self.policy;p['generator']=generator;p['prompt_version']='agent-1'
        p['queries']=self.queries
        if any(q['tool']=='compare_previous' for q in self.queries):p['previous']={k:self.previous['node_results'][k] for k in sorted(self.seen)} if self.previous else None
        return digest(p)
    def call(self,name,args,replay=False):
        if not isinstance(args,dict):raise ValueError('工具参数必须是对象')
        expected={'read_node':{'node_id'},'read_neighbors':{'node_id','relation_type'},'read_evidence':{'node_id'},'read_resources':{'node_id'},'compare_previous':set()}
        if name not in expected or set(args)!=expected[name]:raise ValueError('不允许的工具或参数')
        if not replay and len(self.trace)>=6:raise ValueError('工具次数超限')
        original=set(self.seen)
        try:
            if name=='compare_previous':
                result={'before':ref(self.previous) if self.previous else None,'after':ref(self.snapshot),
                    'changes':[{ 'node_id':k,'before':self.previous['node_results'][k]['status'],'after':self.snapshot['node_results'][k]['status']} for k in sorted(self.seen) if self.previous and self.previous['node_results'][k]!=self.snapshot['node_results'][k]]}
            else:
                nid=args['node_id']
                if nid not in self.allowed:raise ValueError('节点不在当前对象的允许查询范围')
                self.seen.add(nid)
                if name=='read_neighbors':
                    typ=args['relation_type']
                    if typ not in ('all','supports','belongs_to','prerequisite','similar','parallel'):raise ValueError('关系类型无效')
                    self.seen|={e['target'] if e['source']==nid else e['source'] for e in self.adj[nid] if e['relation_type']==typ or typ=='all'}
                if name=='read_evidence':
                    wanted=set(self.snapshot['node_results'][nid]['evidence_refs'])
                    self.seen.update(e['node_id'] for e in [e for e in self.snapshot['evidence'] if e['evidence_id'] in wanted and e['node_id'] in self.allowed][:8])
                self._check();p=self.payload()
                result={'nodes':p['nodes'],'edges':p['edges']} if name in ('read_node','read_neighbors') else {'evidence':p['evidence']} if name=='read_evidence' else {'resources':p['resources']}
            if {'tool':name,'arguments':args} not in self.queries:self.queries.append({'tool':name,'arguments':copy.deepcopy(args)})
            self._check()
            if not replay:self.trace.append({'tool':name,'arguments':args,'node_count':len(self.seen)})
            return result
        except BaseException:self.seen=original;raise
    def validate_output(self,value):
        from jsonschema import validate
        from .contracts import OUTPUT
        validate(value,OUTPUT)
        if not value['explanation'].strip() or len(value['explanation'])>6000:raise ValueError('解释为空或过长')
        if not set(value['cited_node_ids'])<=self.seen:raise ValueError('引用了未读取节点')
        if not set(value['cited_evidence_ids'])<={e['evidence_id'] for e in self.evidence()}:raise ValueError('引用了未读取证据')
        if not set(value['resource_ids'])<={r['resource_id'] for r in self.resource_list()}:raise ValueError('引用了未读取资源')
        if not value['cited_node_ids']:raise ValueError('解释必须关联已知节点')
        return value

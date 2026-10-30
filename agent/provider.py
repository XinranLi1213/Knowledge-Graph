import copy
import json
import os
import urllib.request
import urllib.error
import time
from jsonschema.exceptions import ValidationError
from .contracts import OUTPUT
from .pedagogy import instructions,check_presentation,clean_display,intent,PROMPT_VERSION,QUESTION_PROMPT_VERSION

class GenerationError(ValueError):
    def __init__(self,code,message):super().__init__(message);self.code=code

PROVIDERS={
    'openai':{'id':'openai','label':'OpenAI','endpoint':'https://api.openai.com/v1/chat/completions','key_env':'OPENAI_API_KEY','default_model':'','models':[],'output_mode':'json_schema'},
    'deepseek':{'id':'deepseek','label':'DeepSeek','endpoint':'https://api.deepseek.com/chat/completions','key_env':'DEEPSEEK_API_KEY','default_model':'deepseek-flash','models':['deepseek-flash','deepseek-v4-pro'],'output_mode':'json_object'}}

def provider_catalog():return [{k:v for k,v in item.items() if k!='key_env'} for item in PROVIDERS.values()]

class ProviderError(RuntimeError):
    def __init__(self,code,message):super().__init__(message);self.code=code

def load_env(path):
    if not path.is_file():return
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if not line.strip() or line.lstrip().startswith('#') or '=' not in line:continue
        key,value=line.split('=',1);key=key.strip()
        if key in ('AGENT_PROVIDER','OPENAI_API_KEY','DEEPSEEK_API_KEY','AGENT_MODEL','AGENT_MAX_OUTPUT_TOKENS'):os.environ.setdefault(key,value.strip().strip('\"\''))

class Provider:
    prompt_version=PROMPT_VERSION
    question_prompt_version=QUESTION_PROMPT_VERSION
    def __init__(self,mode=None,key=None,model=None,transport=None):
        self.mode=mode or os.getenv('AGENT_PROVIDER','rules')
        if self.mode not in ('rules',*PROVIDERS):raise ValueError('AGENT_PROVIDER支持rules、openai或deepseek')
        config=PROVIDERS.get(self.mode,{})
        self.key=(key or os.getenv(config['key_env'])) if self.mode!='rules' else None
        self.model=(model or os.getenv('AGENT_MODEL') or config['default_model']) if self.mode!='rules' else None
        self.transport=transport or self._request
        if self.mode!='rules' and (not self.key or not self.model):raise ValueError(config['label']+'需要'+config['key_env']+'和有效模型名称')
    @property
    def origin(self):return 'rules_demo' if self.mode=='rules' else 'model'
    @property
    def identity(self):return self.mode+':'+(self.model or 'rules-v1')
    def _request(self,payload):
        request=urllib.request.Request(PROVIDERS[self.mode]['endpoint'],data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+self.key})
        try:
            with urllib.request.urlopen(request,timeout=45) as response:
                value=json.load(response);value['_request_id']=response.headers.get('x-request-id') or response.headers.get('x-ds-request-id');return value
        except urllib.error.HTTPError as error:
            code={400:'invalid_request',401:'authentication',402:'insufficient_balance',403:'permission',404:'model_not_found',429:'rate_limit'}.get(error.code,'provider_http')
            raise ProviderError(code,{'invalid_request':'接口参数或模型不兼容，请检查供应商与模型名称。','authentication':'密钥无效，请检查API Key。','insufficient_balance':'API账户余额不足，请在对应供应商平台检查余额。','permission':'当前账户无访问权限。','model_not_found':'模型不可用，请检查模型名称。','rate_limit':'额度或速率受限，请稍后重试。'}.get(code,'模型服务返回错误，请稍后重试。')) from None
        except json.JSONDecodeError:raise ProviderError('invalid_response','模型服务返回的响应不是完整JSON，请稍后重试。') from None
        except TimeoutError:raise ProviderError('timeout','模型服务响应超时，请稍后重试。') from None
        except Exception:raise ProviderError('network','模型服务连接失败，请检查网络后重试。') from None
    def generate(self,ctx,question=None,history=None):
        usage={'model_calls':0,'input_tokens':0,'output_tokens':0}
        ctx.usage=usage
        ctx.request_ids=[];ctx.attempts=[]
        if self.mode=='rules':return self.rules(ctx,question),usage
        schema=copy.deepcopy(OUTPUT);schema['properties']['explanation']={'type':'string'}
        for field in ['cited_node_ids','cited_evidence_ids','resource_ids','limitations']:schema['properties'][field]['items']={'type':'string'}
        schema['required']=list(schema['properties'])
        if question:schema['properties']['sections']={'type':'null'}
        # Strict provider schemas do not accept minLength; runtime validation still does.
        def compatible(value):
            if isinstance(value,dict):
                value.pop('minLength',None)
                for v in value.values():compatible(v)
            elif isinstance(value,list):
                for v in value:compatible(v)
        compatible(schema)
        tools=[]
        for name in ['read_node','read_neighbors','read_evidence','read_resources','read_teaching','compare_previous']:
            props={} if name=='compare_previous' else {'node_id':{'type':'string'}}
            if name=='read_neighbors':props['relation_type']={'type':'string','enum':['all','supports','belongs_to','prerequisite','similar','parallel']}
            tools.append({'type':'function','function':{'name':name,'description':'在固定对象/评价版本内查询；不改变事实。', 'strict':True,'parameters':{'type':'object','properties':props,'required':list(props),'additionalProperties':False}}})
        model_context=ctx.model_payload()
        if question:
            from .exercises import examples
            if intent(question) in ('explain','assessment') and not any(w in question for w in ('成绩','得分','达成','学情','薄弱','覆盖','评价','低分','分数')):
                model_context['nodes']={k:{f:v for f,v in n.items() if f in ('label','level')} for k,n in model_context['nodes'].items()}
                model_context.update(evidence=[],focus=None,learning_context={},course_objectives=[],verified_factual_summary=None,verified_limitations=['本轮是学科讲解或练习设计，不对学生成绩作判断。'])
            reference=examples(ctx)
            if any(word in question for word in ('不给答案','不要给答案','不提供完整答案','自己算')):reference=[{k:v for k,v in e.items() if k!='solution'} for e in reference]
            model_context['verified_examples']=reference
        messages=[{'role':'system','content':instructions(ctx,question)},
            {'role':'user','content':json.dumps({'context':model_context,'history':history or [],'question':question or '给出当前节点的简明诊断与可执行行动。'},ensure_ascii=False)}]
        if self.mode=='deepseek':
            for tool in tools:tool['function'].pop('strict',None)
            example={'explanation':'先给出直接结论。','sections':None if question else {'conclusion':'当前需要关注的重点。','actions':['安排一次针对目标知识的短测，记录过程用于定位困难。'],'verification':'比较独立完成情况与复测结果，区分需要继续讲解的环节。'},'cited_node_ids':[ctx.target or sorted(ctx.seen)[0]],'cited_evidence_ids':[],'resource_ids':[],'limitations':[]}
            messages[0]['content']+=' 终答必须是一个JSON对象，不使用Markdown代码围栏。JSON Schema：'+json.dumps(schema,ensure_ascii=False)+'。格式示例（不能照抄解释）：'+json.dumps(example,ensure_ascii=False)
        repaired=False;retried=False;cache={};tool_errors=0
        limit=max(512,min(4000,int(os.getenv('AGENT_MAX_OUTPUT_TOKENS','4000'))))
        cap=min(limit,2600 if question else 1800)
        for index in range(4):
            if len(json.dumps(messages,ensure_ascii=False))>96000:raise ValueError('累计模型消息预算超限')
            usage['model_calls']+=1
            final=index==3 or len(ctx.trace)>=6 or repaired
            payload={'model':self.model,'messages':messages,'tools':tools}
            if final:payload['tool_choice']='none'
            if self.mode=='deepseek':payload.update(max_tokens=cap,thinking={'type':'disabled'},response_format={'type':'json_object'})
            else:payload.update(max_completion_tokens=cap,parallel_tool_calls=False,response_format={'type':'json_schema','json_schema':{'name':'diagnostic_output','strict':True,'schema':schema}})
            attempt={'number':index+1,'output_cap':cap,'finish_reason':None,'error_code':None};ctx.attempts.append(attempt)
            try:response=self.transport(payload)
            except ProviderError as error:
                attempt['error_code']=error.code
                if error.code in ('network','timeout','invalid_response','rate_limit','provider_http') and not retried and index<3:
                    retried=True;time.sleep(.3);continue
                raise
            if response.get('_request_id'):ctx.request_ids.append(str(response['_request_id'])[:200])
            u=response.get('usage',{});usage['input_tokens']+=u.get('prompt_tokens',0);usage['output_tokens']+=u.get('completion_tokens',0)
            choice=response['choices'][0];message=choice['message'];attempt['finish_reason']=choice.get('finish_reason')
            if message.get('refusal') or choice.get('finish_reason')=='content_filter':raise GenerationError('refusal','模型拒绝回答，未发布新结果')
            if message.get('tool_calls'):
                if final:raise GenerationError('tool_budget','已到终答阶段，模型仍请求工具')
                messages.append({k:message[k] for k in ('role','content','tool_calls') if k in message})
                for call in message['tool_calls']:
                    if len(ctx.trace)>=6:raise ValueError('工具次数超限')
                    try:
                        name=call['function']['name'];args=json.loads(call['function']['arguments']);key=json.dumps([name,args],sort_keys=True)
                        if key not in cache:cache[key]=ctx.call(name,args)
                        result=cache[key]
                    except (ValueError,KeyError,TypeError):
                        tool_errors+=1
                        if tool_errors>1:raise GenerationError('invalid_tool','工具查询反复越界或无效')
                        result={'error':'工具参数无效或超出当前对象允许范围；请使用已给出的依据完成回答。'}
                    messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(result,ensure_ascii=False)})
                continue
            try:
                if choice.get('finish_reason')=='length':raise GenerationError('truncated','输出达到上限，结果未完整生成')
                if choice.get('finish_reason')!='stop' or not message.get('content'):raise GenerationError('empty_output','模型返回空内容或非完整终答')
                value=ctx.validate_output(json.loads(message['content']));value=clean_display(value,ctx,question)
                if question:
                    from .exercises import check_answer
                    check_answer(value,ctx,question)
                if not question and value.get('sections'):
                    from .factual_summary import summary,limitations
                    value['sections']['conclusion']=summary(ctx);value['explanation']=summary(ctx);value['limitations']=limitations(ctx)
                    attempt['factual_summary_source']='program';attempt['teaching_actions_source']='model'
                check_presentation(value,question,ctx)
                return value,usage
            except (ValueError,ValidationError) as error:
                code=getattr(error,'code','invalid_output');attempt['error_code']=code
                if repaired or index>=3:raise GenerationError(code,'回答校验未通过：'+str(error)[:100]) from None
                repaired=True;cap=min(limit,max(cap,3200 if question else 2400))
                # Partial JSON is never published; repair from facts, not regex extraction.
                messages.append({'role':'user','content':'上次输出未通过'+code+'校验，具体问题：'+str(error)[:160]+'。请基于原始事实重新给出完整、简洁JSON终答；保留合法引用；自动诊断必须包含结论、1–3条具体行动和可检验的复测步骤。追问要直接解决上述问题。不要调用工具。'})
        raise GenerationError('call_budget','模型调用次数达到上限，未获得合格终答')
    def rules(self,ctx,question):
        nid=ctx.target
        if not nid:
            ids=ctx.focus['provisional_low_node_ids']+ctx.focus['weak_node_ids'];ids=list(dict.fromkeys(ids))[:3]
            text='当前重点关注：'+('、'.join(ctx.nodes[k]['label'] for k in ids) if ids else '暂无有评价依据的薄弱项')+'。能力画像需结合各项评价覆盖率理解，未评价项不判为薄弱。'
        else:
            st=ctx.snapshot['node_results'][nid]['status'];value=st['achievement_rate'];ids=[nid]
            text=ctx.nodes[nid]['label']+'：'
            if value is None:text+='尚未开始学习，暂不判断薄弱。' if st['learning_state']=='not_started' else '当前没有该粒度的评价分数，需要补充测评。'
            else:
                text+=f"当前{'已评价部分掌握度' if st['score_is_provisional'] else '达成估计'} {value:.2f}，评价覆盖 {st['coverage_rate']:.0%}。"
                text+=('已考部分低于达标线，应优先复核。' if value<60 else '已评价部分达到当前达标线，可结合任务验证稳定性。')
                if st['learning_progress'] is not None:text+=f"学习进度为 {st['learning_progress']:.0%}，与评价覆盖分别统计。"
                if st['evidence_granularity']=='course_total':text+='只有课程总分，不能定位具体知识点薄弱项。'
            if question:
                if any(x in question for x in ['之前','变化','上次','提高','前后']):
                    diff=ctx.call('compare_previous',{});text+=f"与前一版比较，本次可见范围有{len(diff['changes'])}个节点结果变化。" if diff['before'] else '当前是首版，暂无前一版可比较。'
                elif any(x in question for x in ['先修','后继','基础']):
                    ctx.call('read_neighbors',{'node_id':nid,'relation_type':'prerequisite'})
                    prior=[e['source'] for e in ctx.graph['edges'] if e['target']==nid and e['relation_type']=='prerequisite']
                    text+='直接先修：'+('、'.join(ctx.nodes[k]['label'] for k in prior) if prior else '暂无已登记节点')+'；先修关系不直接传递成绩。'
                elif any(x in question for x in ['依据','为什么','低','补习','复习','建议']):
                    ctx.call('read_evidence',{'node_id':nid});text+='建议对照已给出的评价记录核查错误步骤；这是一条规则演示回答，不替代大模型对具体题目错因的分析。'
                else:text+='当前使用规则演示模式，仅提供可核验的状态解释；开放式分析需配置真实模型。'
        evidence=ctx.evidence()
        return ctx.validate_output({'explanation':text,'cited_node_ids':ids or sorted(ctx.seen)[:1],
            'cited_evidence_ids':[e['evidence_id'] for e in evidence if e['node_id'] in ids][:8],
            'resource_ids':[r['resource_id'] for r in ctx.resource_list()][:2],
            'limitations':['规则演示：未调用大模型。','未评价、未学习与已测薄弱分开判断。']})

# Refresh the local reload controller when this module is explicitly reloaded.
# It has no startup side effect and never exports an in-memory credential.
import sys as _sys
if 'agent.runtime_control' in _sys.modules:
    import importlib as _importlib
    _importlib.reload(_sys.modules['agent.runtime_control'])

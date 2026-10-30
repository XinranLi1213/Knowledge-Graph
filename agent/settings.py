"""Local service configuration: never returns or persists a credential."""
import threading
from .provider import Provider,PROVIDERS,provider_catalog
from .engine import Conflict

class Settings:
    def __init__(self,engine,factory=None):
        self.engine=engine;self.factory=factory or (lambda key,model,supplier:Provider(supplier,key,model));self.lock=threading.Lock();self.revision=0;self.verified=False
    def status(self):
        return {**self.engine.capabilities(),'verified':self.verified,'storage':'service_memory','supplier':self.engine.provider.mode if self.engine.provider.origin=='model' else 'deepseek','providers':provider_catalog(),'configuration_revision':self.revision}
    def disconnect(self):
        with self.lock:
            with self.engine.lock:self.engine.provider=Provider('rules');self.revision+=1;self.verified=False
        return self.status()
    def test_and_enable(self,body):
        key=body.get('api_key','');model=body.get('model','');supplier=body.get('supplier','openai')
        if not isinstance(supplier,str) or supplier not in PROVIDERS:raise ValueError('请选择受支持的API供应商')
        if not model:model=PROVIDERS[supplier]['default_model']
        if not isinstance(key,str) or len(key)>1024 or any(c.isspace() for c in key):raise ValueError('密钥格式无效')
        if not isinstance(model,str) or not model.strip() or len(model)>120 or any(c.isspace() for c in model):raise ValueError('请输入有效模型名称')
        with self.lock:
            revision=self.revision
            if not key and self.engine.provider.mode==supplier:key=self.engine.provider.key
        if not key:raise ValueError('请输入API Key')
        candidate=self.factory(key,model,supplier)
        scope=self.engine.scope({'type':'student','id':'DEMO001'},'mixed_evidence')
        ctx=self.engine.context(scope,'teacher','C05');output,usage=candidate.generate(ctx,'这是连接测试。请简要解释当前C05评价并引用C05，不要扩展查询。',[]);ctx.validate_output(output)
        with self.lock:
            if revision!=self.revision:raise Conflict('测试期间配置已变化，请重新测试')
            with self.engine.lock:self.engine.provider=candidate;self.revision+=1;self.verified=True
        return {**self.status(),'test':{'passed':True,'model_calls':usage['model_calls'],'request_ids':getattr(ctx,'request_ids',[])}}

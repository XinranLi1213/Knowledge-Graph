"""Reload generation policy at an idle local service without exporting its credential."""
import importlib
import json
import threading

def reload_generation(engine,settings):
    with engine.lock:
        if any(r['state']=='running' for r in engine.store.all('agent_run')) or any(b['state']=='running' for b in engine.store.all('batch')):raise ValueError('请先暂停批次并等待正在运行的任务完成')
        from . import pedagogy,context,provider,contracts,factual_summary,exercises,bundles,engine as engine_module,settings as settings_module,batches as batches_module,http_server
        previous_batches_class=batches_module.Batches
        importlib.reload(contracts);importlib.reload(factual_summary);importlib.reload(exercises);importlib.reload(pedagogy);importlib.reload(context);importlib.reload(provider);importlib.reload(bundles);importlib.reload(engine_module);importlib.reload(batches_module)
        for name in ('work','execute','summary','resume'):setattr(previous_batches_class,name,getattr(batches_module.Batches,name))
        engine.__class__=engine_module.Engine
        if not hasattr(engine,'model_slots'):engine.model_slots=threading.BoundedSemaphore(2)
        manager=getattr(engine,'batch_manager',None)
        if manager is None:
            # One-time migration for the already-running preview service, whose
            # batch manager predated the explicit back-reference. No key inspection.
            import gc
            manager=next((obj for obj in gc.get_objects() if type(obj).__module__=='agent.batches' and type(obj).__name__=='Batches' and getattr(obj,'engine',None) is engine),None)
        if manager is not None:
            manager.__class__=batches_module.Batches;engine.batch_manager=manager
            for batch in engine.store.all('batch'):
                if batch['mode']=='first_release' and batch['state']=='paused' and batch['reason']!='本批预算到达；可继续剩余任务':
                    batch['tokens_used']=sum(r['usage']['input_tokens']+r['usage']['output_tokens'] for r in batch['results']);batch['calls_used']=sum(r['usage']['model_calls'] for r in batch['results']);manager.save(batch)
        current=engine.provider;default_transport=getattr(current.transport,'__self__',None) is current
        current.__class__=provider.Provider
        if default_transport:current.transport=current._request
        engine_module.Context=context.Context;engine_module.Provider=provider.Provider
        settings_module.Provider=provider.Provider;settings_module.PROVIDERS=provider.PROVIDERS;settings_module.provider_catalog=provider.provider_catalog
        batches_module.PROMPT_VERSION=pedagogy.PROMPT_VERSION;http_server.ProviderError=provider.ProviderError
        http_server.export_bundle=bundles.export_bundle;http_server.load_bundle=bundles.load_bundle
        engine.teaching=json.loads((engine.root/'review/teaching-reference/reference.json').read_text(encoding='utf-8'))
        return {'reloaded':True,'prompt_version':pedagogy.PROMPT_VERSION,'configured':current.origin=='model'}

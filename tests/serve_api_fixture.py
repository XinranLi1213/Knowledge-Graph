"""Browser-only mock transport. Never contacts an external API or exports results."""
from pathlib import Path
import json
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.http_server import create_server
from agent.provider import Provider,ProviderError

def transport(payload):
    context=json.loads(payload['messages'][1]['content'])['context'];node=context['target_node_id'] or next(iter(context['nodes']))
    score=context['nodes'][node]['status']['achievement_rate'];coverage=context['nodes'][node]['status']['coverage_rate']
    output={'explanation':f'浏览器测试传输：当前评价 {score:.2f}，覆盖 {coverage:.0%}。' if score is not None else '浏览器测试传输：当前没有评价。',
        'cited_node_ids':[node],'cited_evidence_ids':[],'resource_ids':[],'limitations':['仅用于浏览器测试，没有调用真实模型。']}
    return {'_request_id':'browser-mock-request','choices':[{'finish_reason':'stop','message':{'content':json.dumps(output,ensure_ascii=False)}}],'usage':{'prompt_tokens':100,'completion_tokens':20}}

def factory(key,model,supplier='openai'):
    def fail(_):raise ProviderError('authentication','密钥无效，请检查API Key。')
    return Provider(supplier,key,model,fail if key=='bad-key' else transport)

if __name__=='__main__':
    with tempfile.TemporaryDirectory() as tmp:
        server=create_server(Path(__file__).resolve().parents[1],Path(tmp)/'browser.sqlite',0,Provider('rules'),factory)
        print(f'http://127.0.0.1:{server.server_address[1]}',flush=True)
        try:server.serve_forever()
        except KeyboardInterrupt:pass
        finally:server.server_close();server.engine.close()

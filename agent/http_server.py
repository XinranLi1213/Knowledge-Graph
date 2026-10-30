from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse,parse_qs,unquote
import json
import os
from jsonschema.exceptions import ValidationError
from .engine import Engine,Conflict
from .provider import load_env,ProviderError
from .settings import Settings
from .bundles import export_bundle,load_bundle

def create_server(root,db_path=None,port=8765,provider=None,provider_factory=None):
    root=Path(root).resolve();runtime=root/'.runtime';runtime.mkdir(exist_ok=True)
    engine=Engine(root,db_path or runtime/'agent.sqlite3',provider=provider)
    settings=Settings(engine,provider_factory)
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(root),**kwargs)
        def reply(self,status,value):
            data=json.dumps(value,ensure_ascii=False,allow_nan=False).encode()
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def trusted(self):
            origin=self.headers.get('Origin');site=self.headers.get('Sec-Fetch-Site')
            if self.headers.get('Host') not in ('127.0.0.1:'+str(self.server.server_address[1]),'localhost:'+str(self.server.server_address[1])):raise ValueError('需要通过本机地址访问')
            if site=='cross-site' or origin and urlparse(origin).netloc!=self.headers.get('Host'):raise ValueError('仅允许同源本地请求')
        def args(self):return {k:v[-1] for k,v in parse_qs(urlparse(self.path).query).items()}
        def scope(self,args):return engine.scope({'type':args.get('subject_type','student'),'id':args.get('subject_id','DEMO001')},args.get('scenario','mixed_evidence'))
        def body(self):
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('需要application/json')
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=2000000:raise ValueError('请求大小无效')
            value=json.loads(self.rfile.read(length),parse_constant=lambda _:(_ for _ in ()).throw(ValueError('不允许非有限数值')))
            if not isinstance(value,dict):raise ValueError('请求必须为对象')
            return value
        def do_GET(self):
            path=urlparse(self.path).path
            if path.startswith('/api/'):
                try:
                    self.trusted();args=self.args()
                    if path=='/api/agent/health':return self.reply(200,{'available':True,'provider':engine.provider.origin,**settings.status()})
                    if path=='/api/agent/config':return self.reply(200,settings.status())
                    scope=self.scope(args)
                    if path=='/api/agent/snapshot':return self.reply(200,engine.ensure(scope))
                    if path=='/api/agent/state':return self.reply(200,engine.state(scope,args.get('audience','teacher'),args.get('node_id') or None))
                    return self.reply(404,{'error':'接口不存在'})
                except (ValueError,ValidationError,KeyError,TypeError) as error:return self.reply(400,{'error':str(error)[:240]})
            parts=Path(unquote(path)).parts
            target=(root/unquote(path).lstrip('/')).resolve()
            if any(p.startswith('.') for p in parts) or not target.is_relative_to(root) or target.suffix in ('.sqlite3','.db','.py','.pyc') or path.startswith('/agent/'):
                self.send_error(403);return
            if target.is_dir() and path not in ('','/'):
                self.send_error(403);return
            super().do_GET()
        def do_POST(self):
            try:
                self.trusted();body=self.body();path=urlparse(self.path).path
                if path=='/api/agent/config/test':return self.reply(200,settings.test_and_enable(body))
                if path=='/api/agent/config/disconnect':return self.reply(200,settings.disconnect())
                if path=='/api/agent/bundle/export':
                    with engine.lock:
                        destination=root/'review/model-diagnostics/bundle.json'
                        count=export_bundle(engine,destination);engine.seed_artifacts=load_bundle(engine,destination)
                    return self.reply(200,{'exported_model_diagnoses':count})
                scope=self.scope(body);audience=body.get('audience','teacher');target=body.get('node_id') or None
                if path=='/api/agent/diagnose':result=engine.ensure_diagnosis(scope,audience,target,'retry' if body.get('retry') else 'view')
                elif path=='/api/agent/ask':result=engine.ask(scope,audience,target,body.get('question'),body.get('snapshot_ref'))
                elif path=='/api/agent/demo-update':
                    if audience!='teacher':raise ValueError('模拟补测入口仅限教师演示')
                    result=engine.demo_update(scope,body['base_revision'],body['event_id'])
                elif path=='/api/agent/snapshots':
                    if audience!='teacher':raise ValueError('快照提交入口仅限教师演示')
                    result=engine.submit(scope,body['snapshot'],body['base_revision'],body['event_id'])
                else:return self.reply(404,{'error':'接口不存在'})
                self.reply(200,result)
            except Conflict as error:self.reply(409,{'error':str(error)})
            except PermissionError as error:self.reply(403,{'error':str(error)})
            except ProviderError as error:self.reply(502,{'error':str(error),'code':error.code})
            except (ValueError,ValidationError,KeyError,TypeError) as error:self.reply(400,{'error':str(error)[:240]})
            except Exception:self.reply(500,{'error':'本地智能体服务发生错误，请重试'})
        def log_message(self,format,*args):
            if not self.path.startswith('/api/'):super().log_message(format,*args)
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler);server.daemon_threads=True;server.engine=engine;server.settings=settings
    return server

def main():
    root=Path(__file__).resolve().parents[1];load_env(root/'.env')
    server=create_server(root,db_path=os.environ.get('AGENT_DB_PATH') or None,port=int(os.environ.get('AGENT_PORT','8765')))
    print(f'Local: http://127.0.0.1:{server.server_address[1]} | Agent: {server.engine.provider.origin}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close();server.engine.close()

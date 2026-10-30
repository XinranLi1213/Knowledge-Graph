"""Real follow-up acceptance through a configured local service, without credential access."""
import argparse
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

CASES=[
 ('class','COMM-DEMO-40','teacher','mixed_evidence','C02','这门课需要关注什么？请给出教师可以实际采取的教学措施。'),
 ('class','COMM-DEMO-40','teacher','mixed_evidence','C02','把刚才建议的短测具体写成两道建议题，给出评分要点，暂不提供完整答案。'),
 ('student','DEMO001','student','mixed_evidence','C09.K01','给我一道C语言整数除法与浮点转换的自测题，写出完整代码和两个要比较的表达式。先不给答案。'),
 ('student','DEMO001','student','mixed_evidence','C09.K02','给出刚才那道题的答案，尤其解释第二个表达式为什么会不同。'),
 ('student','DEMO001','teacher','course_totals_only','C07','根据当前证据，能断定哪个具体知识点薄弱吗？下一步应补什么测评？'),
 ('student','DEMO001','student','mixed_evidence','C05.K05','我还没学这个内容，应该怎么预习？请给一个具体的小任务。'),
 ('student','DEMO001','teacher','mixed_evidence','A04','这个分数现在能说明能力不合格吗？请说明依据和下一步如何补充证据。'),
 ('student','DEMO001','student','mixed_evidence','C02.K03','用一个具体简单例子解释小信号等效分析的步骤，不要复述我的全部得分。'),
 ('student','DEMO001','student','mixed_evidence','C02.K03','给刚才的例子出一道只改变一个条件的变式题，我先自己算，不要给答案。')]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8766);parser.add_argument('--output',default='real-followups-v2.json');parser.add_argument('--cases');args=parser.parse_args();base=f'http://127.0.0.1:{args.port}/api/agent/'
    def api(path,value=None):
        request=urllib.request.Request(base+path,data=json.dumps(value).encode() if value is not None else None,headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=20) as r:return json.load(r)
    file=Path(__file__).resolve().parents[1]/'review/agent-v5'/args.output
    saved=json.loads(file.read_text(encoding='utf-8')) if file.exists() else {'source':'real_configured_service','cases':[]}
    for index,case in enumerate(CASES):
        if args.cases and index not in [int(x) for x in args.cases.split(',')]:continue
        if any(x['case']==index and x['turn']['state']=='succeeded' for x in saved['cases']):continue
        typ,id,audience,scenario,node,question=case
        binding={'subject_type':typ,'subject_id':id,'audience':audience,'scenario':scenario,'node_id':node};query=urllib.parse.urlencode(binding)
        snapshot=api('snapshot?'+query);request=api('ask',{**binding,'question':question,'snapshot_ref':{'snapshot_id':snapshot['snapshot_id'],'revision':snapshot['revision']}})
        deadline=time.monotonic()+240
        while True:
            state=api('state?'+query);turn=next(t for t in state['turns'] if t['turn_id']==request['turn']['turn_id'])
            if turn['state'] not in ('queued','running'):break
            if time.monotonic()>deadline:raise SystemExit('请求仍在服务端运行，停止发新请求以避免重复计费')
            time.sleep(1)
        run=next((r for r in state['runs'] if r['run_id']==request['run']['run_id']),None)
        saved['cases'].append({'case':index,'binding':binding,'turn':turn,'run':run});file.write_text(json.dumps(saved,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'case':index,'node':node,'state':turn['state'],'usage':run['usage'] if run else None},ensure_ascii=False),flush=True)

if __name__=='__main__':main()

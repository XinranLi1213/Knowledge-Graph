"""Self-contained authored exercises with independently computed reference values."""
def examples(ctx):
    if not ctx.target:return []
    node=ctx.nodes[ctx.target];course=node.get('course_id') or ctx.target
    if course=='C09':
        return [{'id':'c-integer-division-v1','provenance':'authored_reference_verified_by_program','topic':'整数除法与浮点转换',
            'problem':'按C99及之后的规则，a=9,b=4且b始终非零。先预测再运行代码，比较p、q、r。只改变b为5作变式，不涉及除零或有符号溢出。',
            'code':'#include <stdio.h>\nint main(void) {\n    int a=9, b=4;\n    int p=a/b;\n    double q=a/b;\n    double r=(double)a/b;\n    printf("%d %.2f %.2f\\n",p,q,r);\n    return 0;\n}',
            'solution':{'p':9//4,'q':float(9//4),'r':9/4,'changed_b_5':{'p':9//5,'q':float(9//5),'r':9/5}},
            'check':'整数运算先发生，再进行赋值转换；浮点转换必须在除法前作用到操作数。'}]
    if course!='C02':return []
    vcc=12.;rb=560000.;rc=2000.;rl=10000.;beta=100.;vbe=.7;vt=.026
    ib=(vcc-vbe)/rb;ic=beta*ib;vce=vcc-ic*rc;rpi=beta*vt/ic
    gain=-beta*(rc*rl/(rc+rl))/rpi;variant=-beta*(rc*5000/(rc+5000))/rpi
    assert vce>vbe and vce>2 and abs(gain*.0005)<vce
    return [
        {'id':'diode-model-v1','provenance':'authored_reference_verified_by_program','topic':'半导体器件模型',
         'problem':'题1：5V直流源正端接1kΩ电阻，再接二极管阳极，阴极接电源负端；采用正向0.7V、反向截止的恒压降模型。求导通状态与电流。另给NPN三极管VE=0V、VB=0.7V、VC=6V，按两个结的偏置判断工作区。变式只把二极管电源5V改为0.4V，其余不变。',
         'solution':{'diode_current_A':(5-.7)/1000,'variant_current_A':0,'transistor_region':'基射结正偏、集基结反偏，处于放大区。'},
         'check':'题面给定模型，仅在所给近似下求解；评分看回路方向、导通假设、单位与工作区理由。'},
        {'id':'common-emitter-v1','provenance':'authored_reference_verified_by_program','topic':'小信号等效分析',
         'problem':'NPN固定偏置共射电路：发射极接地，VCC=12V，RB=560kΩ从VCC接基极，RC=2kΩ从VCC接集电极。RL=10kΩ经耦合电容接输出，直流开路、中频交流短路。β=100，VBE=0.7V，VT=26mV，忽略基区体电阻与输出电阻。输入是基极对地峰值0.5mV的小信号。先求IBQ、ICQ、VCEQ并检查VC>VB，再按rπ=βVT/ICQ、Av=-β(RC并联RL)/rπ求中频增益。变式只将RL改为5kΩ，其他参数全部保持。',
         'solution':{'IBQ_A':ib,'ICQ_A':ic,'VCEQ_V':vce,'rpi_ohm':rpi,'Av':gain,'variant_Av':variant,'variant_DC_unchanged':True},
         'check':'RL通过耦合电容接入，不改变直流工作点。原题与变式均在给定理想模型的放大区，基极小信号幅度远小于VT。必须完整交代连接和假设，不可换回历史中300kΩ/3kΩ的失效参数。'}]

def check_answer(value,ctx,question):
    if not question or not ctx.target:return
    import re
    course=ctx.nodes[ctx.target].get('course_id') or ctx.target;text=value['explanation']
    if course=='C02' and re.search(r'(?:RB|R_B|基极偏置电阻).{0,8}(?:只|仅).{0,8}直流',text):raise ValueError('RB也在交流输入通路中；只有基极理想电压输入的增益式可不显含RB，不能说RB只在直流通路')
    if course=='C09' and any(w in question for w in ('不给答案','不要给答案','不提供完整答案','自己算')) and re.search(r'(?:p|q|r|s|t)\s*[=:：]\s*\d+(?:\.\d+)?',text):raise ValueError('用户要求先不给答案，不能提前列出表达式的数值结果')
    if course=='C02' and any(w in question for w in ('不给答案','不要给答案','不提供完整答案','自己算')) and re.search(r'二极管截止|电流为零',text):raise ValueError('要求不给答案时，评分要点和附加说明也不能泄露二极管状态或数值；只列需检查的步骤与条件')
    if ctx.nodes[ctx.target]['level']=='L1_Ability' and re.search(r'能力.{0,15}(已评价知识点数为0|尚未拆到知识点)',text):raise ValueError('能力节点的child_knowledge_evaluated不适用；删除能力层已评价知识点数为0或尚未拆到知识点的断言，支撑课程有其自己的知识点评价，不能混淆')

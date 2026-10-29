from pathlib import Path
import json
root=Path(__file__).resolve().parents[1]
p=root/'src/app.js'
s=p.read_text(encoding='utf-8').replace('if(!e.active)simulation.alphaTarget(.1).restart();n.fx=n.x;n.fy=n.y;','n.dragged=false;').replace('n.fx=e.x;n.fy=e.y;','if(!n.dragged){simulation.alpha(.15).restart();n.dragged=true;}n.fx=e.x;n.fy=e.y;')
s=s.replace("new ResizeObserver(()=>{}).observe($('#graph'));",'')
p.write_text(s,encoding='utf-8')
p=root/'styles/app.css'
s=p.read_text(encoding='utf-8')
if '.node.selected .shape.risk' not in s:s+='\n.node.selected .shape.risk{stroke:#df743e;stroke-dasharray:5 3}\n.node text{font-size:12px}\n'
p.write_text(s,encoding='utf-8')
# Keep stable technical graph IDs; update all visible professional naming at its source.
p=root/'tools/build_review_data.py'
s=p.read_text(encoding='utf-8').replace('通信工程MVP合成教学数据','电子信息工程MVP合成教学数据').replace('用于通信工程演示课程群','用于电子信息工程演示课程群').replace('通信工程预置图谱展示契约','电子信息工程预置图谱展示契约')
s=s.replace("'critical_discrepancy':'全部截图为电子信息工程，不是通信工程。'","'source_confirmation':'全部截图为2024级电子信息工程培养方案。'")
p.write_text(s,encoding='utf-8')
p=root/'tools/verify_review_data.py'
s=p.read_text(encoding='utf-8').replace('来源：电子信息工程截图改编的通信工程演示，所有成绩和关系为模拟。','来源：2024级电子信息工程培养方案截图；知识点、教学关系与成绩为模拟。')
p.write_text(s,encoding='utf-8')
p=root/'review/执行方案.md'
s=p.read_text(encoding='utf-8').replace('通信工程专业图谱与班级诊断 MVP 执行方案（待审查）','电子信息工程专业图谱与班级诊断 MVP 执行方案（已审查）')
s=s.replace('版本：1.0 / 2026-10-29。状态：仅方案与数据已制作；界面开发、依赖安装和部署尚未开始。用户审查通过后才执行下列开发阶段。','版本：1.1 / 2026-10-29。状态：用户已审查通过，按第8节执行本地前端开发。')
start=s.index('用户提供的');end=s.index('18门演示课程')
s=s[:start]+'''用户提供的8张截图属于“2024级电子信息工程人才培养方案”。根据最新审查意见，展示名称统一为“电子信息工程（培养方案图谱演示）”，不再改编为通信工程。保留可核实的课程字段，知识点、教学关系与学情为模拟；界面只保留简洁的“预置教学数据”标识。工程设计与管理的学分和学期为模拟。

'''+s[end:]
s=s.replace('专业图谱 · 通信工程（改编演示）','专业图谱 · 电子信息工程（培养方案图谱演示）').replace('长期显示“模拟教学数据”标签，在来源说明中突出专业不匹配与改编说明。','底部保留“预置教学数据”标识，来源详情折叠在节点侧栏。')
s=s.replace('显示grey+insufficient_coverage。','显示grey+insufficient_coverage；若阶段性得分低于60，在诊断SVG中加橙红色虚线描边，保留灰色填充。')
s=s.replace('顶层显示模拟数据标识，出处说明承认源材料为电子信息工程，不伪造正式通信工程方案。','专业标题为电子信息工程，预置数据标识简洁，出处可在侧栏查看。')
s=s.replace('本轮只形成这些文件，等待用户审查。','审查已通过，继续按第8节实施；校验情况见前端验收记录.md。')
p.write_text(s,encoding='utf-8')

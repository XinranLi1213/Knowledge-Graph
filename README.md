# 电子信息工程（培养方案图谱演示）

HTML / CSS / JavaScript + 本地D3 7.9.0，配合Python本地诊断服务。无需npm安装或构建。当前默认使用明确标注的规则演示；可配置真实模型适配器。

在项目目录启动：

```powershell
python -m pip install -r requirements.txt
python tools/serve.py
```

浏览器打开 http://127.0.0.1:8765 。退出服务使用 Ctrl+C。请通过HTTP访问，不要直接双击index.html（浏览器会限制JSON文件读取）。

进入时选择教师端或学生演示。教师默认进入班级概览，可选择DEMO001–DEMO003查看个人图谱；学生选择模拟姓名与学号进入“我的技能树”，无需身份验证。顶部可切换角色、对象与三种评价场景。

保留结构拓扑/学情诊断；点击课程展开其知识点，双击节点固定或解锁，滚轮缩放，空白拖动平移，Esc取消选择。筛选框支持Ctrl/Command多选；“完整支撑链”与默认一阶邻域分别展示。“画像”按钮可收起/展开侧栏。

公共图谱、学生档案、评价快照、预置建议来自review/personalization-v2，以只读投影关联，成绩不在页面计算。教师侧栏展示帮扶与依据，学生侧栏展示复习和本地任务单；学习进度与评价覆盖分别显示。

灰色且阶段性低于60分的节点保留橙色虚线描边；只有课程总分时不反推知识点分数。切换对象/角色/场景保留布局和缩放。当前身份选择仅供演示，没有正式登录或正式建议候选采纳功能。

右下角“智能助手”支持自动诊断与继续追问。选中节点后自动绑定对象、角色、节点和评价版本；右侧节点面板同步显示诊断。教师在个人mixed_evidence场景选中C05，可点击“模拟C05补测”：程序更新事实并聚合，新解释异步生成。原回答保留历史版本标记，下一问默认最新评价。无关变化可复用已重新验证的解释，诊断刷新保留画布位置与缩放。

运行快照、事件、解释、任务和对话保存在.runtime/agent.sqlite3；重启保留，原预置JSON不被修改。个人补测不自动重写预置班均。启动参数与完整快照提交接口见[运行协议](review/agent-v3/运行协议与接口.md)。服务仅监听本机；演示角色选择不能充当正式多用户鉴权。

接入真实模型：将.env.example复制为.env，设置AGENT_PROVIDER=openai、OPENAI_API_KEY、AGENT_MODEL后重启。适配器使用OpenAI结构化输出与有限只读工具；密钥只在服务端。本次未配置密钥，没有发起真实模型请求；已验证的是规则闭环及模型模拟传输。显式模型模式失败会显示失败，不悄悄切换成规则回答。

校验：

```powershell
node --test tests/graph.test.js tests/personalization.test.js
python -m unittest discover -s tests -p test_agent.py -v
python tools/verify_review_data.py
python tools/verify_personalization_review.py --allow-frontend-changes
node tools/browser_agent.cjs
```

Python数据校验需要jsonschema。离线重新制作数据可运行tools/build_review_data.py（依赖原截图目录），仅用于维护预设文件，不是应用运行步骤。

tools/browser_agent.cjs自启隔离临时服务与数据库，强制使用规则演示并在结束后关闭服务，验证自动诊断、补测更新、版本绑定和桌面/手机抽屉。tools/browser_personalization.cjs覆盖既有个性化界面，运行前先启动本地服务。两者使用本机Codex运行时的Playwright及本机Chrome；其他机器需相应调整路径。tools/browser_check.cjs是v0.1班级界面的历史脚本。

新增四类契约、执行方案和验收记录见[agent-v3](review/agent-v3/README.md)；D3许可证见vendor/D3-LICENSE。本轮未部署线上站点。

## Git 版本管理

当前项目使用本地Git管理，班级基线标记为 `v0.1.0`，个性化图谱版本标记为 `v0.2.0`，事件驱动诊断版本为 `v0.3.0`。代码、预置数据、审查文档及界面截图均保存；运行库、依赖目录、缓存和环境密钥文件不纳入版本。

每次修改后，可检查差异并保存一个版本：

```powershell
git status
git diff
git add .
git diff --cached
git commit -m "描述本次修改"
```

查看历史版本或某个文件的旧内容（将提交号替换为实际值）：

```powershell
git log --oneline --decorate
git log --oneline -- src/app.js
git show v0.1.0:src/app.js
git show 提交号:src/app.js
git diff v0.1.0 HEAD -- src/app.js
```

`git show` 和 `git diff` 只查看内容，不覆盖当前文件。后续开发建议先创建分支，例如 `git switch -c codex/improve-graph`。本地提交不会自动上传；当前未配置远程仓库。

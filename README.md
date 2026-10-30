# 电子信息工程（培养方案图谱演示）

HTML / CSS / JavaScript + 本地D3 7.9.0，配合Python本地诊断服务。无需npm安装或构建。默认只读浏览；可在智能助手内选择DeepSeek或OpenAI，启用生成与追问。

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

右下角“智能助手”标题栏有“API 设置”，在同一抽屉内切换设置页，不改变画布。先选择供应商（DeepSeek/OpenAI），再输入模型名称与对应密钥，点击“测试并启用”。DeepSeek默认提示deepseek-flash，也可填写账户可用的其他模型；接口地址按供应商自动显示。该操作发送DEMO001/C05演示上下文，校验输出并产生少量API用量。切换供应商清空输入密钥，服务端禁止跨供应商沿用旧密钥。配置只存在当前服务内存，重启清除，作用于本机服务所有模拟角色。密码提交后清空，不回填、不写浏览器存储。

未配置时可以看原静态数据和已有模型诊断，不能继续追问或重新生成。配置后可点击“生成诊断”与发送问题。浏览已有结果或点击新节点本身不产生模型费用。选中节点自动绑定对象、角色、节点和评价版本；评价更新时，有API才按依赖异步刷新。旧回答保留历史版本标记；移除密钥或换模型不会使仍匹配事实的诊断失效。教师个人mixed_evidence场景可“模拟C05补测”，无API时只更新事实并将受影响诊断标旧。

运行快照、事件、解释、任务和对话保存在.runtime/agent.sqlite3；重启保留，原预置JSON不被修改。API设置中的“保存为静态成果”将有效模型诊断及必要评价/来源记录导出到review/model-diagnostics，供无密钥的其他本地安装浏览，不含私人对话或密钥。个人补测不自动重写预置班均。当前接口见[运行协议](review/agent-v4/运行协议与验收.md)。服务仅监听本机；演示角色选择不能充当正式多用户鉴权。

也可将.env.example复制为.env：DeepSeek配置AGENT_PROVIDER=deepseek、DEEPSEEK_API_KEY、AGENT_MODEL=deepseek-flash；OpenAI配置AGENT_PROVIDER=openai、OPENAI_API_KEY和可用的AGENT_MODEL。重启后界面标为“尚未测试”，可留空密钥测试同一供应商的现有配置。本次环境没有密钥，未发起真实模型请求、未制作真实模型成果；成果清单如实为空。已验证的是完整模拟传输与只读闭环。真实调用失败会显示错误，不切换成规则回答。供应商适配细节见[多供应商配置](review/多供应商API配置.md)。

校验：

```powershell
node --test tests/graph.test.js tests/personalization.test.js
python -m unittest discover -s tests -p 'test_*.py' -v
python tools/verify_review_data.py
python tools/verify_personalization_review.py --allow-frontend-changes
node tools/browser_api_config.cjs
python tools/model_diagnostics.py validate
```

Python数据校验需要jsonschema。离线重新制作数据可运行tools/build_review_data.py（依赖原截图目录），仅用于维护预设文件，不是应用运行步骤。

tools/browser_api_config.cjs自启隔离服务和临时数据库，使用模拟模型传输，验证设置、追问、补测、断开与手机界面；结束后关闭服务，不调用外部模型。tools/browser_agent.cjs保留为同一检查的兼容入口，v0.3规则追问脚本可从Git旧版本查看。tools/browser_personalization.cjs覆盖既有个性化界面，运行前先启动本地服务。浏览器检查依赖本机Codex运行时的Playwright及本机Chrome；其他机器需相应调整路径。

API配置、契约扩展和验收见[agent-v4](review/agent-v4/运行协议与验收.md)；先前四类契约见[agent-v3](review/agent-v3/README.md)。D3许可证见vendor/D3-LICENSE。本轮未部署线上站点。

## Git 版本管理

当前项目使用本地Git管理，班级基线 `v0.1.0`，个性化图谱 `v0.2.0`，事件诊断 `v0.3.0`，API设置与静态成果 `v0.4.0`，DeepSeek/OpenAI多供应商配置 `v0.4.1`。运行库、依赖目录、缓存和环境密钥文件不纳入版本。

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

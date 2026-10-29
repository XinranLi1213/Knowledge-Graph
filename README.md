# 电子信息工程（培养方案图谱演示）

静态前端：HTML / CSS / JavaScript + 本地D3 7.9.0。无需npm安装或构建，无后端API与大模型。

在项目目录启动：

```powershell
python tools/serve.py
```

浏览器打开 http://127.0.0.1:8765 。退出服务使用 Ctrl+C。请通过HTTP访问，不要直接双击index.html（浏览器会限制JSON文件读取）。

进入时选择教师端或学生演示。教师默认进入班级概览，可选择DEMO001–DEMO003查看个人图谱；学生选择模拟姓名与学号进入“我的技能树”，无需身份验证。顶部可切换角色、对象与三种评价场景。

保留结构拓扑/学情诊断；点击课程展开其知识点，双击节点固定或解锁，滚轮缩放，空白拖动平移，Esc取消选择。筛选框支持Ctrl/Command多选；“完整支撑链”与默认一阶邻域分别展示。“画像”按钮可收起/展开侧栏。

公共图谱、学生档案、评价快照、预置建议来自review/personalization-v2，以只读投影关联，成绩不在页面计算。班级通用教师文案通过旧数据适配保留。教师侧栏展示帮扶与依据，学生侧栏展示复习和本地任务单；学习进度与评价覆盖分别显示。

灰色且阶段性低于60分的节点保留橙色虚线描边；只有课程总分时不反推知识点分数。切换对象/角色/场景保留布局和缩放。当前没有正式登录、真实API、LLM调用或候选发布功能。

校验：

```powershell
node --test tests/graph.test.js tests/personalization.test.js
python tools/verify_review_data.py
python tools/verify_personalization_review.py --allow-frontend-changes
```

Python数据校验需要jsonschema。离线重新制作数据可运行tools/build_review_data.py（依赖原截图目录），仅用于维护预设文件，不是应用运行步骤。

浏览器检查脚本tools/browser_personalization.cjs覆盖当前个性化界面，使用本机Codex运行时的Playwright及本机Chrome；运行前先启动本地服务。其他机器需相应调整浏览器和Playwright路径。tools/browser_check.cjs是v0.1班级界面的历史脚本，保留作历史验证记录。

数据契约与审查记录见review目录；D3许可证见vendor/D3-LICENSE。本轮未部署线上站点。

## Git 版本管理

当前项目使用本地Git管理，班级基线标记为 `v0.1.0`，个性化图谱版本标记为 `v0.2.0`。代码、预置数据、审查文档及界面截图均保存；依赖目录、缓存和环境密钥文件不纳入版本。

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

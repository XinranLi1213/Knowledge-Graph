# 电子信息工程（培养方案图谱演示）

静态前端：HTML / CSS / JavaScript + 本地D3 7.9.0。无需npm安装或构建，无后端API与大模型。

在项目目录启动：

```powershell
python tools/serve.py
```

浏览器打开 http://127.0.0.1:8765 。退出服务使用 Ctrl+C。请通过HTTP访问，不要直接双击index.html（浏览器会限制JSON文件读取）。

默认展示阶段性评价场景。顶部切换结构拓扑/学情诊断与三种评价场景；点击课程展开其知识点，双击节点固定或解锁，滚轮缩放，空白拖动平移，Esc取消选择。筛选框支持Ctrl/Command多选；“完整支撑链”与默认一阶邻域分别展示。

成绩、覆盖率、颜色直接读取 review/data 中的预置JSON，不在页面计算。灰色且阶段性低于60分的节点，在诊断模式以橙色虚线描边；只有课程总分时不反推知识点分数。学生端未实现。

校验：

```powershell
node --test tests/graph.test.js
python tools/verify_review_data.py
```

Python数据校验需要jsonschema。离线重新制作数据可运行tools/build_review_data.py（依赖原截图目录），仅用于维护预设文件，不是应用运行步骤。

浏览器检查脚本 tools/browser_check.cjs 使用本机Codex运行时的Playwright及本机Chrome；运行前先启动本地服务。其他机器需相应调整浏览器和Playwright路径。

数据契约与审查记录见review目录；D3许可证见vendor/D3-LICENSE。本轮未部署线上站点。

## Git 版本管理

当前项目使用本地Git管理，基线版本标记为 `v0.1.0`。代码、预置数据、审查文档及界面截图均保存；依赖目录、缓存和环境密钥文件不纳入版本。

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

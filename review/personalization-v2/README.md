# 个性化图谱审查包 v2

本目录是下一阶段的契约、模拟数据与实施方案，未接入现有前端。

建议阅读顺序：

1. [数据契约与关系说明](数据契约与关系说明.md)：学生契约与原节点契约的联系、差异及字段定义。
2. [数据审查概览](数据审查概览.md)：数据规模、DEMO001–003的实际预置值与文件位置。
3. [LLM建议读写协议](LLM建议读写协议.md)：未来如何读取依据、交付并版本化更新建议。
4. [实施方案](实施方案.md)：审查后才执行的前端开发阶段与验收要求。
5. [建议评估与数据组合器设计](建议评估与数据组合器设计.md)：本次建议的采用边界、DataStore/LayoutStore、stroke_style和裁剪模式。

重点样例：

- data/graph.json：唯一公共图谱。
- data/students.json：40名模拟学生档案。
- data/snapshots/student/DEMO001/mixed_evidence.json：个人阶段评价。
- data/recommendations/DEMO001/mixed_evidence.json：教师与学生分别使用的预置建议。
- examples/llm-context-teacher.json、examples/llm-context-student-C05.json：教师/学生的C05一阶局部诊断输入。
- examples/llm-context-student.json：学生总体画像摘要输入。
- examples/recommendation-update-candidate.json：未应用的建议更新候选。
- examples/recommendation-update-overview-candidate.json：未应用的学生总体建议更新候选。
- contracts/contract.schema.json：8类记录的JSON Schema。
- contracts/recommendation-update.provider.schema.json：面向提供方输出子集的示例Schema（仅离线检查，未调用API）。
- validation-report.json：本轮离线数据验证结果。

在项目根目录可运行 `python tools/verify_personalization_review.py` 复核数据；依赖jsonschema。`tools/build_personalization_review.py` 只从已有JSON制作本包，不依赖原截图、不改旧文件、不是前端运行依赖。

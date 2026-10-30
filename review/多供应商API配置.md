# DeepSeek / OpenAI多供应商配置 v0.4.1

2026-10-30。保留现有静态数据、已保存诊断、事实指纹和只读浏览。供应商选择放在原API设置页，不新增主界面布局。

## 使用DeepSeek

启动或重启python tools/serve.py，在“智能助手 → API设置”选择DeepSeek。接口地址自动显示https://api.deepseek.com/chat/completions，默认模型deepseek-flash，提示deepseek-v4-pro，也可手动填写账户可用的模型名称。填写DeepSeek官方平台密钥，点击“测试并启用”；通过后生成诊断或继续追问。

本次以2026-10-30读取的[DeepSeek官方调用文档](https://api-docs.deepseek.com/)为准，模型建议来自该文档，未将旧模型别名硬编码为当前默认模型。若使用第三方托管平台的密钥，需要对应平台的端点适配，本轮两个入口均为供应商官方接口。

环境配置替代方式：将.env.example复制为.env并填写：

```dotenv
AGENT_PROVIDER=deepseek
DEEPSEEK_API_KEY=填写本机密钥
AGENT_MODEL=deepseek-flash
```

OpenAI继续使用AGENT_PROVIDER=openai、OPENAI_API_KEY及可用AGENT_MODEL。DeepSeek不会读取OPENAI_API_KEY；跨供应商切换不能留空沿用另一家的密钥。界面切换供应商时清空密码，预填对应默认模型和模型建议；模型可编辑，接口地址只读。新配置测试失败保留原配置，断开后保存的模型结果仍可浏览。

## 协议差异

| 项目 | OpenAI | DeepSeek |
|---|---|---|
| 请求地址 | https://api.openai.com/v1/chat/completions | https://api.deepseek.com/chat/completions |
| 终答格式 | response_format=json_schema | response_format=json_object |
| 输出上限参数 | max_completion_tokens | max_tokens |
| 函数定义 | strict=true | 使用正式接口工具定义，不发送Beta专属strict |
| 思考模式 | 保留原适配 | thinking.type=disabled，保持当前延迟与输出预算 |
| 结果接收 | 项目Schema与引用校验 | 项目Schema与引用校验 |

DeepSeek Chat Completions的JSON模式保证JSON格式，不等同于供应商强制执行项目Schema。服务端仍检查完整字段、对象作用域、节点/证据/资源引用与长度，拒绝空答、截断、非法JSON或不合约输出，不用正则提取答案，不悄悄切成规则回答。相关行为依据[JSON Output文档](https://api-docs.deepseek.com/guides/json_mode/)和[工具调用文档](https://api-docs.deepseek.com/guides/tool_calls/)。

工具循环仅回传role/content/tool_calls，不把思考正文作为历史对话或保存的诊断。保留单任务最多4次模型调用、6次只读工具与原上下文预算。补充400参数/模型不兼容、402余额不足等错误提示。生成来源、agent_run与conversation_turn中的供应商和模型均来自本次实际适配实例；切换供应商不使仍匹配事实的旧诊断失效。

## 扩展方式与验收

供应商目录集中在agent/provider.py的PROVIDERS，配置能力判断使用origin=model，不再在引擎中硬编码OpenAI。新增供应商应增加目录项、独立密钥环境变量与实际请求格式适配，并验证工具、终答和引用约束；不能仅换网址并承诺所有接口兼容。

30项后台测试、13项前端测试和浏览器检查通过。新增覆盖DeepSeek JSON/工具循环、官方端点及密钥隔离、环境配置默认值、跨供应商切换与旧结果复用；浏览器验证默认DeepSeek、供应商切换清密码、对应地址、测试启用、诊断/追问、断开保留结果、手机无溢出与坐标缩放不变。截图见api-settings-desktop.png与api-settings-mobile.png。

本机无DEEPSEEK_API_KEY或.env，没有真实外部API调用；上述调用测试使用隔离模拟传输。有效密钥应通过本机设置页输入，不需要在聊天中提供。现有模型成果清单仍为空，没有用测试文本替代真实模型成果。

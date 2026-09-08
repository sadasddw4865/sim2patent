# sim2patent —— 变更记录

## [0.1.0] - 2025

首个可发布版本:仿真结果(CSV/JSON)到专利 agent 交接件的桥接流水线。

- 解析适配器:规范/宽松 JSON、CSV;参数/指标列自动分类,可 `--param-cols` 覆盖
- 发明点挖掘与技术交底生成:DeepSeek(OpenAI 兼容)两阶段 LLM,JSON 契约校验 + 自动重试
- 离线 mock:无 API key / `--mock` 时可端到端运行,全部测试离线
- 数值可溯源:提示词强制引用数据摘要真实数值,输出带数据证据/置信度/风险
- 交接协议:PatentAgentPort + handoff JSON(仿真/分析/交底全量结构化数据)
- CLI:裸用法、`run`/`parse` 子命令;产物:交底书.md / 创新点清单.md / handoff_*.json

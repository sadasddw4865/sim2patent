"""sim2patent —— 仿真 agent 结果 → 专利 agent 输入的桥接 agent。

流水线:仿真结果(CSV/JSON) -> 结构化解析 -> LLM 发明点识别
        -> 技术交底书 + 创新点清单 -> 交接到(未来的)专利 agent。
"""

__version__ = "0.1.0"

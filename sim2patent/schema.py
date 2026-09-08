"""sim2patent.schema —— 数据模型。

整条链路在三种对象间流动:

  SimulationResult  (解析器从 CSV/JSON 还原出的结构化仿真结果)
        |  analyze 阶段(LLM,基于数据摘要)
        v
  InventionAnalysis (发明点候选清单 + 分析小结)
        |  disclose 阶段(LLM)
        v
  TechnicalDisclosure (技术交底书结构化字段,渲染成 .md 手稿)

所有对象都可经 to_dict() 无损序列化,便于落盘、人工审核和
后续专利 agent 以 JSON 形式消费。
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


# --------------------------------------------------------------------------
# 第一段:仿真结果
# --------------------------------------------------------------------------

@dataclass
class SimParam:
    """一个设计/工况参数。value 保留原始字符串,便于承载范围如 '0.05-0.4'。"""

    name: str
    value: str
    unit: str = ""
    role: str = "design"          # design(设计变量) | condition(工况) | constant(常量)
    note: str = ""


@dataclass
class SimMetric:
    """一个结果评价指标。baseline_value 指对照方案下的取值(如有)。"""

    name: str
    value: float
    unit: str = ""
    baseline_value: Optional[float] = None
    better_direction: str = ""    # higher | lower
    design_point: str = ""        # 关联的设计点 id(留空表示汇总指标)
    note: str = ""


@dataclass
class DesignPoint:
    """一行仿真记录:一组参数取值 -> 一组指标取值。"""

    id: str
    params: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    is_baseline: bool = False
    note: str = ""


@dataclass
class SimulationResult:
    """结构化后的仿真输出(整份输入文件的语义等价物)。"""

    title: str = ""
    objective: str = ""           # 这次仿真想回答的工程问题
    baseline: str = ""            # 对比基准/现有方案的描述
    parameters: list[SimParam] = field(default_factory=list)
    metrics: list[SimMetric] = field(default_factory=list)
    design_points: list[DesignPoint] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    source_file: str = ""
    raw: dict[str, Any] = field(default_factory=dict)   # 原始输入副本,便于追溯

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------
# 第二段:发明点分析
# --------------------------------------------------------------------------

@dataclass
class InventionPoint:
    """一个候选发明点。所有声称都应有 supporting_evidence 指向数据。"""

    title: str
    category: str = ""            # 结构 | 参数组合 | 工艺 | 控制策略 | 材料 | 算法 | 其他
    novelty_argument: str = ""    # 相对现有方案的差异 / 为什么可能新颖
    technical_effect: str = ""    # 带来的技术效果(尽量量化)
    supporting_evidence: list[str] = field(default_factory=list)  # 指标名 + 设计点/数据
    claim_direction: str = ""     # 建议的权利要求展开方向(留给专利 agent 的线索)
    confidence: float = 0.0       # 0-1,数据支撑强度的主观估计
    concern: str = ""             # 不确定性/风险(如样本不足、仅单一工况验证)


@dataclass
class InventionAnalysis:
    """analyze 阶段产物:发明点清单与分析小结。"""

    summary: str = ""
    points: list[InventionPoint] = field(default_factory=list)
    model: str = ""               # 记录由哪个模型生成,便于追溯

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------
# 第三段:技术交底书
# --------------------------------------------------------------------------

@dataclass
class TechnicalDisclosure:
    """disclose 阶段产物:结构化交底书字段(渲染后即 .md 手稿)。"""

    title: str = ""
    technical_field: str = ""             # 技术领域
    background_problem: str = ""          # 要解决的技术问题(背景)
    prior_art_shortcomings: str = ""      # 现有技术及其不足
    solution_summary: str = ""            # 技术方案概述
    embodiments: list[str] = field(default_factory=list)   # 实施例(带具体数值)
    technical_effects: list[str] = field(default_factory=list)  # 技术效果(带仿真数据)
    innovation_points: list[str] = field(default_factory=list)  # 从创新点清单挑选汇总
    design_space_note: str = ""           # 参数范围/可实施范围说明
    data_basis: list[str] = field(default_factory=list)    # 支撑数据的来源说明
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------
# 汇总报告
# --------------------------------------------------------------------------

@dataclass
class BridgeReport:
    """一次 run 的完整产出。"""

    input_path: str
    simulation: SimulationResult
    analysis: InventionAnalysis
    disclosure: TechnicalDisclosure
    handoff_json_path: str = ""     # 交给专利 agent 的 JSON 交接文件
    disclosure_md_path: str = ""    # 交底书 .md 手稿
    innovation_md_path: str = ""    # 创新点清单 .md
    used_mock: bool = False

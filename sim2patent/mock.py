"""sim2patent.mock —— 离线确定性实现(不调用任何 LLM)。

用途:
1. 无 DEEPSEEK_API_KEY 时让整条流水线仍可跑通(--mock);
2. 单元测试不依赖网络;
3. 作为"预期行为下限",供对照真实 LLM 输出质量。

实现方式:对指标做 基线->最优 的增量统计,按类别模板生成
发明点与技术效果。只描述数据里真实存在的差异,不发明数值。
"""
from __future__ import annotations

from typing import Optional

from .schema import (
    InventionAnalysis,
    InventionPoint,
    SimulationResult,
    TechnicalDisclosure,
)


def _delta_text(name: str, best: float, base: Optional[float], direction: str = "") -> str:
    if base is None or abs(base) < 1e-12:
        return f"{name} 最优取值 {best}"
    d = best - base
    pct = d / abs(base) * 100.0
    if direction == "lower":
        word = "降低" if d < 0 else "升高"
    elif direction == "higher":
        word = "提升" if d > 0 else "下降"
    else:
        word = "变化"
    return f"{name}{word} {abs(pct):.1f}%(由 {base} 至 {best})"


def _direction_word(delta: float, direction: str) -> tuple[str, Optional[bool]]:
    """返回 (动词, 是否改善)。direction 未知时 improvement=None。"""
    if direction == "lower":
        return ("降低" if delta < 0 else "升高"), delta < 0
    if direction == "higher":
        return ("提升" if delta > 0 else "下降"), delta > 0
    return ("变化", None)


def analyze_mock(sim: SimulationResult) -> InventionAnalysis:
    """从指标汇总表构造最朴素的候选发明点。"""
    points: list[InventionPoint] = []
    evidence: list[str] = []
    for m in sim.metrics:
        if m.baseline_value is None:
            continue
        evidence.append(_delta_text(m.name, m.value, m.baseline_value, m.better_direction))
    if not evidence:
        evidence = [f"采集到 {len(sim.design_points)} 组设计点、{len(sim.metrics)} 项指标"]

    # 找到相对变化幅度最大的指标作为主发明点素材
    ranked = sorted(
        (m for m in sim.metrics if m.baseline_value is not None and abs(m.baseline_value) > 1e-12),
        key=lambda m: abs((m.value - m.baseline_value) / m.baseline_value),
        reverse=True,
    )
    for i, m in enumerate(ranked[:2]):
        d = m.value - m.baseline_value
        pct = d / abs(m.baseline_value) * 100.0
        word, improved = _direction_word(d, m.better_direction)
        quality = "改善" if improved else ("恶化" if improved is False else "变化")
        note = f"({m.note})" if m.note else ""
        points.append(
            InventionPoint(
                title=f"以{_short(m.name)}为目标的参数/结构协同改进",
                category="参数组合",
                novelty_argument=(
                    f"通过调整仿真设计变量组合,使{m.name}相对基线{word}约{abs(pct):.1f}%;"
                    "相对现有方案的差异点需人工确认。"
                ),
                technical_effect=f"{m.name}{word}约 {abs(pct):.1f}%,效果呈{quality}方向{note}",
                supporting_evidence=[
                    _delta_text(m.name, m.value, m.baseline_value, m.better_direction)
                ],
                claim_direction=f"围绕{m.name}的取值区间与结构参数组合撰写从属权利要求",
                confidence=0.3,
                concern="离线模板生成,未做新颖性检索与实施例核对,仅作占位。",
            )
        )

    if not points:
        points.append(
            InventionPoint(
                title="参数范围与最优组合的记录",
                category="其他",
                novelty_argument="差异点待人工/LLM 分析确认。",
                technical_effect="记录最优设计点对应的指标表现。",
                supporting_evidence=evidence,
                confidence=0.1,
                concern="缺少基线对比,数据不足以支撑发明点。",
            )
        )

    return InventionAnalysis(
        summary="(离线 mock)仅做了指标增量的确定性统计,未做语义化发明点挖掘。",
        points=points,
        model="mock",
    )


def _short(name: str) -> str:
    return name if len(name) <= 12 else name[:12] + "…"


def disclose_mock(sim: SimulationResult, analysis: InventionAnalysis) -> TechnicalDisclosure:
    """把解析结果与 mock 分析直接排版成结构化交底书。"""
    effects: list[str] = []
    for p in analysis.points:
        effects.append(f"- {p.technical_effect}(依据:{'; '.join(p.supporting_evidence)})")
    embodiments = [
        f"- 实施例 N:采用 {', '.join(dp.params.values()) if dp.params else '(参数见附表)'} "
        f"的参数组合,{', '.join(f'{k}={v}' for k, v in dp.metrics.items())}"
        for dp in sim.design_points[:5]
    ]
    field_ = sim.title or "工程技术仿真"
    return TechnicalDisclosure(
        title=f"{field_}相关的结构/参数改进",
        technical_field=field_,
        background_problem=sim.objective or "需基于仿真数据整理技术问题",
        prior_art_shortcomings=sim.baseline or "未提供现有方案描述(待补充)",
        solution_summary="根据仿真数据中改善幅度最大的指标选取改进方向;具体技术手段待 LLM/人工补全。",
        embodiments=embodiments or ["- (待补充实施例)"],
        technical_effects=effects or ["- (待补充技术效果)"],
        innovation_points=[p.title for p in analysis.points],
        design_space_note="参数取值空间以输入数据中的范围为准(见附表);超出数据覆盖的范围需另行仿真验证。",
        data_basis=[f"来源文件:{sim.source_file}", f"共 {len(sim.design_points)} 个设计点"],
        model="mock",
    )

"""sim2patent.utils —— 小工具:把 SimulationResult 压缩成 LLM 友好的数据摘要。"""
from __future__ import annotations

from .schema import SimulationResult


def fmt_num(x: float) -> str:
    return f"{x:.4g}"


def build_data_digest(sim: SimulationResult, max_points: int = 60) -> str:
    """把解析结果渲染成紧凑文本(限制体量,防超长;行数封顶)。"""
    parts: list[str] = []
    if sim.title:
        parts.append(f"## 标题\n{sim.title}")
    if sim.objective:
        parts.append(f"## 仿真目标\n{sim.objective}")
    if sim.baseline:
        parts.append(f"## 对比基准(现有方案)\n{sim.baseline}")
    if sim.parameters:
        parts.append("## 设计/工况参数")
        for p in sim.parameters:
            parts.append(f"- {p.name}: {p.value} {p.unit} [{p.role}]")
    if sim.metrics:
        parts.append("## 指标汇总(基线->最优)")
        for m in sim.metrics:
            base = fmt_num(m.baseline_value) if m.baseline_value is not None else "-"
            parts.append(f"- {m.name}: {fmt_num(m.value)} {m.unit}(基线 {base})")
    if sim.design_points:
        parts.append("## 设计点明细(截断显示)")
        shown = sim.design_points[:max_points]
        for dp in shown:
            tag = "[基线]" if dp.is_baseline else ""
            params = " ".join(f"{k}={v}" for k, v in dp.params.items())
            metrics = " ".join(f"{k}={fmt_num(v)}" for k, v in dp.metrics.items())
            parts.append(f"- {dp.id}{tag} | {params} | {metrics}")
        if len(sim.design_points) > max_points:
            parts.append(f"(其余 {len(sim.design_points) - max_points} 行已省略)")
    if sim.notes:
        parts.append("## 解析备注\n" + "\n".join(f"- {n}" for n in sim.notes))
    return "\n".join(parts)

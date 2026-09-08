"""sim2patent.render —— 把结构化产物渲染成可审阅的 Markdown。"""
from __future__ import annotations

from .schema import InventionAnalysis, SimulationResult, TechnicalDisclosure


def render_innovation_md(sim: SimulationResult, analysis: InventionAnalysis) -> str:
    lines: list[str] = [
        "# 创新点清单(仿真数据挖掘)",
        "",
        f"> 来源: `{sim.source_file}` | 模型: `{analysis.model}`",
        "",
        "## 小结",
        "",
        analysis.summary or "(无)",
        "",
        "## 候选发明点",
        "",
    ]
    for i, p in enumerate(analysis.points, 1):
        lines += [
            f"### {i}. {p.title}",
            "",
            f"- **类别**: {p.category or '-'}",
            f"- **新颖性理由**: {p.novelty_argument or '-'}",
            f"- **技术效果**: {p.technical_effect or '-'}",
            f"- **数据证据**:",
        ]
        lines += [f"  - {e}" for e in p.supporting_evidence] or ["  - (无)"]
        lines += [
            f"- **建议展开方向(给专利 agent)**: {p.claim_direction or '-'}",
            f"- **支撑置信度**: {p.confidence:.2f}",
            f"- **风险/待验证**: {p.concern or '-'}",
            "",
        ]
    return "\n".join(lines)


def render_disclosure_md(
    sim: SimulationResult,
    analysis: InventionAnalysis,
    doc: TechnicalDisclosure,
) -> str:
    def section(title: str, body: str) -> list[str]:
        return [f"## {title}", "", body or "(待补充)", ""]

    lines: list[str] = [
        f"# {doc.title or '技术交底书(草稿)'}",
        "",
        f"> 本文档由仿真结果自动生成,属**草稿**;提交专利前须经工程师/专利代理师核实数值与实施例。",
        f"> 模型: `{doc.model}` | 数据来源: `{sim.source_file}`",
        "",
    ]
    lines += section("一、技术领域", doc.technical_field)
    lines += section("二、要解决的技术问题", doc.background_problem)
    lines += section("三、现有技术及其不足", doc.prior_art_shortcomings)
    lines += section("四、技术方案概述", doc.solution_summary)

    lines += ["## 五、实施例", ""]
    lines += [f"{e}" for e in doc.embodiments] or ["(待补充)"]
    lines += [""]

    lines += ["## 六、技术效果(数据支撑)", ""]
    lines += [f"{e}" for e in doc.technical_effects] or ["(待补充)"]
    lines += [""]

    lines += ["## 七、核心创新点", ""]
    for p in doc.innovation_points:
        lines.append(f"- {p}")
    lines += [""]

    lines += section("八、可实施范围说明", doc.design_space_note)
    lines += ["## 九、数据依据", ""]
    lines += [f"- {b}" for b in doc.data_basis] or ["(待补充)"]
    lines += [""]

    lines += ["---", "", "### 附录:候选发明点一览", ""]
    for i, p in enumerate(analysis.points, 1):
        lines.append(f"- [{i}] {p.title} —— {p.technical_effect or '-'}")
    return "\n".join(lines)

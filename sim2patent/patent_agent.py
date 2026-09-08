"""sim2patent.patent_agent —— 通往"专利 agent"的交接端口。

本桥接 agent 的职责到此为止:产出《技术交底书 + 创新点清单》,
然后交给专利 agent。本模块定义交接协议与默认实现:

- PatentAgentPort:专利 agent 应当实现的接口协议;
- HandoffPatentAgent:默认实现 —— 把结构化 JSON + Markdown 落到磁盘,
  即"把交接件放在共享目录",供真实专利 agent(或人工)取用;
- 真实专利 agent(例如用 LLM 把交底书写成权利要求书)可在后续实现
  PatentAgentPort,通过 make_patent_agent(kind=...) 接入,桥接侧零改动。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .schema import BridgeReport


class PatentAgentPort(Protocol):
    """专利 agent 的接口协议(实现方:未来的权利要求撰写 agent)。"""

    def consume(self, report: BridgeReport) -> str:
        """接收桥接产出,返回专利 agent 的产物摘要/路径。"""
        ...


@dataclass
class HandoffFile:
    """一次交接落盘的文件集合。"""

    handoff_json: Path
    disclosure_md: Path
    innovation_md: Path


@dataclass
class HandoffPatentAgent:
    """默认实现:把交接件写成文件。这是桥接 agent 的终点。"""

    out_dir: Path

    def consume(self, report: BridgeReport) -> str:
        self._ensure(report)
        return (
            f"交接完成。产物:\n"
            f"  - 交接 JSON: {report.handoff_json_path}\n"
            f"  - 交底书:   {report.disclosure_md_path}\n"
            f"  - 创新点:   {report.innovation_md_path}"
        )

    @staticmethod
    def _ensure(report: BridgeReport) -> None:
        # 依赖 bridge 已填好路径;若为空则视为未落盘,直接报错避免静默丢失
        if not (report.handoff_json_path and report.disclosure_md_path and report.innovation_md_path):
            raise RuntimeError("交接文件尚未生成,请先运行 bridge.run()")


def make_patent_agent(kind: str, out_dir: str | Path) -> PatentAgentPort:
    """工厂。目前仅 handoff;后续可扩展 'claims'(真实权利要求撰写 agent)。"""
    out = Path(out_dir)
    if kind == "handoff":
        return HandoffPatentAgent(out)
    raise ValueError(f"未知专利 agent 类型: {kind}(当前支持: handoff)")


# --------------------------------------------------------------------------
# 交接 JSON 的结构说明(给专利 agent 的契约文档,纯注释)
# --------------------------------------------------------------------------
HANDOFF_SCHEMA_DOC = """交接文件(sim2patent_handoff_*.json)顶层结构:
{
  "meta":            {"generator": "sim2patent", "model": ..., "input": ...},
  "simulation":      {...SimulationResult.to_dict()...},
  "analysis":        {...InventionAnalysis.to_dict()...(含 points)},
  "disclosure":      {...TechnicalDisclosure.to_dict()...}
}
真实专利 agent 实现 PatentAgentPort 后,可直接读取 disclosure + analysis.points
撰写权利要求书;所有数值均应追溯到 simulation.design_points / metrics。
"""

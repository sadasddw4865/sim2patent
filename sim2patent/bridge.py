"""sim2patent.bridge —— 桥接 agent 的编排核心。

用法:
    from sim2patent.bridge import Bridge
    Bridge().run("examples/sample_sim.json")   # 自动探测 key,mock 兜底

Bridge 自身不做语义分析,只负责:
  1. 解析输入(parsers)                     -> SimulationResult
  2. 数据摘要 + LLM/mock 发明点分析(stages) -> InventionAnalysis
  3. LLM/mock 技术交底生成(stages)          -> TechnicalDisclosure
  4. 渲染 Markdown 与交接 JSON(render)
  5. 调用专利 agent 端口落盘(patent_agent)
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from .config import Settings, settings as _default_settings
from .llm import LLMBackend, LLMError
from .parsers import parse_input
from .patent_agent import make_patent_agent
from .render import render_disclosure_md, render_innovation_md
from .schema import BridgeReport
from .stages import make_stages

_OUT_SUBDIR = "output"


class Bridge:
    """仿真 -> 专利 输入转换编排器。"""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        out_dir: Optional[str | Path] = None,
        param_columns: Optional[Iterable[str]] = None,
        force_mock: bool = False,
    ) -> None:
        self.settings = settings or _default_settings
        self.param_columns = param_columns
        self.out_dir = Path(out_dir) if out_dir else Path.cwd() / _OUT_SUBDIR

        self.llm: Optional[LLMBackend] = None
        if not force_mock:
            if self.settings.has_key:
                try:
                    self.llm = LLMBackend(self.settings)
                except LLMError as exc:
                    print(f"[warn] 无法初始化 LLM,将使用离线 mock: {exc}")
            else:
                print("[warn] 未设置 DEEPSEEK_API_KEY,将使用离线 mock(--mock 同效)")
        self.used_mock = self.llm is None

    # ------------------------------------------------------------------
    def run(self, input_path: str | Path) -> BridgeReport:
        path = Path(input_path)
        sim = parse_input(path, param_columns=self.param_columns)

        analyzer, discloser = make_stages(self.llm)
        analysis = analyzer(sim)
        disclosure = discloser(sim, analysis)

        report = BridgeReport(
            input_path=str(path),
            simulation=sim,
            analysis=analysis,
            disclosure=disclosure,
            used_mock=self.used_mock,
        )
        self._write_outputs(report)
        return report

    # ------------------------------------------------------------------
    def _write_outputs(self, report: BridgeReport) -> None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = Path(report.input_path).stem
        out = self.out_dir
        out.mkdir(parents=True, exist_ok=True)

        handoff_json = out / f"handoff_{stem}_{stamp}.json"
        disclosure_md = out / f"交底书_{stem}_{stamp}.md"
        innovation_md = out / f"创新点清单_{stem}_{stamp}.md"

        payload = {
            "meta": {
                "generator": "sim2patent",
                "version": "0.1.0",
                "model": report.analysis.model,
                "used_mock": report.used_mock,
                "input": report.input_path,
                "generated_at": stamp,
            },
            "simulation": report.simulation.to_dict(),
            "analysis": report.analysis.to_dict(),
            "disclosure": report.disclosure.to_dict(),
        }
        handoff_json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        disclosure_md.write_text(
            render_disclosure_md(report.simulation, report.analysis, report.disclosure),
            encoding="utf-8",
        )
        innovation_md.write_text(
            render_innovation_md(report.simulation, report.analysis), encoding="utf-8"
        )

        report.handoff_json_path = str(handoff_json)
        report.disclosure_md_path = str(disclosure_md)
        report.innovation_md_path = str(innovation_md)

        # 交给专利 agent 端口(默认实现即落盘,见 patent_agent.py)
        agent = make_patent_agent("handoff", self.out_dir)
        print(agent.consume(report))

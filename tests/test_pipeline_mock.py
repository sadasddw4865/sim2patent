"""离线 mock 全链路测试(不依赖网络与 LLM)。"""
from __future__ import annotations

from pathlib import Path

from sim2patent.bridge import Bridge

EX = Path(__file__).resolve().parent.parent / "examples"


def test_mock_pipeline_writes_outputs(tmp_path):
    bridge = Bridge(out_dir=tmp_path, force_mock=True)
    report = bridge.run(EX / "sample_sim.json")

    assert report.used_mock is True
    assert report.analysis.model == "mock"
    assert len(report.analysis.points) >= 1
    assert report.disclosure.embodiments

    # 三个产物文件都应真实落盘
    for p in (report.handoff_json_path, report.disclosure_md_path, report.innovation_md_path):
        assert Path(p).exists(), p
        assert Path(p).stat().st_size > 0

    # 交接 JSON 是合法 UTF-8 JSON 且含三个顶层段
    import json

    payload = json.loads(Path(report.handoff_json_path).read_text(encoding="utf-8"))
    assert set(payload) == {"meta", "simulation", "analysis", "disclosure"}


def test_mock_pipeline_csv(tmp_path):
    bridge = Bridge(out_dir=tmp_path, force_mock=True)
    report = bridge.run(EX / "sample_sim.csv")
    assert report.simulation.source_file.endswith("sample_sim.csv")
    assert len(report.analysis.points) >= 1

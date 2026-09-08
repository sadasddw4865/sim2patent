"""解析器单元测试。运行:`python -m pytest tests -q`"""
from __future__ import annotations

from pathlib import Path

from sim2patent.parsers import parse_input

EX = Path(__file__).resolve().parent.parent / "examples"


def test_json_canonical():
    sim = parse_input(EX / "sample_sim.json")
    assert "风冷" in sim.title
    assert len(sim.metrics) == 3
    assert len(sim.design_points) == 5
    assert sim.design_points[0].is_baseline is True
    temp = next(m for m in sim.metrics if m.name == "最高温度")
    assert temp.baseline_value == 55.4
    assert temp.value == 43.6


def test_json_loose_records():
    sim = parse_input(EX / "sample_records.json")
    assert len(sim.design_points) == 3
    assert sim.design_points[0].id == "R1"
    # 记录行中的数值指标应进入对应设计点
    dp = sim.design_points[1]
    assert dp.metrics["最大应力"] == 205.0


def test_csv_heuristic():
    sim = parse_input(EX / "sample_sim.csv")
    names = [p.name for p in sim.parameters]
    assert names == ["入口风速", "风道倾角", "翅片间距"]
    assert len(sim.design_points) == 5
    metric_names = [m.name for m in sim.metrics]
    assert "最高温度" in metric_names
    # 无 is_baseline 列时,首行作为基线回退
    temp = next(m for m in sim.metrics if m.name == "最高温度")
    assert temp.baseline_value == 55.4


def test_csv_param_columns_override():
    sim = parse_input(EX / "sample_sim.csv", param_columns=["风道倾角", "翅片间距"])
    names = [p.name for p in sim.parameters]
    assert names == ["风道倾角", "翅片间距"]
    # 未指定为参数的入口风速被当作指标列
    metric_names = [m.name for m in sim.metrics]
    assert "入口风速" in metric_names

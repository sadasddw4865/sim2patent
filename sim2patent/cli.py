"""sim2patent.cli —— 命令行入口。

示例(在项目根目录 sim2patent/ 下执行):

    # 全流程(有 DEEPSEEK_API_KEY 走真实 LLM,否则自动降级 mock)
    python -m sim2patent examples/sample_sim.json

    # 强制离线 mock(不调用任何网络)
    python -m sim2patent run examples/sample_sim.csv --mock

    # 只解析不做 LLM,检查解析结果
    python -m sim2patent parse examples/sample_sim.json

Windows PowerShell 设置密钥:
    $env:DEEPSEEK_API_KEY = "sk-..."
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .bridge import Bridge
from .parsers import parse_input
from .schema import SimulationResult

_PKG_DIR = Path(__file__).resolve().parent.parent


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sim2patent",
        description="仿真 agent 结果 -> 专利 agent 输入的桥接 agent",
    )
    sub = p.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="全流程:解析 -> 发明点 -> 交底书 -> 交接")
    run_p.add_argument("input", help="仿真输出文件(.json / .csv)")
    _add_common(run_p)

    parse_p = sub.add_parser("parse", help="仅解析输入并打印结构化结果")
    parse_p.add_argument("input", help="仿真输出文件(.json / .csv)")
    parse_p.add_argument("--param-cols", default="", help="CSV 参数列,逗号分隔(可选)")

    p.add_argument("input_arg", nargs="?", help=argparse.SUPPRESS)
    return p


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--mock", action="store_true", help="强制离线 mock,不调用 LLM")
    p.add_argument("--out", default="", help="输出目录(默认 <当前目录>/output)")
    p.add_argument("--param-cols", default="", help="CSV 参数列,逗号分隔(可选)")


def _parse_param_cols(text: str) -> list[str] | None:
    cols = [c.strip() for c in text.split(",") if c.strip()]
    return cols or None


def _print_sim(sim: SimulationResult) -> None:
    print(f"标题: {sim.title or '(空)'}")
    print(f"目标: {sim.objective or '(空)'}")
    print(f"基准: {sim.baseline or '(空)'}")
    print(f"参数({len(sim.parameters)}): " + ", ".join(p.name for p in sim.parameters))
    for m in sim.metrics:
        base = f"(基线 {m.baseline_value})" if m.baseline_value is not None else ""
        print(f"  指标 {m.name} = {m.value} {m.unit}{base}")
    print(f"设计点: {len(sim.design_points)} 组")
    for n in sim.notes:
        print(f"  备注: {n}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    # 兼容 `sim2patent <file>` 的裸用法
    if args.command is None and getattr(args, "input_arg", None):
        return _do_run(args.input_arg, mock=False, out="", param_cols=None)
    if args.command is None:
        _build_parser().print_help()
        return 2

    if args.command == "parse":
        sim = parse_input(args.input, param_columns=_parse_param_cols(args.param_cols))
        _print_sim(sim)
        return 0

    if args.command == "run":
        return _do_run(
            args.input,
            mock=args.mock,
            out=args.out,
            param_cols=_parse_param_cols(args.param_cols),
        )

    _build_parser().print_help()
    return 2


def _do_run(input_file: str, mock: bool, out: str, param_cols: list[str] | None) -> int:
    try:
        bridge = Bridge(
            out_dir=out or None,
            param_columns=param_cols,
            force_mock=mock,
        )
        report = bridge.run(input_file)
        print()
        print("=" * 60)
        print(f"桥接完成(mock={report.used_mock})")
        print(f"  数据来源: {report.input_path}")
        print(f"  发明点数: {len(report.analysis.points)}")
        print(f"  生成模型: {report.analysis.model}")
        print(f"  交接文件: {report.handoff_json_path}")
        return 0
    except Exception as exc:  # 用户可见的友好报错
        print(f"[错误] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

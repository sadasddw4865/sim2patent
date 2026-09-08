"""sim2patent.parsers —— 把工程仿真输出文件解析成 SimulationResult。

支持两种输入形态:

1) JSON(.json)
   - 规范形态:顶层含 parameters / metrics / design_points 等键,
     字段与 schema.SimulationResult 对应;
   - 宽松形态:任意 dict / 记录数组,用启发式把"看起来像参数的列"
     与"像指标的列"分开(配合 param_columns 可精确指定)。

2) CSV(.csv)
   首行为表头,每行一个设计点。判定规则(可被 param_columns 覆盖):
   - 列名含 design/param/变量/参数/工况/入口/倾角 等关键词 -> 参数
   - 列名含 temp/效率/压降/ΔT/温度/指标/metric 等关键词或全为数值 -> 指标
   - 其余未匹配的数值列按指标处理。

对任何输入,解析都只做"搬移与类型转换",不臆造语义;
拿不准的列名会原样进入 notes,便于人工复核。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Optional

from .schema import DesignPoint, SimMetric, SimParam, SimulationResult

# 参数列名特征词(小写匹配)
_PARAM_HINTS = (
    "param", "design", "variable", "工况", "条件", "参数", "变量", "几何",
    "angle", "倾角", "width", "间距", "radius", "半径", "length", "长度",
    "height", "高度", "thickness", "厚度", "speed", "风速", "入口", "inlet",
    "flow", "流量", "ratio", "比例", "系数",
)
# 行标识列(编号/主键,既不是参数也不是指标)
_ID_COLUMNS = ("id", "设计点", "编号", "序号", "point", "case", "ID", "No", "行号")


def _is_id_column(name: str) -> bool:
    low = name.lower()
    return any(low == ic.lower() for ic in _ID_COLUMNS)
# 指标列名特征词
_METRIC_HINTS = (
    "metric", "result", "指标", "结果", "温度", "temp", "效率", "efficien",
    "压降", "pressure", "drop", "delta", "Δ", "温升", "均匀", "uniform",
    "功率", "power", "质量", "应力", "stress", "位移", "变形", "strain",
    "安全系数", "系数", "寿命", "life", "噪声", "noise",
)


def _hint_of(name: str, hints: Iterable[str]) -> bool:
    low = name.lower()
    return any(h in low for h in hints)


def _classify_columns(header: list[str], param_columns: Optional[set[str]]) -> tuple[list[str], list[str]]:
    """返回 (参数列, 指标列)。显式 param_columns 优先;其余按特征词启发式。"""
    if param_columns:
        p_cols = [c for c in header if c in param_columns]
        m_cols = [c for c in header if c not in param_columns and not _is_id_column(c) and c.strip()]
        if not p_cols:
            raise ValueError(f"param_columns 中没有与表头匹配的列: {param_columns}")
        return p_cols, m_cols
    p_cols, m_cols = [], []
    for c in header:
        name = c.strip()
        if not name or _is_id_column(name):
            continue
        if _hint_of(name, _PARAM_HINTS) and not _hint_of(name, _METRIC_HINTS):
            p_cols.append(c)
        else:
            m_cols.append(c)   # 指标特征词或无法判定 -> 按指标(保守)
    if not p_cols and len(header) >= 2:
        # 完全没有参数特征词时:首列(非 id 列)视为设计点编号/参数占位
        p_cols = [next(c for c in header if not _is_id_column(c.strip()) and c.strip())]
    return p_cols, m_cols


def _to_float(text: str) -> Optional[float]:
    t = text.strip().replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def _records_from_rows(header: list[str], rows: list[list[str]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for r in rows:
        if not any(cell.strip() for cell in r):
            continue
        rec: dict[str, Any] = {}
        for i, cell in enumerate(r):
            if i < len(header):
                rec[header[i]] = cell
        records.append(rec)
    return records


# --------------------------------------------------------------------------
# JSON 解析
# --------------------------------------------------------------------------

def _parse_json_canonical(data: dict[str, Any], source: str) -> SimulationResult:
    sim = SimulationResult(source_file=source, raw=data)
    sim.title = str(data.get("title", ""))
    sim.objective = str(data.get("objective", ""))
    sim.baseline = str(data.get("baseline", ""))

    for p in data.get("parameters", []) or []:
        if isinstance(p, dict):
            sim.parameters.append(
                SimParam(
                    name=str(p.get("name", "")),
                    value=str(p.get("value", "")),
                    unit=str(p.get("unit", "")),
                    role=str(p.get("role", "design")),
                    note=str(p.get("note", "")),
                )
            )
    for m in data.get("metrics", []) or []:
        if not isinstance(m, dict):
            continue
        val = _to_float(str(m.get("value", "")))
        if val is None:
            continue
        base_raw = m.get("baseline_value")
        base = _to_float(str(base_raw)) if base_raw not in (None, "") else None
        name = str(m.get("name", ""))
        direction = str(m.get("better_direction", "")) or _infer_better_direction(name)
        sim.metrics.append(
            SimMetric(
                name=name,
                value=val,
                unit=str(m.get("unit", "")),
                baseline_value=base,
                better_direction=direction,
                design_point=str(m.get("design_point", "")),
                note=str(m.get("note", "")),
            )
        )
    for dp in data.get("design_points", []) or []:
        if isinstance(dp, dict):
            sim.design_points.append(_design_point_from_record(dp))
    for n in data.get("notes", []) or []:
        sim.notes.append(str(n))
    # 设计点缺失指标汇总时,由设计点推导;存在汇总但缺基线时用基线行补齐
    if not sim.metrics and sim.design_points:
        _fill_metric_summaries(sim)
    elif sim.metrics and sim.design_points:
        ref = next((p for p in sim.design_points if p.is_baseline), sim.design_points[0])
        for m in sim.metrics:
            if m.baseline_value is None and m.name in ref.metrics:
                m.baseline_value = ref.metrics[m.name]
    if not sim.title and data.get("目标"):
        sim.title = str(data["目标"])
    if not sim.objective and data.get("仿真目标"):
        sim.objective = str(data["仿真目标"])
    return sim


def _design_point_from_record(rec: dict[str, Any]) -> DesignPoint:
    params: dict[str, str] = {}
    metrics: dict[str, float] = {}
    id_val = str(rec.get("id") or rec.get("设计点") or rec.get("编号")
                 or rec.get("point") or "")
    is_base = bool(rec.get("is_baseline") or rec.get("基线") or False)
    skip_keys = ("id", "设计点", "编号", "point", "is_baseline", "基线", "note", "备注")
    for k, v in rec.items():
        if k in skip_keys:
            continue
        if v is None:
            continue
        # bool 是 int 的子类,必须先于数值分支处理,否则会注入 None 指标
        if isinstance(v, bool):
            params[k] = str(v)
            continue
        if isinstance(v, (int, float)) or _to_float(str(v)) is not None:
            f = _to_float(str(v))
            if f is not None and _hint_of(str(k), _PARAM_HINTS):
                params[k] = str(v)
            else:
                metrics[k] = f
        else:
            params[k] = str(v)
    return DesignPoint(
        id=id_val,
        params=params,
        metrics=metrics,
        is_baseline=is_base,
        note=str(rec.get("note", "")),
    )


def _parse_json_loose(data: Any, source: str) -> SimulationResult:
    """宽松形态:dict 或记录数组。若是 dict 且有关键子表则优先走规范分支。"""
    if isinstance(data, dict):
        if any(k in data for k in ("parameters", "metrics", "design_points")):
            return _parse_json_canonical(data, source)
        return _parse_json_canonical({"design_points": _records_from_dicts([data])}, source)
    if isinstance(data, list):
        return _parse_json_canonical({"design_points": _records_from_dicts(data)}, source)
    raise ValueError("JSON 顶层必须是对象或记录数组")


def _records_from_dicts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            continue
        rec = dict(it)
        rec.setdefault("id", f"P{i + 1}")
        out.append(rec)
    return out


# --------------------------------------------------------------------------
# CSV 解析
# --------------------------------------------------------------------------

def _parse_csv(path: Path, param_columns: Optional[set[str]]) -> SimulationResult:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        raise ValueError("CSV 为空")
    header = [c.strip() for c in rows[0]]
    data_rows = rows[1:]
    p_cols, m_cols = _classify_columns(header, param_columns)
    sim = SimulationResult(title=path.stem, source_file=str(path))
    sim.parameters = [SimParam(name=c, value="", role="design") for c in p_cols]
    for dp_row in data_rows:
        rec: dict[str, Any] = {header[i]: cell for i, cell in enumerate(dp_row) if i < len(header)}
        dp = _design_point_from_record(rec)
        # _design_point_from_record 会把数值参数误判为指标(它按 PARAM_HINTS 判定);
        # CSV 场景下参数集合由 p_cols 明确给出,这里做纠正。
        dp.params = {c: str(rec.get(c, "")).strip() for c in p_cols}
        dp.metrics = {}
        for c in m_cols:
            raw = rec.get(c)
            f = _to_float(str(raw)) if raw not in (None, "") else None
            if f is not None:
                dp.metrics[c] = f
        if dp.id == "":
            dp.id = f"DP{len(sim.design_points) + 1}"
        sim.design_points.append(dp)
    # 用基线列(若存在)填充 metrics 汇总
    _fill_metric_summaries(sim)
    if not p_cols:
        sim.notes.append("未识别到参数列,全部按指标列处理")
    return sim


def _fill_metric_summaries(sim: SimulationResult) -> None:
    """从设计点推导指标汇总。

    语义:ref = 基线行取值(无 is_baseline 标记则取首行作对照);
    value = 对比行中"相对 ref 变化幅度最大"的一行取值 ——
    把最显著的效应显式呈现给下游分析。
    """
    base_pts = [p for p in sim.design_points if p.is_baseline]
    comp_pts = [p for p in sim.design_points if not p.is_baseline]
    if not sim.design_points or not comp_pts:
        return
    ref = base_pts[0] if base_pts else sim.design_points[0]
    metric_names = list(sim.design_points[0].metrics.keys())
    for name in metric_names:
        if name not in ref.metrics:
            continue
        base = ref.metrics[name]
        # 找相对基线 |Δ| 最大的一行作为"效应最强"取值
        best_pt, best_val = None, None
        for p in comp_pts:
            if name not in p.metrics:
                continue
            v = p.metrics[name]
            if best_pt is None or abs(v - base) > abs(best_val - base):
                best_pt, best_val = p, v
        if best_val is None:
            continue
        sim.metrics.append(
            SimMetric(
                name=name,
                value=best_val,
                baseline_value=base,
                better_direction=_infer_better_direction(name),
                note=f"效应最强设计点:{best_pt.id}",
            )
        )


# 仅收录语义确定、不会误伤的“越低越好/越高越好”特征词
_LOWER_BETTER = (
    "温度", "温升", "温差", "压降", "应力", "噪声", "成本", "功耗",
    "重量", "变形", "误差", "失真", "风阻", "Δ", "delta", "drop",
    "stress", "noise",
)
_HIGHER_BETTER = (
    "效率", "寿命", "强度", "刚度", "均匀", "uniform", "efficien",
    "life", "strength", "系数",
)


def _infer_better_direction(name: str) -> str:
    low = name.lower()
    lower = any(h in low for h in _LOWER_BETTER)
    higher = any(h in low for h in _HIGHER_BETTER)
    if lower and not higher:
        return "lower"
    if higher and not lower:
        return "higher"
    return ""


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------

def parse_input(
    input_path: str | Path,
    param_columns: Optional[Iterable[str]] = None,
) -> SimulationResult:
    """把 CSV/JSON 仿真输出解析为 SimulationResult。

    param_columns: 显式指定 CSV 中哪些列是参数(其余按指标)。
    """
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"输入文件不存在: {path}")
    pc = {c.strip() for c in param_columns} if param_columns else None
    suffix = path.suffix.lower()
    if suffix == ".json":
        with path.open("r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
        return _parse_json_loose(data, str(path))
    if suffix == ".csv":
        return _parse_csv(path, pc)
    raise ValueError(f"不支持的输入格式: {suffix} (支持 .json / .csv)")

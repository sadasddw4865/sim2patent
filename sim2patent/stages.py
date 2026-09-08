"""sim2patent.stages —— 两个 LLM 阶段(analyze / disclose)+ JSON 契约校验。

每一阶段都:
1. 构造数据摘要(utils.build_data_digest,行数封顶);
2. 调用 LLM 取 JSON;
3. 校验契约(宽松:类型与必填键),失败自动重试一次;
4. 组装成 schema 对象并记录模型名。
"""
from __future__ import annotations

import json
from typing import Any, Callable

from . import prompts
from .llm import LLMBackend, LLMError
from .mock import analyze_mock, disclose_mock
from .schema import InventionAnalysis, InventionPoint, SimulationResult, TechnicalDisclosure
from .utils import build_data_digest

_MAX_POINTS = 60


# --------------------------------------------------------------------------
# 校验助手
# --------------------------------------------------------------------------

def _expect_list(obj: Any, key: str, default: list[Any]) -> list[Any]:
    v = obj.get(key, default)
    return v if isinstance(v, list) else default


def _expect_str(obj: Any, key: str, default: str = "") -> str:
    v = obj.get(key, default)
    return str(v) if v is not None else default


def _parse_point(raw: Any) -> InventionPoint:
    if not isinstance(raw, dict):
        raise LLMError("发明点不是对象")
    return InventionPoint(
        title=_expect_str(raw, "title"),
        category=_expect_str(raw, "category"),
        novelty_argument=_expect_str(raw, "novelty_argument"),
        technical_effect=_expect_str(raw, "technical_effect"),
        supporting_evidence=[str(x) for x in _expect_list(raw, "supporting_evidence", [])],
        claim_direction=_expect_str(raw, "claim_direction"),
        concern=_expect_str(raw, "concern"),
        confidence=_to_conf(raw.get("confidence", 0.0)),
    )


def _to_conf(v: Any) -> float:
    try:
        c = float(v)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, c))


def _ask_json(backend: LLMBackend, system: str, user: str) -> dict[str, Any]:
    """取 JSON;失败(解析或契约)自动重试一次。"""
    try:
        return backend.chat_json(system, user)
    except LLMError:
        return backend.chat_json(prompts.RETRY_HINT, user)


# --------------------------------------------------------------------------
# 阶段一:发明点分析
# --------------------------------------------------------------------------

def analyze(
    sim: SimulationResult,
    backend: LLMBackend,
) -> InventionAnalysis:
    digest = build_data_digest(sim, _MAX_POINTS)
    raw = _ask_json(backend, prompts.ANALYZE_SYSTEM, prompts.ANALYZE_USER.format(data_digest=digest))

    points_raw = _expect_list(raw, "points", [])
    if not points_raw:
        raise LLMError("LLM 未返回任何发明点(points 为空)")
    points = [_parse_point(p) for p in points_raw if isinstance(p, dict)]
    if not points:
        raise LLMError("发明点清单无法解析")

    return InventionAnalysis(
        summary=_expect_str(raw, "summary"),
        points=points,
        model=backend.model,
    )


# --------------------------------------------------------------------------
# 阶段二:技术交底书
# --------------------------------------------------------------------------

def disclose(
    sim: SimulationResult,
    analysis: InventionAnalysis,
    backend: LLMBackend,
) -> TechnicalDisclosure:
    digest = build_data_digest(sim, _MAX_POINTS)
    analysis_json = json.dumps(analysis.to_dict(), ensure_ascii=False, indent=2)
    raw = _ask_json(
        backend,
        prompts.DISCLOSE_SYSTEM,
        prompts.DISCLOSE_USER.format(data_digest=digest, analysis_json=analysis_json),
    )

    embodiments = [str(x) for x in _expect_list(raw, "embodiments", [])]
    if not embodiments:
        raise LLMError("交底书缺少实施例(embodiments 为空)")
    effects = [str(x) for x in _expect_list(raw, "technical_effects", [])]
    innovations = [str(x) for x in _expect_list(raw, "innovation_points", [])]
    basis = [str(x) for x in _expect_list(raw, "data_basis", [])]

    return TechnicalDisclosure(
        title=_expect_str(raw, "title"),
        technical_field=_expect_str(raw, "technical_field"),
        background_problem=_expect_str(raw, "background_problem"),
        prior_art_shortcomings=_expect_str(raw, "prior_art_shortcomings"),
        solution_summary=_expect_str(raw, "solution_summary"),
        embodiments=embodiments,
        technical_effects=effects,
        innovation_points=innovations,
        design_space_note=_expect_str(raw, "design_space_note"),
        data_basis=basis,
        model=backend.model,
    )


# --------------------------------------------------------------------------
# 供 bridge 选择的工厂:mock 或 LLM
# --------------------------------------------------------------------------

Analyzer = Callable[[SimulationResult], InventionAnalysis]
Discloser = Callable[[SimulationResult, InventionAnalysis], TechnicalDisclosure]


def make_stages(backend: LLMBackend | None) -> tuple[Analyzer, Discloser]:
    """有 backend 用 LLM 阶段,否则用确定性 mock。"""
    if backend is None:
        return analyze_mock, disclose_mock
    return (lambda sim: analyze(sim, backend)), (lambda sim, ana: disclose(sim, ana, backend))

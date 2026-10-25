"""Auditable checks and descriptive analysis of fixed-template solver outputs.

This module is independent of FastAPI, MATLAB, and any paid model service.
Checks establish input/output consistency, not convergence or real-ocean truth.
Design references: arlpy's environment checks, acoustics-agent's layered
validation, and OpenHands' typed action/observation boundary. No upstream
solver implementation or AT fixture is copied here.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
# SHD positions are commonly stored as single precision. At 100 km this
# tolerance covers coordinate serialization without accepting a wrong cell.
COORD_TOL_M = 0.05
VALUE_TOL_DB = 1e-5
PLAN_FIELDS = (
    "template", "frequency_hz", "source_depth_m", "frequencies_hz",
    "source_depths_m", "receiver_depth_m", "range_min_km", "range_max_km",
    "range_points", "depth_points",
)


class ResultValidationError(ValueError):
    def __init__(self, report: dict[str, Any]):
        self.report = report
        super().__init__("仿真产物校验失败：" + "；".join(report["errors"]))


def _number(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _array(value: Any) -> bool:
    return isinstance(value, (list, tuple))


def _axis(value: Any) -> bool:
    return _array(value) and len(value) >= 2 and all(_number(v) for v in value)


def _close(a: Any, b: Any, tol: float = COORD_TOL_M) -> bool:
    return _number(a) and _number(b) and abs(a - b) <= tol


def _sample(value: Any) -> bool:
    # MATLAB jsonencode represents NaN as null. Nonfinite numeric entries are
    # treated as masked samples, while strings and booleans are malformed.
    return value is None or isinstance(value, (int, float)) and not isinstance(value, bool)


def _equal_sample(a: Any, b: Any) -> bool:
    if _number(a) and _number(b):
        return abs(a - b) <= VALUE_TOL_DB
    return _sample(a) and _sample(b) and not _number(a) and not _number(b)


def _case_value(plan: Mapping[str, Any], scalar: str, plural: str) -> Any:
    if scalar in plan:
        return plan[scalar]
    values = plan.get(plural)
    return values[0] if _array(values) and len(values) == 1 else None


def _grid_matches(axis: list[float], start: Any, end: Any, points: Any) -> bool:
    if not _axis(axis) or not _number(start) or not _number(end):
        return False
    if not isinstance(points, int) or isinstance(points, bool) or points < 2 or len(axis) != points:
        return False
    return all(abs(v - (start + i * (end - start) / (points - 1))) <= COORD_TOL_M
               for i, v in enumerate(axis))


def verify_result(result: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    """Return named consistency checks without running a solver or raising.

    ``plan`` should describe one submitted case, including scalar
    frequency_hz/source_depth_m (or singleton frequency/source arrays).
    Missing required evidence fails a check; it is never filled with an
    invented number. Masked pressure-release surface samples remain valid.
    """
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []

    def check(key: str, label: str, passed: bool, detail: str) -> None:
        checks.append({"id": key, "label": label, "passed": bool(passed), "detail": detail})

    if not isinstance(result, Mapping) or not isinstance(plan, Mapping):
        check("object_schema", "输入和结果对象", False, "结果与计划必须为对象")
        return {"schema_version": SCHEMA_VERSION, "ok": False, "checks": checks,
                "errors": [checks[0]["label"]], "warnings": [], "metrics": {}}

    ranges = result.get("ranges_m")
    depths = result.get("depths_m")
    matrix = result.get("tl_db")
    curve = result.get("curve_tl_db")
    range_axis_ok, depth_axis_ok = _axis(ranges), _axis(depths)
    check("range_axis", "距离轴有限且严格递增", range_axis_ok and all(b > a for a, b in zip(ranges, ranges[1:])),
          "距离单位为 m，至少两个有限坐标，禁止重复或倒序")
    check("depth_axis", "深度轴有限且严格递增", depth_axis_ok and all(b > a for a, b in zip(depths, depths[1:])),
          "深度单位为 m，至少两个有限坐标，禁止重复或倒序")

    range_start, range_end = plan.get("range_min_km"), plan.get("range_max_km")
    range_bounds_ok = (_number(range_start) and _number(range_end) and range_start < range_end
                       and range_axis_ok and _close(ranges[0], range_start * 1000)
                       and _close(ranges[-1], range_end * 1000)
                       and all(range_start * 1000 - COORD_TOL_M <= r <= range_end * 1000 + COORD_TOL_M for r in ranges))
    check("range_bounds", "距离范围对应任务", range_bounds_ok, "km → m；起点、终点与所有采样点须在任务范围内")
    check("range_grid", "距离网格对应请求采样", range_axis_ok and _grid_matches(
        ranges, range_start * 1000 if _number(range_start) else None,
        range_end * 1000 if _number(range_end) else None, plan.get("range_points")),
        "核对采样点数与等间距位置，坐标容差 0.05 m")
    fixed_munk = plan.get("template") == "munk_5000m"
    check("template", "已登记环境模板", fixed_munk, "当前校验器只对应 5000 m Munk 模板")
    check("depth_grid", "深度网格对应环境", depth_axis_ok and fixed_munk and _grid_matches(
        depths, 0.0, 5000.0, plan.get("depth_points")), "当前模板深度范围 0–5000 m，核对点数及等间距位置")

    expected_shape = [len(depths), len(ranges)] if depth_axis_ok and range_axis_ok else None
    rectangular = (expected_shape is not None and _array(matrix) and len(matrix) == expected_shape[0]
                   and all(_array(row) and len(row) == expected_shape[1] for row in matrix))
    check("matrix_shape", "TL 数组轴与尺寸", rectangular, "数组轴顺序固定为 [深度, 距离]，不能以转置图代替")
    declared_shape = result.get("shape")
    check("declared_shape", "声明尺寸对应实际数据", rectangular and declared_shape == expected_shape,
          "shape 必须与坐标长度、TL 数组实际尺寸一致")
    samples_ok = rectangular and all(_sample(v) for row in matrix for v in row)
    check("sample_types", "TL 样本类型", samples_ok, "允许有限数值与已屏蔽的非有限/null 样本，禁止字符串或布尔值")
    finite_values = [float(v) for row in matrix for v in row if _number(v)] if samples_ok else []
    sample_count = expected_shape[0] * expected_shape[1] if rectangular else 0
    valid_ratio = len(finite_values) / sample_count if sample_count else None
    check("finite_samples", "至少存在有效 TL 样本", bool(finite_values), "全无效场不能视为成功产物")
    reported_ratio = result.get("valid_ratio")
    check("valid_ratio", "有效比例对应实际样本", valid_ratio is not None and _number(reported_ratio)
          and 0 <= reported_ratio <= 1 and abs(reported_ratio - valid_ratio) <= 1e-7,
          "使用实际有限样本数 / 所有网格样本数复算")
    if valid_ratio is not None and valid_ratio < 0.9:
        warnings.append("有效样本不足 90%；请结合边界无效样本和原始日志检查。90% 是提示门槛，不是物理定律。")

    frequency = _case_value(plan, "frequency_hz", "frequencies_hz")
    source = _case_value(plan, "source_depth_m", "source_depths_m")
    check("frequency", "实际频率对应任务", _close(result.get("frequency_hz"), frequency, 1e-4),
          "实际 SHD 频率与单个任务频率一致，容差 0.0001 Hz")
    check("source_depth", "实际源深对应任务", _close(result.get("source_depth_m"), source, 0.01),
          "实际源深与任务一致，坐标序列化容差 0.01 m")
    requested = plan.get("receiver_depth_m")
    actual = result.get("actual_receiver_depth_m")
    check("receiver_request", "接收深度请求记录一致", _close(result.get("requested_receiver_depth_m"), requested, 0.01),
          "结果不得把改变后的深度标成原请求")
    nearest_index = min(range(len(depths)), key=lambda i: abs(depths[i] - requested)) if depth_axis_ok and _number(requested) else None
    selected_index = min(range(len(depths)), key=lambda i: abs(depths[i] - actual)) if depth_axis_ok and _number(actual) else None
    receiver_ok = (nearest_index is not None and selected_index is not None
                   and _close(actual, depths[selected_index])
                   and abs(abs(depths[selected_index] - requested) - abs(depths[nearest_index] - requested)) <= COORD_TOL_M)
    check("receiver_nearest", "实际接收深度为最近网格", receiver_ok, "报告实际取样深度，允许等距最近点，不伪称精确取到请求深度")
    receiver_error = abs(actual - requested) if _number(actual) and _number(requested) else None
    check("receiver_error", "接收网格误差记录一致", _close(result.get("receiver_depth_error_m"), receiver_error, 0.01),
          "误差为 |实际深度 − 请求深度|，单位 m")
    curve_ok = range_axis_ok and _array(curve) and len(curve) == len(ranges) and all(_sample(v) for v in curve)
    check("curve_length", "接收曲线与距离轴对应", curve_ok, "曲线长度须与距离采样点数相等")
    curve_matches = (curve_ok and rectangular and receiver_ok
                     and all(_equal_sample(a, b) for a, b in zip(curve, matrix[selected_index])))
    check("curve_row", "接收曲线对应 TL 实际行", curve_matches, "曲线必须来自所报告实际接收深度的 TL 行，数值容差 0.00001 dB")
    if curve_ok and not any(_number(v) for v in curve):
        warnings.append("该接收深度曲线没有有限样本；场图可能有效，但不能报告接收曲线的数值极值。")
    errors = [c["label"] for c in checks if not c["passed"]]
    return {"schema_version": SCHEMA_VERSION, "ok": not errors, "checks": checks,
            "errors": errors, "warnings": warnings,
            "metrics": {"finite_samples": len(finite_values), "total_samples": sample_count,
                        "valid_ratio": valid_ratio, "actual_receiver_depth_m": actual if _number(actual) else None,
                        "receiver_depth_error_m": receiver_error,
                        "shape": expected_shape, "coordinate_tolerance_m": COORD_TOL_M},
            "scope": "验证输入和产物一致性，不替代求解器收敛、海域真实性或实验验证"}


def validate_result(result: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    report = verify_result(result, plan)
    if not report["ok"]:
        raise ResultValidationError(report)
    return report


def analyze_result(result: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    """Calculate descriptive highlights from a verified matrix and curve."""
    validation = validate_result(result, plan)
    field_values = [float(v) for row in result["tl_db"] for v in row if _number(v)]
    curve_points = [(float(r), float(tl)) for r, tl in zip(result["ranges_m"], result["curve_tl_db"]) if _number(tl)]
    field_stats = {"tl_min_db": min(field_values), "tl_max_db": max(field_values),
                   "tl_median_db": statistics.median(field_values)}
    curve_stats: dict[str, Any] = {"finite_samples": len(curve_points)}
    if curve_points:
        minimum = min(curve_points, key=lambda pair: pair[1])
        maximum = max(curve_points, key=lambda pair: pair[1])
        curve_stats.update(tl_min_db=minimum[1], tl_max_db=maximum[1],
                           tl_median_db=statistics.median(p[1] for p in curve_points),
                           min_tl_range_km=minimum[0] / 1000, max_tl_range_km=maximum[0] / 1000)
    highlights = [
        {"id": "field_median", "label": "声场有效样本 TL 中位数", "value": field_stats["tl_median_db"], "unit": "dB"},
        {"id": "valid_ratio", "label": "有效网格比例", "value": validation["metrics"]["valid_ratio"] * 100, "unit": "%"},
        {"id": "actual_receiver", "label": "实际接收深度", "value": result["actual_receiver_depth_m"], "unit": "m"},
        {"id": "receiver_error", "label": "接收深度网格偏差", "value": validation["metrics"]["receiver_depth_error_m"], "unit": "m"},
    ]
    if curve_points:
        highlights.extend([
            {"id": "curve_min", "label": "接收曲线采样最低 TL", "value": curve_stats["tl_min_db"], "unit": "dB"},
            {"id": "curve_min_range", "label": "最低 TL 对应采样距离", "value": curve_stats["min_tl_range_km"], "unit": "km"},
        ])
    limits = [
        "Munk 5000 m 理想环境，未接入指定真实海域的观测数据。",
        "相干简正波场存在干涉；TL 不要求随距离单调增加。",
        "FIELD 归一化压力的 TL 不是水听器绝对声压级；没有源级和噪声条件，不能给出通信或探测距离。",
        "最低 TL 仅指当前接收曲线已采样点，不能解释成连续域最优点或最佳海域。",
        "中位数依赖网格与有效样本分布；不同取样条件不可直接排名。",
        "当前校验未证明数值收敛，不能替代网格收敛试验或实验验证。",
    ]
    grid = {"range_min_m": result["ranges_m"][0], "range_max_m": result["ranges_m"][-1],
            "range_points": len(result["ranges_m"]), "depth_min_m": result["depths_m"][0],
            "depth_max_m": result["depths_m"][-1], "depth_points": len(result["depths_m"])}
    signature = hashlib.sha256(json.dumps({"ranges_m": result["ranges_m"], "depths_m": result["depths_m"],
                                           "receiver_depth_m": result["actual_receiver_depth_m"],
                                           "template": plan.get("template"), "reference": result.get("reference")},
                                          sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return {"schema_version": SCHEMA_VERSION, "method": "deterministic_numeric_analysis",
            "evidence": "result.json", "frequency_hz": result["frequency_hz"],
            "source_depth_m": result["source_depth_m"], "field": field_stats, "curve": curve_stats,
            "grid": grid, "highlights": highlights, "limits": limits, "warnings": validation["warnings"],
            "comparability": {"sampling_signature": signature, "can_rank_environments": False,
                              "requires": ["相同环境模板", "相同完整距离/深度坐标", "相同实际接收深度", "相同 TL 归一化及相干约定"],
                              "allowed_controlled_variables": ["frequency_hz", "source_depth_m"],
                              "note": "对比前应核对完整网格；频率/源深可作为明确的控制变量，不据此评价真实海域优劣。"}}


def compare_results(a: Mapping[str, Any], b: Mapping[str, Any],
                    plan_a: Mapping[str, Any], plan_b: Mapping[str, Any]) -> dict[str, Any]:
    """Check controlled-comparison conditions, then compute measured deltas.

    Deliberately conservative for field medians: different finite masks fail
    the comparison rather than silently comparing different populations.
    """
    report_a, report_b = verify_result(a, plan_a), verify_result(b, plan_b)
    checks = {"both_results_verified": report_a["ok"] and report_b["ok"],
              "same_template": plan_a.get("template") == plan_b.get("template"),
              "same_normalization": bool(a.get("reference")) and a.get("reference") == b.get("reference"),
              "same_receiver_depth": _close(a.get("actual_receiver_depth_m"), b.get("actual_receiver_depth_m"))}
    for key in ["ranges_m", "depths_m"]:
        left, right = a.get(key), b.get(key)
        checks["same_" + key] = (_axis(left) and _axis(right) and len(left) == len(right)
                                and all(_close(x, y) for x, y in zip(left, right)))
    if checks["both_results_verified"] and checks["same_ranges_m"] and checks["same_depths_m"]:
        checks["same_finite_mask"] = all(_number(x) == _number(y) for ra, rb in zip(a["tl_db"], b["tl_db"]) for x, y in zip(ra, rb))
    else:
        checks["same_finite_mask"] = False
    comparable = all(checks.values())
    changed = [key for key in ["frequency_hz", "source_depth_m"] if a.get(key) != b.get(key)]
    delta = None
    if comparable:
        aa, bb = analyze_result(a, plan_a), analyze_result(b, plan_b)
        delta = {"field_median_tl_db_b_minus_a": bb["field"]["tl_median_db"] - aa["field"]["tl_median_db"]}
    return {"comparable": comparable, "checks": checks, "changed_controlled_variables": changed,
            "deltas": delta, "can_rank_environments": False,
            "note": "通过只表示采样与归一化适合做受控对照；不证明数值收敛，不等于海域或通信性能排名。"}


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(job_id: str, plan: Mapping[str, Any], folder: str | Path,
                   validation: Mapping[str, Any] | None = None, analysis: Mapping[str, Any] | None = None,
                   *, started_at: str | None = None, finished_at: str | None = None,
                   solver_versions: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Read actual result.json and hash only registered artifacts.

    API keys and absolute configuration paths are never copied into the
    manifest. Unreported external solver versions remain explicitly unknown.
    """
    folder = Path(folder)
    with (folder / "result.json").open(encoding="utf-8-sig") as source:
        result = json.load(source)
    fresh_validation = validate_result(result, plan)
    # Provided reports are advisory: the data is always checked again here.
    validation = fresh_validation
    analysis = analyze_result(result, plan)
    artifacts = []
    names = {"case.json": "input", "case.env": "input", "case.flp": "input",
             "run_ocean_case.m": "script", "result.json": "result", "curve.csv": "result"}
    for name, role in names.items():
        path = folder / name
        if path.is_file() and not path.is_symlink():
            artifacts.append({"name": name, "role": role, "sha256": file_sha256(path), "bytes": path.stat().st_size})
    versions = solver_versions or {}
    return {"schema_version": SCHEMA_VERSION, "job_id": str(job_id),
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "started_at": started_at, "finished_at": finished_at,
            "plan": {key: plan[key] for key in PLAN_FIELDS if key in plan},
            "solver": {"name": "KRAKEN/FIELD", "kraken_version": versions.get("kraken") or None,
                       "field_version": versions.get("field") or None,
                       "version_note": "版本仅记录实际报告值；未提供版本的外部程序标为未知，不推测发行版。",
                       "matlab_version": result.get("matlab_version") or None},
            "measured": {"frequency_hz": result["frequency_hz"], "source_depth_m": result["source_depth_m"],
                         "requested_receiver_depth_m": result["requested_receiver_depth_m"],
                         "actual_receiver_depth_m": result["actual_receiver_depth_m"],
                         "receiver_depth_error_m": result["receiver_depth_error_m"],
                         "valid_ratio": validation["metrics"]["valid_ratio"], "shape": validation["metrics"]["shape"]},
            "artifacts": artifacts, "missing_artifacts": [name for name in names if not any(a["name"] == name for a in artifacts)],
            "validation": dict(validation), "analysis": dict(analysis),
            "scope": "哈希可核验这些输入、脚本和现有产物；不独立证明程序已启动、物理正确或数值收敛。"}


def write_manifest(job_id: str, plan: Mapping[str, Any], folder: str | Path,
                   validation: Mapping[str, Any] | None = None, analysis: Mapping[str, Any] | None = None,
                   **metadata: Any) -> dict[str, Any]:
    manifest = build_manifest(job_id, plan, folder, validation, analysis, **metadata)
    path = Path(folder) / "manifest.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)
    return manifest

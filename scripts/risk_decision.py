#!/usr/bin/env python3
"""
Hybrid ML + rule-based risk decision support for Fulcrum.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - runtime guard
    yaml = None


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RULES = PROJECT_ROOT / "config" / "risk_rules.yaml"


def load_rules(path: Path = DEFAULT_RULES) -> dict[str, Any]:
    if yaml is None:
        raise ImportError("PyYAML is required. Install with: pip install pyyaml")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid rules config format in {path}")
    return data


def _value(row: dict[str, Any], feature: str) -> Any:
    return row.get(feature)


def _compare(actual: Any, operator: str, threshold: Any) -> bool:
    if actual is None:
        return False
    try:
        if operator == "lt":
            return actual < threshold
        if operator == "gt":
            return actual > threshold
        if operator == "eq":
            return actual == threshold
    except TypeError:
        return False
    raise ValueError(f"Unsupported operator: {operator}")


def _evaluate_expression(row: dict[str, Any], expression: dict[str, Any]) -> bool:
    if "all" in expression:
        return all(_evaluate_condition(row, cond) for cond in expression["all"])
    if "any" in expression:
        return any(_evaluate_condition(row, cond) for cond in expression["any"])
    return False


def _evaluate_condition(row: dict[str, Any], condition: dict[str, Any]) -> bool:
    feature = condition.get("feature")
    if feature:
        return _compare(_value(row, str(feature)), str(condition.get("operator", "")), condition.get("threshold"))
    if "expression" in condition:
        return _evaluate_expression(row, condition["expression"])
    return False


def evaluate_rules(row: dict[str, Any], rules_config: dict[str, Any]) -> list[dict[str, Any]]:
    triggered: list[dict[str, Any]] = []
    for severity_key, severity_name in (("critical_rules", "critical"), ("trend_rules", "trend")):
        for rule in rules_config.get(severity_key, []):
            if _evaluate_condition(row, rule):
                triggered.append(
                    {
                        "name": str(rule.get("name", "")),
                        "severity": severity_name,
                        "reason": str(rule.get("reason", "")).strip(),
                    }
                )
    return triggered


def _base_risk_band(probability: float, threshold: float) -> str:
    if probability >= threshold:
        return "High"
    if probability >= (threshold - 0.15):
        return "Medium"
    return "Low"


def _escalate_band(band: str) -> str:
    if band == "Low":
        return "Medium"
    if band == "Medium":
        return "High"
    return band


def _unique_reasons(values: list[str], limit: int = 3) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def evaluate_hybrid_decision(
    row: dict[str, Any],
    ml_probability: float,
    model_threshold: float,
    rules_config: dict[str, Any],
    model_reasons: list[str] | None = None,
) -> dict[str, Any]:
    triggered = evaluate_rules(row, rules_config)
    critical_count = sum(1 for item in triggered if item["severity"] == "critical")
    band = _base_risk_band(float(ml_probability), float(model_threshold))
    if len(triggered) >= 2 and critical_count >= 1:
        band = _escalate_band(band)

    reason_candidates = [item["reason"] for item in triggered]
    if model_reasons:
        reason_candidates.extend(model_reasons)
    top_reasons = _unique_reasons(reason_candidates, limit=3)

    support_parts = [
        f"ML probability {ml_probability:.3f} against threshold {model_threshold:.3f}.",
    ]
    if triggered:
        support_parts.append(f"{len(triggered)} rule-based red flag(s) were triggered.")
    else:
        support_parts.append("No explicit rule-based red flags were triggered.")
    if top_reasons:
        support_parts.append("Key reasons: " + "; ".join(top_reasons))

    return {
        "ml_probability": float(ml_probability),
        "model_threshold": float(model_threshold),
        "ml_class": int(float(ml_probability) >= float(model_threshold)),
        "rule_flags_triggered": [item["name"] for item in triggered],
        "rule_flag_count": len(triggered),
        "critical_rule_count": critical_count,
        "risk_band": band,
        "top_reasons": top_reasons,
        "support_summary": " ".join(support_parts),
        "framing_message": str(rules_config.get("framing_message", "")).strip(),
    }

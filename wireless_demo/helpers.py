import math

import numpy as np
import pandas as pd
import streamlit as st

from .config import FEATURE_AGG_SUFFIXES, FEATURE_GLOSSARY


def to_df(X, cols):
    return pd.DataFrame(X, columns=cols)


def shap_pos(explainer, X_df):
    if explainer is None:
        return np.zeros((len(X_df), len(X_df.columns)))
    vals = explainer.shap_values(X_df)
    if isinstance(vals, list):
        return vals[1] if len(vals) > 1 else vals[0]
    return vals


def severity(prob, pval):
    high = (prob >= 0.85) or (pval is not None and pval <= 0.05)
    med = (prob >= 0.70) or (pval is not None and pval <= 0.20)
    return ("High", "red") if high else (("Medium", "orange") if med else ("Low", "green"))


def meters_to_latlon_offset(d_north_m, d_east_m, lat0):
    dlat = d_north_m / 111_111.0
    dlon = d_east_m / (111_111.0 * math.cos(math.radians(lat0)))
    return dlat, dlon


def rand_point_near(lat0, lon0, radius_m):
    r = radius_m * np.sqrt(np.random.rand())
    theta = 2 * np.pi * np.random.rand()
    dn, de = r * np.cos(theta), r * np.sin(theta)
    dlat, dlon = meters_to_latlon_offset(dn, de, lat0)
    return lat0 + dlat, lon0 + dlon


def haversine_m(lat1, lon1, lat2, lon2):
    radius = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def time_of_day_load(tick):
    return 0.5 + 0.5 * math.sin((tick % 600) / 600 * 2 * math.pi)


def fmt_eta(seconds):
    if seconds is None or not np.isfinite(seconds):
        return "—"
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    return f"{minutes:02d}:{secs:02d}"


def to_builtin(obj):
    if isinstance(obj, dict):
        return {str(key): to_builtin(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_builtin(value) for value in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    return obj


def fmt_pct(value):
    try:
        return f"{100 * float(value):.0f}%"
    except Exception:
        return "—"


def fmt_num(value):
    try:
        return f"{float(value):.2f}"
    except Exception:
        return str(value)


def feature_base(name: str) -> str:
    for suffix in FEATURE_AGG_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def feature_label(base: str) -> str:
    return FEATURE_GLOSSARY.get(base, base).split(":")[0]


def build_anomaly_explanation(incident: dict) -> str:
    feats = incident.get("features", {})
    reasons = incident.get("reasons", [])[:5]
    if not feats or not reasons:
        return "Model detected unusual patterns across several signals."

    lines = []
    for reason in reasons:
        base = feature_base(reason["feature"])
        z_score = feats.get(f"{base}_z", 0.0)
        last = feats.get(f"{base}_last")
        direction = "higher than normal" if z_score >= 0.8 else ("lower than normal" if z_score <= -0.8 else "unusually shifted")
        impact = float(reason["impact"])
        trend = "↑" if impact > 0 else "↓"
        label = feature_label(base)
        last_str = f" (now {fmt_num(last)})" if last is not None else ""
        lines.append(
            f"- {trend} **{label}** looked **{direction}** (z={z_score:+.2f}){last_str}; contributed {impact:+.2f} to anomaly."
        )

    p_value = incident.get("p_value")
    if p_value is not None:
        lines.append(f"- Confidence: conformal **p-value={p_value:.3f}** (lower ⇒ stronger evidence).")
    else:
        lines.append("- Confidence: model probability only (conformal off).")
    return "\n".join(lines)


def build_type_explanation(incident: dict) -> str:
    label = incident.get("type_label", "Unknown")
    confidence = incident.get("type_conf")
    fused = incident.get("type_probs_fused")
    ml_probs = incident.get("type_probs_ml")
    rules = incident.get("type_scores_rules")
    classes = incident.get("type_classes", ["Breach", "Jamming", "Spoof", "Tamper"])
    parts = []

    if label != "Unknown":
        if confidence is not None:
            parts.append(f"**Predicted type:** **{label}** with fused confidence **{fmt_pct(confidence)}**.")
        else:
            parts.append(f"**Predicted type:** **{label}** (rules fallback).")
    else:
        parts.append("Type head abstained (low confidence).")

    if fused and ml_probs and rules:
        rows = ["| Type | Fused | ML | Rules |", "|---|---:|---:|---:|"]
        for index, cls in enumerate(classes):
            rows.append(f"| {cls} | {fmt_pct(fused[index])} | {fmt_pct(ml_probs[index])} | {fmt_pct(rules[index])} |")
        parts.append("\n".join(rows))

    hints = {
        "Jamming": "Signals consistent with interference: ↓SNR/SINR, ↑noise floor, ↑errors (BLER/PHY), ↑loss/latency.",
        "Breach": "Access anomalies: ↑deauth & association churn, ↑auth/DHCP issues, **rogue_rssi_gap > 0**.",
        "Spoof": "GNSS inconsistency: ↑position error with odd HDOP, fewer sats, Doppler/clock/C/N0 oddities.",
        "Tamper": "Integrity anomalies: ↑duplicates/sequence gaps/timestamp skew, ↑schema/HMAC/CRC issues.",
    }
    base_label = label.replace(" (low conf)", "").replace(" (rules)", "")
    if base_label in hints:
        parts.append(f"**Domain evidence:** {hints[base_label]}")

    type_reasons = incident.get("type_reasons", [])[:4]
    if type_reasons:
        bullets = []
        for reason in type_reasons:
            base = feature_base(reason["feature"])
            bullets.append(f"- {feature_label(base)}: impact {reason['impact']:+.2f}")
        parts.append("**Most influential signals (type head):**\n" + "\n".join(bullets))

    return "\n\n".join(parts)


def conformal_pvalue(prob):
    cal_scores = st.session_state.get("conformal_scores")
    if cal_scores is None:
        return None
    nonconformity = 1 - prob
    return float((np.sum(cal_scores >= nonconformity) + 1) / (len(cal_scores) + 1))

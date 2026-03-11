import json
import time
from pathlib import Path

import streamlit as st

from .config import CFG


REVIEW_STORE_PATH = Path(__file__).resolve().parent.parent / ".demo_state" / "hitl_reviews.json"
DEFAULT_STATUS = "Pending Review"
REVIEW_STATUSES = [DEFAULT_STATUS, "Approved", "False Positive", "Escalated"]


def scenario_group_name(scenario):
    for category in ["Jamming", "Access Breach", "GPS Spoofing", "Data Tamper"]:
        if str(scenario).startswith(category):
            return category
    return str(scenario)


def incident_review_key(incident):
    return f"{incident['device_id']}_{incident['ts']}_{incident['tick']}"


def load_review_log():
    if not REVIEW_STORE_PATH.exists():
        return {}
    try:
        return json.loads(REVIEW_STORE_PATH.read_text())
    except Exception:
        return {}


def save_review_log(review_log):
    REVIEW_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_STORE_PATH.write_text(json.dumps(review_log, indent=2, sort_keys=True))


def ensure_review_log():
    if "review_log" not in st.session_state:
        st.session_state.review_log = load_review_log()
    return st.session_state.review_log


def get_review_record(incident):
    return ensure_review_log().get(
        incident_review_key(incident),
        {
            "status": DEFAULT_STATUS,
            "note": "",
            "reviewed_at": None,
            "reviewer_role": None,
        },
    )


def get_review_status(incident):
    return get_review_record(incident).get("status", DEFAULT_STATUS)


def sync_legacy_labels(review_log):
    labels = {}
    for key, record in review_log.items():
        status = record.get("status", DEFAULT_STATUS)
        if status == DEFAULT_STATUS:
            continue
        labels[key] = {
            "ack": status in {"Approved", "False Positive", "Escalated"},
            "false_positive": status == "False Positive",
            "status": status,
            "note": record.get("note", ""),
            "reviewer_role": record.get("reviewer_role"),
        }
    st.session_state.incident_labels = labels


def record_review(incident, status, reviewer_role, note=""):
    if status not in REVIEW_STATUSES:
        raise ValueError(f"Unsupported review status: {status}")

    review_log = ensure_review_log()
    key = incident_review_key(incident)
    review_log[key] = {
        "incident_key": key,
        "status": status,
        "note": note.strip(),
        "reviewed_at": int(time.time()),
        "reviewer_role": reviewer_role,
        "device_id": incident.get("device_id"),
        "scenario": incident.get("scenario"),
        "severity": incident.get("severity"),
        "prob": incident.get("prob"),
        "type_label": incident.get("type_label") or incident.get("type"),
        "tick": incident.get("tick"),
    }
    st.session_state.review_log = review_log
    sync_legacy_labels(review_log)
    save_review_log(review_log)
    return review_log[key]


def review_rows():
    rows = list(ensure_review_log().values())
    return sorted(rows, key=lambda row: row.get("reviewed_at") or 0, reverse=True)


def latest_review_for_device(device_id, scenario=None):
    target_group = scenario_group_name(scenario) if scenario else None
    for row in review_rows():
        if row.get("device_id") != device_id:
            continue
        if target_group is not None and scenario_group_name(row.get("scenario", "")) != target_group:
            continue
        return row
    return None


def get_device_review_effect(device_id, scenario, tick):
    latest = latest_review_for_device(device_id, scenario)
    if latest is None:
        return {"status": DEFAULT_STATUS, "suppress": False, "prioritize": False, "reason": None}

    status = latest.get("status", DEFAULT_STATUS)
    reviewed_tick = latest.get("tick")
    suppression_enabled = st.session_state.get("hitl_suppression_enabled", CFG.hitl_suppression_enabled)
    suppression_ticks = int(st.session_state.get("hitl_suppression_ticks", CFG.hitl_suppression_ticks))
    suppress = False
    prioritize = False
    reason = None

    if (
        suppression_enabled
        and status == "False Positive"
        and reviewed_tick is not None
        and tick <= int(reviewed_tick) + suppression_ticks
    ):
        suppress = True
        reason = f"Suppressed duplicate after human false-positive review at tick {reviewed_tick}."
    elif status == "Escalated":
        prioritize = True
        reason = "Prioritized because this device was previously escalated by a human reviewer."
    elif status == "Approved":
        reason = "Human reviewer previously confirmed similar behavior for this device."

    return {
        "status": status,
        "suppress": suppress,
        "prioritize": prioritize,
        "reason": reason,
        "review_record": latest,
    }


def current_hitl_policy():
    return {
        "suppression_enabled": st.session_state.get("hitl_suppression_enabled", CFG.hitl_suppression_enabled),
        "suppression_ticks": int(st.session_state.get("hitl_suppression_ticks", CFG.hitl_suppression_ticks)),
        "escalation_boost": float(st.session_state.get("hitl_escalation_boost", CFG.hitl_escalation_boost)),
    }

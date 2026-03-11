import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from .helpers import (
    build_anomaly_explanation,
    build_type_explanation,
    conformal_pvalue,
    feature_base,
    feature_label,
    shap_pos,
)
from .hitl import get_review_record, get_review_status, incident_review_key, record_review
from .logic import feature_cols_cached


ROLE_INCIDENT_COPY = {
    "End User": {
        "details": "Open plain-language detail",
        "snapshot": "Incident snapshot",
    },
    "Domain Expert": {
        "details": "Open analyst detail",
        "snapshot": "Incident snapshot",
    },
    "AI Builder": {
        "details": "Open model detail",
        "snapshot": "Model payload",
    },
    "Executive": {
        "title": "Business summary",
        "meta": "Operational context",
        "probability": "AI risk score",
        "pvalue": "Confidence check",
        "category": "Threat family",
        "device": "Affected asset",
        "evidence": "Why this matters",
        "review_status": "Decision status",
        "note": "Leadership note",
        "approve": "Accept alert",
        "false_positive": "Dismiss alert",
        "escalate": "Escalate response",
        "details": "Open supporting detail",
        "snapshot": "Raw incident payload",
        "approved": "Accepted",
        "false_positive_status": "Dismissed",
    },
    "Regulator": {
        "title": "Review summary",
        "meta": "Oversight context",
        "probability": "Model risk score",
        "pvalue": "Confidence check",
        "category": "Threat family",
        "device": "Affected asset",
        "evidence": "Visible evidence",
        "review_status": "Human review status",
        "note": "Reviewer note",
        "approve": "Record approved",
        "false_positive": "Record false positive",
        "escalate": "Record escalation",
        "details": "Open technical detail",
        "snapshot": "Audit payload",
        "approved": "Approved",
        "false_positive_status": "False Positive",
    },
}


def _incident_role_copy(role):
    return ROLE_INCIDENT_COPY.get(role, {})


def _status_display(status, role):
    copy = _incident_role_copy(role)
    if status == "Approved":
        return copy.get("approved", status)
    if status == "False Positive":
        return copy.get("false_positive_status", status)
    return status


def incident_category(incident):
    scenario = incident.get("scenario", "")
    for category in ["Jamming", "Access Breach", "GPS Spoofing", "Data Tamper"]:
        if scenario.startswith(category):
            return category
    return "Other"


def incident_id(incident):
    return f"{incident['device_id']}_{incident['ts']}_{incident['tick']}"


def get_device_history(device_id, fields):
    buf = st.session_state.dev_buf.get(device_id, [])
    if not buf:
        return pd.DataFrame()
    df = pd.DataFrame(list(buf))
    return df[fields] if all(field in df.columns for field in fields) else df


def _metric_chip(label, value):
    return (
        "<div class='metric-chip'>"
        f"<div class='metric-chip-label'>{label}</div>"
        f"<div class='metric-chip-value'>{value}</div>"
        "</div>"
    )


def _severity_color(severity_level):
    return {
        "High": "#b91c1c",
        "Medium": "#c2410c",
        "Low": "#15803d",
    }.get(severity_level, "#475569")


def _incident_type_value(incident):
    type_label = incident.get("type_label", "Unknown")
    type_conf = incident.get("type_conf")
    return f"{type_label} · {type_conf * 100:.0f}%" if type_conf is not None else type_label


def _top_reason_lines(incident, limit=3):
    reasons = incident.get("reasons", [])[:limit]
    if not reasons:
        return ["Model confidence is driven by several smaller signals rather than one dominant feature."]
    return [
        f"{feature_label(feature_base(item['feature']))} changed materially for this device (impact {item['impact']:+.2f})."
        for item in reasons
    ]


def _type_probability_frame(incident):
    classes = incident.get("type_classes") or ["Breach", "Jamming", "Spoof", "Tamper"]
    fused = incident.get("type_probs_fused") or []
    ml_probs = incident.get("type_probs_ml") or []
    rules = incident.get("type_scores_rules") or []
    rows = []
    for index, label in enumerate(classes):
        rows.append(
            {
                "type": label,
                "fused": fused[index] if index < len(fused) else None,
                "ml": ml_probs[index] if index < len(ml_probs) else None,
                "rules": rules[index] if index < len(rules) else None,
            }
        )
    return pd.DataFrame(rows)


def _snapshot_payload_for_role(incident, role):
    base_payload = {
        "device_id": incident.get("device_id"),
        "scenario": incident.get("scenario"),
        "tick": incident.get("tick"),
        "severity": incident.get("severity"),
        "type_label": incident.get("type_label") or incident.get("type"),
    }

    if role == "End User":
        base_payload.update(
            {
                "what_happened": f"{incident_category(incident)} behavior was detected on this device.",
                "ai_risk_score": round(float(incident.get("prob", 0.0)), 2),
                "recommended_action": "Review, dismiss, or escalate based on operational context.",
            }
        )
        return base_payload

    if role == "Executive":
        base_payload.update(
            {
                "business_risk": f"{incident.get('severity', 'Low')} urgency",
                "ai_risk_score": round(float(incident.get("prob", 0.0)), 2),
                "human_review_status": incident.get("review_status", "Pending Review"),
            }
        )
        return base_payload

    if role == "Regulator":
        base_payload.update(
            {
                "model_probability": round(float(incident.get("prob", 0.0)), 4),
                "p_value": incident.get("p_value"),
                "review_status": incident.get("review_status", "Pending Review"),
                "review_priority": incident.get("review_priority"),
                "hitl_reason": incident.get("hitl_reason"),
            }
        )
        return base_payload

    if role == "AI Builder":
        return {
            **base_payload,
            "prob": incident.get("prob"),
            "p_value": incident.get("p_value"),
            "type": incident.get("type"),
            "type_conf": incident.get("type_conf"),
            "type_margin": incident.get("type_margin"),
            "type_probs_fused": incident.get("type_probs_fused"),
            "type_probs_ml": incident.get("type_probs_ml"),
            "type_scores_rules": incident.get("type_scores_rules"),
            "queue_score": incident.get("queue_score"),
        }

    if role == "Domain Expert":
        return {
            **base_payload,
            "prob": incident.get("prob"),
            "p_value": incident.get("p_value"),
            "review_status": incident.get("review_status", "Pending Review"),
            "top_reasons": incident.get("reasons", [])[:3],
        }

    return {
        **base_payload,
        "prob": incident.get("prob"),
        "p_value": incident.get("p_value"),
    }


def _render_end_user_details(incident):
    st.markdown("#### What happened")
    st.markdown(
        f"The system flagged **{incident['device_id']}** for **{incident_category(incident)}** behavior with **{incident.get('severity', 'Low')}** severity."
    )
    st.markdown("#### What to do next")
    for line in _top_reason_lines(incident):
        st.markdown(f"- {line}")
    st.info("Use the review actions above to confirm whether this device needs follow-up, dismissal, or escalation.")
    st.markdown("#### Why the system flagged it")
    st.markdown(build_type_explanation(incident))


def _render_domain_expert_details(incident, scope):
    detail_tabs = st.tabs(["Evidence", "Attack rationale", "Device inspector"])
    with detail_tabs[0]:
        st.markdown(build_anomaly_explanation(incident))
    with detail_tabs[1]:
        st.markdown(build_type_explanation(incident))
    with detail_tabs[2]:
        render_device_inspector_from_incident(incident, topk=8, scope=scope)


def _render_regulator_details(incident):
    st.markdown("#### Human oversight")
    st.markdown(
        f"This incident is presented as a reviewable output for **{incident_category(incident)}**. The current human status is **{incident.get('review_status', 'Pending Review')}**."
    )
    st.markdown("#### Visible evidence")
    st.markdown(build_anomaly_explanation(incident))
    st.markdown("#### Audit-facing rationale")
    st.markdown(build_type_explanation(incident))


def _render_ai_builder_details(incident):
    detail_tabs = st.tabs(["Model decision", "Attack typing", "Probability fusion"])
    with detail_tabs[0]:
        st.markdown(build_anomaly_explanation(incident))
    with detail_tabs[1]:
        st.markdown(build_type_explanation(incident))
    with detail_tabs[2]:
        frame = _type_probability_frame(incident)
        if len(frame) > 0:
            st.dataframe(frame, width="stretch")
        else:
            st.info("Type probability breakdown is not available for this incident.")


def _render_executive_details(incident):
    st.markdown("#### Business summary")
    st.markdown(
        f"**{incident_category(incident)}** behavior is affecting **{incident['device_id']}** with **{incident.get('severity', 'Low')}** urgency and AI risk score **{incident.get('prob', 0.0):.2f}**."
    )
    st.markdown("#### Why leadership should care")
    for line in _top_reason_lines(incident):
        st.markdown(f"- {line}")
    st.markdown("#### Supporting rationale")
    st.markdown(build_type_explanation(incident))


def render_incident_body_for_role(incident, role, scope="main"):
    p_value = incident.get("p_value")
    pval_str = f"{p_value:.3f}" if p_value is not None else "—"
    severity = incident.get("severity", "—")
    st.markdown(
        "<div class='metric-strip'>"
        + _metric_chip("Severity", severity)
        + _metric_chip("Anomaly Prob.", f"{incident['prob']:.2f}")
        + _metric_chip("p-value", pval_str)
        + _metric_chip("Attack Type", _incident_type_value(incident))
        + "</div>",
        unsafe_allow_html=True,
    )

    if role == "Domain Expert":
        _render_domain_expert_details(incident, scope)
        return
    if role == "End User":
        _render_end_user_details(incident)
        return
    if role == "Regulator":
        _render_regulator_details(incident)
        return
    if role == "AI Builder":
        _render_ai_builder_details(incident)
        return
    if role == "Executive":
        _render_executive_details(incident)
        return

    st.markdown(build_anomaly_explanation(incident))
    st.markdown(build_type_explanation(incident))


def render_device_inspector_from_incident(incident, topk=8, scope="main"):
    feats = incident.get("features") or st.session_state.last_features.get(incident["device_id"])
    if not feats:
        st.info("Not enough samples for device window yet.")
        return

    base_key = f"{incident_id(incident)}_{scope}"
    x_frame = pd.DataFrame([feats]).fillna(0.0)
    cols = feature_cols_cached()
    x_frame = x_frame.reindex(columns=cols, fill_value=0.0)
    x_scaled = st.session_state.scaler.transform(x_frame)
    x_scaled_df = pd.DataFrame(x_scaled, columns=cols)
    prob = float(st.session_state.model.predict_proba(x_scaled_df)[:, 1][0])

    st.markdown(
        "<div class='inspector-note'><strong>Inspector view:</strong> "
        "Use the contribution chart to see what pushed the alert, then compare those signals "
        "against recent telemetry for the same device.</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='metric-strip'>"
        + _metric_chip("Device", incident["device_id"])
        + _metric_chip("Scenario", incident.get("scenario", "—"))
        + _metric_chip("Anomaly Prob.", f"{prob * 100:.0f}%")
        + _metric_chip("Attack Type", incident.get("type_label", incident.get("type", "Unknown")))
        + "</div>",
        unsafe_allow_html=True,
    )

    shap_vec = shap_pos(st.session_state.explainer, x_scaled_df)[0]
    pairs = sorted(zip(cols, shap_vec), key=lambda kv: abs(kv[1]), reverse=True)[:topk]
    df_shap = pd.DataFrame(pairs, columns=["feature", "impact"])

    history = get_device_history(incident["device_id"], ["snr", "packet_loss", "latency_ms", "pos_error_m"])
    tabs = st.tabs(["Contributors", "Telemetry", "Features"])

    with tabs[0]:
        col1, col2 = st.columns([1, 1.7])
        gauge = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=prob * 100,
                number={"suffix": "%"},
                gauge={
                    "axis": {"range": [0, 100]},
                    "threshold": {
                        "line": {"color": "red", "width": 3},
                        "thickness": 0.8,
                        "value": st.session_state.get("th_slider", 0.75) * 100,
                    },
                },
            )
        )
        col1.plotly_chart(gauge, use_container_width=True, key=f"gauge_{base_key}")
        fig = px.bar(
            df_shap.sort_values("impact"),
            x="impact",
            y="feature",
            orientation="h",
            title=f"Top local contributions — {incident['device_id']}",
            labels={"impact": "contribution → anomaly", "feature": "feature"},
        )
        fig.update_layout(margin=dict(l=10, r=10, t=40, b=10))
        col2.plotly_chart(fig, use_container_width=True, key=f"local_shap_{base_key}")

    with tabs[1]:
        if len(history) > 0:
            history = history.reset_index(drop=True)
            col1, col2 = st.columns(2)
            col1.plotly_chart(px.line(history, y="snr", title="SNR (last window)"), use_container_width=True, key=f"hist_snr_{base_key}")
            col1.plotly_chart(px.line(history, y="packet_loss", title="Packet loss % (last window)"), use_container_width=True, key=f"hist_loss_{base_key}")
            col2.plotly_chart(px.line(history, y="latency_ms", title="Latency ms (last window)"), use_container_width=True, key=f"hist_latency_{base_key}")
            col2.plotly_chart(px.line(history, y="pos_error_m", title="GNSS error m (last window)"), use_container_width=True, key=f"hist_gnss_{base_key}")
        else:
            st.info("Recent telemetry is not available for this device yet.")

    with tabs[2]:
        st.dataframe(x_scaled_df.T.rename(columns={0: "z-value"}), width="stretch")


def render_incident_card(incident, role, scope="main"):
    review_key = incident_review_key(incident)
    base_key = f"{review_key}_{scope}"
    p_value = incident.get("p_value")
    pval_str = f"{p_value:.3f}" if p_value is not None else "—"
    severity = incident.get("severity", "—")
    color = _severity_color(severity)
    badge = f"<span class='severity-pill' style='background:{color};'>{severity}</span>"
    reasons = incident.get("reasons", [])[:3]
    type_label = incident.get("type_label") or incident.get("type", "Unknown")
    review_record = get_review_record(incident)
    review_status = get_review_status(incident)
    copy = _incident_role_copy(role)
    meta_label = copy.get("meta")
    evidence_label = copy.get("evidence", "Top evidence signals")
    review_status_label = copy.get("review_status", "Review status")
    note_label = copy.get("note", "Reviewer note")
    details_label = copy.get("details", "Open incident details")
    snapshot_label = copy.get("snapshot", "Incident snapshot")
    displayed_status = _status_display(review_status, role)
    meta_text = f"{incident['scenario']} · tick {incident['tick']} · model type {incident['type']}"
    if meta_label:
        meta_text = f"{meta_label}: {meta_text}"

    cols = st.columns([1.8, 1])
    with cols[0]:
        st.markdown(
            f"""
            <div class='incident-card'>
                <div class='incident-header'>
                    <div>
                        <div class='incident-title'>{incident['device_id']} · {type_label}</div>
                        <div class='incident-meta'>{meta_text}</div>
                    </div>
                    <div>{badge}</div>
                </div>
                <div class='metric-strip'>
                    {_metric_chip(copy.get('probability', 'Probability'), f"{incident['prob']:.2f}")}
                    {_metric_chip(copy.get('pvalue', 'p-value'), pval_str)}
                    {_metric_chip(copy.get('category', 'Category'), incident_category(incident))}
                    {_metric_chip(copy.get('device', 'Device'), incident['device_id'])}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if reasons:
            concise = [
                f"- {feature_label(feature_base(item['feature']))}: impact {item['impact']:+.2f}"
                for item in reasons
            ]
            st.markdown(f"**{evidence_label}**")
            st.markdown(f"<ul class='reason-list'><li>{'</li><li>'.join(item[2:] for item in concise)}</li></ul>", unsafe_allow_html=True)

        st.caption(f"{review_status_label}: **{displayed_status}**")
        note_key = f"review_note_{base_key}"
        st.text_area(note_label, value=review_record.get("note", ""), key=note_key, height=70)

        action_cols = st.columns(3)
        if action_cols[0].button(copy.get("approve", "Approve alert"), key=f"approve_{base_key}", use_container_width=True):
            review_record = record_review(incident, "Approved", role, st.session_state.get(note_key, ""))
            review_status = review_record["status"]
        if action_cols[1].button(copy.get("false_positive", "Mark false positive"), key=f"fp_{base_key}", use_container_width=True):
            review_record = record_review(incident, "False Positive", role, st.session_state.get(note_key, ""))
            review_status = review_record["status"]
        if action_cols[2].button(copy.get("escalate", "Escalate"), key=f"esc_{base_key}", use_container_width=True):
            review_record = record_review(incident, "Escalated", role, st.session_state.get(note_key, ""))
            review_status = review_record["status"]
        displayed_status = _status_display(review_status, role)

        if review_status != "Pending Review":
            reviewer = review_record.get("reviewer_role") or role
            note = review_record.get("note", "")
            st.caption(f"Human decision: **{displayed_status.upper()}** · reviewer: {reviewer}")
            if note:
                st.caption(f"Review note: {note}")
        with st.expander(details_label):
            render_incident_body_for_role(incident, role, scope=scope)

    with cols[1]:
        st.markdown(f"**{snapshot_label}**")
        st.json(_snapshot_payload_for_role(incident, role))

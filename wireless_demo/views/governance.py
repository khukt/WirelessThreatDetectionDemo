import streamlit as st
import pandas as pd

from ..hitl import current_hitl_policy, incident_review_key, review_rows
from ..training import render_training_explainer
from ..ux import render_focus_callout, render_section_card, render_summary_list, render_tab_intro


@st.cache_data(show_spinner=False)
def _prepare_review_audit_artifacts(review_records_json: str):
    review_df = pd.read_json(review_records_json)
    if "reviewed_at" in review_df.columns:
        review_df["reviewed_at"] = pd.to_datetime(review_df["reviewed_at"], unit="s").dt.strftime("%Y-%m-%d %H:%M:%S")
    display_cols = [col for col in ["reviewed_at", "reviewer_role", "status", "device_id", "scenario", "severity", "type_label", "note"] if col in review_df.columns]
    export_json = review_df.to_json(orient="records", indent=2)
    return review_df, display_cols, export_json


ROLE_GOVERNANCE_CALLOUT = {
    "End User": "This page explains the controls behind the demo, but it is secondary to day-to-day triage.",
    "Domain Expert": "Use governance to confirm that oversight, logging, and review controls support your operational decisions.",
    "Regulator": "This is the main page for the 7 Pillars, auditability, oversight controls, and current governance gaps.",
    "AI Builder": "Use this page to review which trust controls are implemented already and where the technical roadmap still has gaps.",
    "Executive": "Use this page to understand trust, accountability, and compliance readiness at a leadership level.",
}


ROLE_GOVERNANCE_SUMMARY = {
    "Executive": {
        "title": "Leadership summary",
        "bullets": [
            "The demo keeps humans in the loop for every incident decision.",
            "Transparency and audit trails are visible, but some governance controls are still roadmap items.",
            "The strongest current areas are oversight and transparency; fairness and broader impact controls remain gaps.",
        ],
    },
    "Regulator": {
        "title": "Assurance summary",
        "bullets": [
            "Human review, audit logging, and visible escalation paths are present in the demo workflow.",
            "Transparency artifacts are exposed inline, including model logic, confidence controls, and review history.",
            "Several pillars remain partial or gap-level because formal governance, fairness measurement, and impact assessment are not yet implemented.",
        ],
    },
}


def _render_role_governance_summary(role):
    summary = ROLE_GOVERNANCE_SUMMARY.get(role)
    if not summary:
        return
    render_summary_list(summary["title"], summary["bullets"], kicker="Audience summary")
PILLAR_STATUS_STYLE = {
    "Strong": "background: rgba(22, 163, 74, 0.14); color: #166534;",
    "Partial": "background: rgba(245, 158, 11, 0.16); color: #92400e;",
    "Gap": "background: rgba(239, 68, 68, 0.14); color: #991b1b;",
}


TRUSTWORTHY_AI_PILLARS = [
    {
        "title": "Human Agency and Oversight",
        "status": "Strong",
        "evidence": "Human review states, escalation, false-positive handling, and HITL policy controls are active in the incident workflow.",
        "gap": "Still a demo; there is no formal approval workflow tied to downstream real-world enforcement.",
        "next_actions": [
            "Add explicit reviewer assignment and approval ownership.",
            "Show escalation paths and who is accountable for each step.",
            "Require approval before any future automated enforcement action.",
        ],
    },
    {
        "title": "Technical Robustness and Safety",
        "status": "Partial",
        "evidence": "The app uses calibrated confidence, thresholding, conformal p-values, and fallback rule fusion for type decisions.",
        "gap": "It does not provide formal safety cases, adversarial testing coverage, or production-grade fail-safe controls.",
        "next_actions": [
            "Add stress tests for noisy and adversarial telemetry.",
            "Document fail-safe behavior when models or data are unavailable.",
            "Track robustness metrics across scenarios and refresh cycles.",
        ],
    },
    {
        "title": "Privacy and Data Governance",
        "status": "Partial",
        "evidence": "The demo uses synthetic telemetry, which reduces personal-data exposure and simplifies governance concerns.",
        "gap": "It does not yet expose retention policy, access control, lineage, consent, or data stewardship controls.",
        "next_actions": [
            "Add a data lineage and retention summary in Governance.",
            "Expose who can access logs, reviews, and model artifacts.",
            "Document what would change if real telemetry replaced synthetic data.",
        ],
    },
    {
        "title": "Transparency",
        "status": "Strong",
        "evidence": "The app explains model flow, feature impact, calibration, attack typing logic, and keeps a local human review audit log.",
        "gap": "There is room for even clearer end-user explanation text on limitations and confidence uncertainty.",
        "next_actions": [
            "Add uncertainty guidance directly beside live incident cards.",
            "Show known model limitations for each scenario in plain language.",
            "Provide a one-page summary export for non-technical stakeholders.",
        ],
    },
    {
        "title": "Diversity, Non-discrimination and Fairness",
        "status": "Gap",
        "evidence": "The app distinguishes device types and roles, but it does not currently measure fairness or subgroup performance.",
        "gap": "No fairness metrics, bias checks, or comparative error analysis by subgroup are implemented yet.",
        "next_actions": [
            "Evaluate error rates by device type, scenario, and operating profile.",
            "Add subgroup drift and disparate performance checks.",
            "Show fairness findings in Governance with mitigation notes.",
        ],
    },
    {
        "title": "Societal and Environmental Well-being",
        "status": "Gap",
        "evidence": "The app frames itself as a decision-support demo rather than autonomous control for critical infrastructure.",
        "gap": "No explicit societal impact, sustainability, or broader public-interest assessment is shown in the current UI.",
        "next_actions": [
            "Add a short impact assessment for critical infrastructure use cases.",
            "Document operational benefits, risks, and potential unintended harms.",
            "Include basic compute and sustainability considerations for model refresh cycles.",
        ],
    },
    {
        "title": "Accountability",
        "status": "Partial",
        "evidence": "Reviewer actions are logged, downloadable, and visible in governance, which supports traceability and auditability.",
        "gap": "There is no formal ownership matrix, sign-off workflow, incident escalation chain, or policy attestation layer.",
        "next_actions": [
            "Define ownership for model updates, approvals, and incidents.",
            "Add sign-off records for major model refreshes.",
            "Link review logs to a simple responsibility matrix in Governance.",
        ],
    },
]


def _render_pillar_card(pillar):
    style = PILLAR_STATUS_STYLE.get(pillar["status"], PILLAR_STATUS_STYLE["Gap"])
    st.markdown(
        f"""
        <div class="pillar-card">
            <div class="pillar-title">{pillar['title']}</div>
            <div class="pillar-status" style="{style}">{pillar['status']}</div>
            <div class="pillar-copy"><strong>Evidence in app:</strong> {pillar['evidence']}</div>
            <div class="pillar-copy"><strong>Current gap:</strong> {pillar['gap']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander(f"Roadmap for {pillar['title']}", expanded=False):
        st.markdown("**Next actions**")
        st.markdown("\n".join([f"- {action}" for action in pillar.get("next_actions", [])]))


def render_governance_tab(role):
    nonce = st.session_state.ui_nonce
    render_tab_intro("Governance", role)
    render_section_card(
        "EU AI Act — Transparency & Governance",
        "This page shows the trust controls, human oversight, and governance gaps visible in the demo.",
        kicker="Trust overview",
    )
    _render_role_governance_summary(role)
    render_section_card(
        "EU Trustworthy AI — 7 Pillars",
        "Status is shown as Strong, Partial, or Gap based on the controls currently visible in the app.",
        kicker="Pillar view",
    )

    pillar_cols = st.columns(2)
    for idx, pillar in enumerate(TRUSTWORTHY_AI_PILLARS):
        with pillar_cols[idx % 2]:
            _render_pillar_card(pillar)

    with st.expander("Open implementation detail", expanded=False):
        mid_left, mid_right = st.columns(2)
        with mid_left:
            with st.container(border=True):
                st.markdown("#### Training lifecycle")
                st.markdown(
                    "- **Data generation**: synthetic, physics-inspired telemetry.  \n"
                    "- **Windows & features**: rolling-window statistics.  \n"
                    "- **Binary detector**: LightGBM with conformal p-values.  \n"
                    "- **Type head**: LightGBM multiclass + rules.  \n"
                    "- **Thresholding**: suggested threshold = max F1 on validation split."
                )
        with mid_right:
            with st.container(border=True):
                st.markdown("#### Human-in-the-loop controls")
                st.markdown(
                    "- **Review states**: approve, false positive, or escalate.  \n"
                    "- **Audit trail**: reviewer role, timestamp, and note are persisted locally.  \n"
                    "- **Feedback set**: reviewed incidents can inform future tuning or retraining."
                )

    policy = current_hitl_policy()
    render_section_card(
        "Live oversight status",
        "This panel summarizes the active HITL policy and current review outcomes.",
        kicker="Operations snapshot",
    )
    st.caption(
        f"Active HITL policy · suppression: {'enabled' if policy['suppression_enabled'] else 'disabled'} · "
        f"window: {policy['suppression_ticks']} ticks · escalation boost: {policy['escalation_boost']:.2f}"
    )

    reviews = review_rows()
    status_counts = {status: 0 for status in ["Pending Review", "Approved", "False Positive", "Escalated"]}
    for incident in st.session_state.incidents:
        matched = next((row for row in reviews if row.get("incident_key") == incident_review_key(incident)), None)
        status = matched.get("status") if matched else "Pending Review"
        status_counts[status] = status_counts.get(status, 0) + 1

    with st.container(border=True):
        cols = st.columns(4)
        cols[0].metric("Pending review", status_counts["Pending Review"])
        cols[1].metric("Approved", status_counts["Approved"])
        cols[2].metric("False positives", status_counts["False Positive"])
        cols[3].metric("Escalated", status_counts["Escalated"])

    hitl_live_stats = st.session_state.get("hitl_live_stats", {})
    with st.container(border=True):
        live_cols = st.columns(3)
        live_cols[0].metric("Suppressed repeats", hitl_live_stats.get("suppressed_alerts", 0))
        live_cols[1].metric("Prioritized alerts", hitl_live_stats.get("prioritized_alerts", 0))
        latest_effect = hitl_live_stats.get("last_effect")
        live_cols[2].metric("Latest HITL effect", latest_effect.get("effect", "None") if latest_effect else "None")
    if latest_effect:
        st.caption(
            f"Latest live intervention: {latest_effect['effect']} {latest_effect['device_id']} at tick {latest_effect['tick']} · {latest_effect.get('reason') or 'No reason recorded.'}"
        )

    render_section_card(
        "Audit trail",
        "Recent review actions can be inspected and exported.",
        kicker="Traceability",
    )
    if reviews:
        with st.container(border=True):
            st.caption("Recent human review log")
            reviews_json = pd.DataFrame(reviews).to_json(orient="records")
            review_df, display_cols, export_json = _prepare_review_audit_artifacts(reviews_json)
            st.dataframe(review_df[display_cols], width="stretch", hide_index=True)
            st.download_button(
                "Download review audit log",
                data=export_json,
                file_name="hitl_review_log.json",
                mime="application/json",
                use_container_width=True,
            )
    else:
            render_focus_callout("Audit trail empty", "Triage incidents to generate human review records and populate the audit trail.")

    with st.expander("Open technical training detail", expanded=False):
        render_training_explainer(nonce)


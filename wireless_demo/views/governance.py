import streamlit as st
import pandas as pd
from textwrap import dedent

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
            "Human review remains in control of incident decisions.",
            "Audit and transparency evidence are visible in the app.",
            "The largest remaining gaps are fairness, impact assessment, and formal accountability.",
        ],
    },
    "Regulator": {
        "title": "Assurance summary",
        "bullets": [
            "Human review, audit logging, and escalation are visible in the workflow.",
            "Model logic, confidence checks, and review history are exposed inline.",
            "Formal governance, fairness measurement, and impact assessment are still incomplete.",
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

PILLAR_STATUS_VARIANT = {
    "Strong": "success",
    "Partial": "warning",
    "Gap": "warning",
}

PILLAR_GROUP_META = {
    "Strong": {
        "title": "Implemented well in the demo",
        "copy": "These controls are already easy to show and explain.",
        "badge_class": "governance-group-badge--strong",
    },
    "Partial": {
        "title": "Visible, but incomplete",
        "copy": "These controls exist, but they need stronger process or measurement support.",
        "badge_class": "governance-group-badge--partial",
    },
    "Gap": {
        "title": "Still roadmap-level",
        "copy": "These areas are not mature enough yet to support a strong governance claim.",
        "badge_class": "governance-group-badge--gap",
    },
}

PILLAR_STATUS_SCORE = {
    "Strong": 1.0,
    "Partial": 0.5,
    "Gap": 0.0,
}


TRUSTWORTHY_AI_PILLARS = [
    {
        "title": "Human Agency and Oversight",
        "status": "Strong",
        "evidence": "Review states, escalation, and false-positive handling are active in the incident flow.",
        "gap": "There is no formal approval chain for real-world enforcement.",
        "next_actions": [
            "Add explicit reviewer assignment and approval ownership.",
            "Show escalation paths and who is accountable for each step.",
            "Require approval before any future automated enforcement action.",
        ],
    },
    {
        "title": "Technical Robustness and Safety",
        "status": "Partial",
        "evidence": "The app uses calibrated confidence, thresholding, and rule fallback.",
        "gap": "Formal safety cases, adversarial testing, and fail-safe controls are not shown.",
        "next_actions": [
            "Add stress tests for noisy and adversarial telemetry.",
            "Document fail-safe behavior when models or data are unavailable.",
            "Track robustness metrics across scenarios and refresh cycles.",
        ],
    },
    {
        "title": "Privacy and Data Governance",
        "status": "Partial",
        "evidence": "Synthetic telemetry reduces privacy exposure in the demo.",
        "gap": "Retention, access control, lineage, and stewardship are not yet surfaced.",
        "next_actions": [
            "Add a data lineage and retention summary in Governance.",
            "Expose who can access logs, reviews, and model artifacts.",
            "Document what would change if real telemetry replaced synthetic data.",
        ],
    },
    {
        "title": "Transparency",
        "status": "Strong",
        "evidence": "Model flow, feature impact, calibration, and review logging are visible.",
        "gap": "Limitations and uncertainty could still be explained more simply.",
        "next_actions": [
            "Add uncertainty guidance directly beside live incident cards.",
            "Show known model limitations for each scenario in plain language.",
            "Provide a one-page summary export for non-technical stakeholders.",
        ],
    },
    {
        "title": "Diversity, Non-discrimination and Fairness",
        "status": "Gap",
        "evidence": "The app distinguishes device types and roles, but not fairness outcomes.",
        "gap": "Fairness metrics, bias checks, and subgroup error analysis are missing.",
        "next_actions": [
            "Evaluate error rates by device type, scenario, and operating profile.",
            "Add subgroup drift and disparate performance checks.",
            "Show fairness findings in Governance with mitigation notes.",
        ],
    },
    {
        "title": "Societal and Environmental Well-being",
        "status": "Gap",
        "evidence": "The app is positioned as decision support, not autonomous control.",
        "gap": "Societal impact, sustainability, and public-interest assessment are not shown.",
        "next_actions": [
            "Add a short impact assessment for critical infrastructure use cases.",
            "Document operational benefits, risks, and potential unintended harms.",
            "Include basic compute and sustainability considerations for model refresh cycles.",
        ],
    },
    {
        "title": "Accountability",
        "status": "Partial",
        "evidence": "Reviewer actions are logged and downloadable for audit.",
        "gap": "Ownership, sign-off, and escalation governance are not yet formalized.",
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
        dedent(
            f"""
        <div class="pillar-card">
            <div class="pillar-title">{pillar['title']}</div>
            <div class="pillar-status" style="{style}">{pillar['status']}</div>
            <div class="pillar-copy"><strong>Evidence in app:</strong> {pillar['evidence']}</div>
            <div class="pillar-copy"><strong>Current gap:</strong> {pillar['gap']}</div>
        </div>
        """,
        ),
        unsafe_allow_html=True,
    )
    with st.expander(f"Roadmap for {pillar['title']}", expanded=False):
        st.markdown("**Next actions**")
        st.markdown("\n".join([f"- {action}" for action in pillar.get("next_actions", [])]))


def _render_governance_scorecard(strong_count, partial_count, gap_count, reviews, status_counts):
    readiness_score = int(
        round(
            (sum(PILLAR_STATUS_SCORE[pillar["status"]] for pillar in TRUSTWORTHY_AI_PILLARS) / len(TRUSTWORTHY_AI_PILLARS))
            * 100
        )
    )
    active_reviews = status_counts["Approved"] + status_counts["Escalated"] + status_counts["False Positive"]
    policy = current_hitl_policy()
    oversight_strength = "Strong" if policy["suppression_enabled"] and active_reviews > 0 else "Developing"
    roadmap_pressure = "High" if gap_count >= 2 else ("Moderate" if gap_count == 1 else "Low")

    st.markdown(
        dedent(
            f"""
        <div class="governance-scorecard-grid">
            <div class="governance-scorecard governance-scorecard--primary">
                <div class="governance-scorecard-kicker">Readiness</div>
                <div class="governance-scorecard-value">{readiness_score}%</div>
                <div class="governance-scorecard-copy">Based on Strong / Partial / Gap status across the seven pillars.</div>
            </div>
            <div class="governance-scorecard">
                <div class="governance-scorecard-kicker">Oversight strength</div>
                <div class="governance-scorecard-value">{oversight_strength}</div>
                <div class="governance-scorecard-copy">{len(reviews)} review record(s) and live HITL controls are visible.</div>
            </div>
            <div class="governance-scorecard">
                <div class="governance-scorecard-kicker">Transparency coverage</div>
                <div class="governance-scorecard-value">{strong_count + partial_count}/7</div>
                <div class="governance-scorecard-copy">Pillars with at least visible controls or supporting evidence.</div>
            </div>
            <div class="governance-scorecard">
                <div class="governance-scorecard-kicker">Roadmap pressure</div>
                <div class="governance-scorecard-value">{roadmap_pressure}</div>
                <div class="governance-scorecard-copy">{gap_count} pillar gap(s) still need governance or measurement work.</div>
            </div>
        </div>
        """,
        ),
        unsafe_allow_html=True,
    )


def _render_pillar_group_header(status, count):
    meta = PILLAR_GROUP_META[status]
    st.markdown(
        dedent(
            f"""
        <div class="governance-group-header">
            <div>
                <div class="governance-group-kicker">Pillar group</div>
                <div class="governance-group-title">{meta['title']}</div>
                <div class="governance-group-copy">{meta['copy']}</div>
            </div>
            <div class="governance-group-badge-wrap">
                <span class="governance-group-badge {meta['badge_class']}">{status}</span>
                <span class="governance-group-count">{count} pillar{'s' if count != 1 else ''}</span>
            </div>
        </div>
        """,
        ),
        unsafe_allow_html=True,
    )


def _render_governance_snapshot(role, reviews, status_counts):
    strong_count = sum(pillar["status"] == "Strong" for pillar in TRUSTWORTHY_AI_PILLARS)
    partial_count = sum(pillar["status"] == "Partial" for pillar in TRUSTWORTHY_AI_PILLARS)
    gap_count = sum(pillar["status"] == "Gap" for pillar in TRUSTWORTHY_AI_PILLARS)

    render_section_card(
        "Governance readiness snapshot",
        "Start here for the trust story: what assurance evidence is visible now, where human review remains in control, and where the biggest gaps remain.",
        kicker="Snapshot",
    )

    snapshot_cols = st.columns(4)
    snapshot_cols[0].metric("Strong pillars", strong_count)
    snapshot_cols[1].metric("Partial pillars", partial_count)
    snapshot_cols[2].metric("Gap pillars", gap_count)
    snapshot_cols[3].metric("Reviewed incidents", len(reviews))

    _render_governance_scorecard(strong_count, partial_count, gap_count, reviews, status_counts)

    summary_cols = st.columns([1.15, 1.35])
    with summary_cols[0]:
        _render_role_governance_summary(role)
    with summary_cols[1]:
        render_summary_list(
            "What is visible right now",
            [
                "Human review remains in control of the incident workflow.",
                "Audit evidence is downloadable with role, time, and notes.",
                "Confidence checks and model logic are visible alongside governance evidence.",
            ],
            kicker="Assurance summary",
        )

    if gap_count > 0:
        render_focus_callout(
            "Main governance gap",
            "The demo is strongest on transparency and oversight. The weakest areas remain fairness, impact assessment, and formal accountability workflows.",
            variant="warning",
        )

    st.markdown(
        "<div class='quick-chip-row'>"
        f"<span class='quick-chip'>Pending review: {status_counts['Pending Review']}</span>"
        f"<span class='quick-chip'>Approved: {status_counts['Approved']}</span>"
        f"<span class='quick-chip'>False positives: {status_counts['False Positive']}</span>"
        f"<span class='quick-chip'>Escalated: {status_counts['Escalated']}</span>"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_pillars_overview():
    render_section_card(
        "EU Trustworthy AI — 7 Pillars",
        "Pillars are grouped by maturity so viewers can scan strengths first, then partial areas, then roadmap gaps.",
        kicker="Pillar view",
    )

    for status in ["Strong", "Partial", "Gap"]:
        pillars = [pillar for pillar in TRUSTWORTHY_AI_PILLARS if pillar["status"] == status]
        if not pillars:
            continue

        _render_pillar_group_header(status, len(pillars))
        render_focus_callout(PILLAR_GROUP_META[status]["title"], PILLAR_GROUP_META[status]["copy"], variant=PILLAR_STATUS_VARIANT[status])
        pillar_cols = st.columns(2)
        for idx, pillar in enumerate(pillars):
            with pillar_cols[idx % 2]:
                _render_pillar_card(pillar)


def _render_live_oversight_section(reviews, status_counts):
    policy = current_hitl_policy()
    hitl_live_stats = st.session_state.get("hitl_live_stats", {})
    latest_effect = hitl_live_stats.get("last_effect")

    render_section_card(
        "Live oversight status",
        "This section shows the active HITL policy, current review mix, and the latest human intervention affecting queue order.",
        kicker="Operations snapshot",
    )

    st.caption(
        f"Active HITL policy · suppression: {'enabled' if policy['suppression_enabled'] else 'disabled'} · "
        f"window: {policy['suppression_ticks']} ticks · escalation boost: {policy['escalation_boost']:.2f}"
    )

    top_cols = st.columns(4)
    top_cols[0].metric("Pending review", status_counts["Pending Review"])
    top_cols[1].metric("Approved", status_counts["Approved"])
    top_cols[2].metric("False positives", status_counts["False Positive"])
    top_cols[3].metric("Escalated", status_counts["Escalated"])

    live_cols = st.columns(3)
    live_cols[0].metric("Suppressed repeats", hitl_live_stats.get("suppressed_alerts", 0))
    live_cols[1].metric("Prioritized alerts", hitl_live_stats.get("prioritized_alerts", 0))
    live_cols[2].metric("Latest HITL effect", latest_effect.get("effect", "None") if latest_effect else "None")

    if latest_effect:
        render_focus_callout(
            "Latest intervention",
            f"{latest_effect['effect']} affected {latest_effect['device_id']} at tick {latest_effect['tick']}. Reason: {latest_effect.get('reason') or 'No reason recorded.'}",
            variant="info",
        )
    elif not reviews:
        render_focus_callout(
            "No review history yet",
            "Triage a few incidents to show how human decisions affect suppression, prioritization, and auditability.",
            variant="info",
        )


def _render_audit_section(reviews, nonce):
    render_section_card(
        "Audit trail",
        "Review evidence is visible here for inspection and export, making the human oversight story easy to verify.",
        kicker="Traceability",
    )

    if reviews:
        review_df, display_cols, export_json = _prepare_review_audit_artifacts(pd.DataFrame(reviews).to_json(orient="records"))
        st.caption("Recent human review log")
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

    with st.expander("Implementation and training detail", expanded=False):
        detail_cols = st.columns(2)
        with detail_cols[0]:
            with st.container(border=True):
                st.markdown("#### Training lifecycle")
                st.markdown(
                    "- **Data generation**: synthetic, physics-inspired telemetry.  \n"
                    "- **Windows & features**: rolling-window statistics.  \n"
                    "- **Binary detector**: LightGBM with conformal p-values.  \n"
                    "- **Type head**: LightGBM multiclass + rules.  \n"
                    "- **Thresholding**: suggested threshold = max F1 on validation split."
                )
        with detail_cols[1]:
            with st.container(border=True):
                st.markdown("#### Human-in-the-loop controls")
                st.markdown(
                    "- **Review states**: approve, false positive, or escalate.  \n"
                    "- **Audit trail**: reviewer role, timestamp, and note are persisted locally.  \n"
                    "- **Feedback set**: reviewed incidents can inform future tuning or retraining."
                )

        render_training_explainer(nonce)


def render_governance_tab(role):
    nonce = st.session_state.ui_nonce
    render_tab_intro("Governance", role)
    render_section_card(
        "EU AI Act — Transparency & Governance",
        "This page shows the trust controls, confidence checks, human review evidence, and governance gaps visible in the demo, with the key assurance evidence first.",
        kicker="Trust overview",
    )

    reviews = review_rows()
    status_counts = {status: 0 for status in ["Pending Review", "Approved", "False Positive", "Escalated"]}
    for incident in st.session_state.incidents:
        matched = next((row for row in reviews if row.get("incident_key") == incident_review_key(incident)), None)
        status = matched.get("status") if matched else "Pending Review"
        status_counts[status] = status_counts.get(status, 0) + 1

    _render_governance_snapshot(role, reviews, status_counts)
    _render_pillars_overview()
    _render_live_oversight_section(reviews, status_counts)
    _render_audit_section(reviews, nonce)


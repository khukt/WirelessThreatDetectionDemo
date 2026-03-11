import streamlit as st

from ..attack_education import render_attack_academy
from ..training import train_model_with_progress
from ..ux import (
    SCENARIO_COPY,
    icon_badge_html,
    render_model_status_card,
    render_quickstart,
    render_section_card,
)


ROLE_HOME_COPY = {
    "End User": {
        "headline": "Start with the simplest view of the story.",
        "body": "This demo shows how AI monitors wireless operations, flags suspicious behavior, and keeps people in charge of the final decision.",
    },
    "Domain Expert": {
        "headline": "Start with the scenario and analyst workflow.",
        "body": "This demo combines telemetry, anomaly detection, threat typing, and human review so you can judge whether the signals match operational reality.",
    },
    "Regulator": {
        "headline": "Start with an assurance-first view.",
        "body": "This demo shows not only AI outputs, but also the transparency, confidence controls, and human oversight around those outputs.",
    },
    "AI Builder": {
        "headline": "Start by choosing the behavior you want to test.",
        "body": "This demo covers the full loop from synthetic telemetry to anomaly scoring, threat typing, review actions, and governance evidence.",
    },
    "Executive": {
        "headline": "Start with the business story.",
        "body": "This demo explains how the system detects wireless threats, highlights operational risk, and shows where trust and accountability controls sit around the AI.",
    },
}


QUICK_PATHS = [
    ("overview", "Overview", "See the live posture of the fleet and current risk pattern.", "Live monitoring"),
    ("incidents", "Incidents", "Review alerts, evidence, and human decisions.", "Triage queue"),
    ("insights", "Insights", "Understand the model logic and confidence checks.", "Explain AI"),
    ("governance", "Governance", "Review oversight, auditability, and trustworthy AI concepts.", "Trust controls"),
]

SCENARIO_BUTTONS = [
    ("normal", "Normal", "Baseline"),
    ("jamming", "Jamming (localized)", "RF interference"),
    ("breach", "Access Breach (AP/gNB)", "Access attack"),
    ("spoofing", "GPS Spoofing (subset)", "Location attack"),
    ("tamper", "Data Tamper (gateway)", "Integrity issue"),
]

ROLE_BUTTONS = [
    ("end_user", "End User", "Simple guided view"),
    ("domain_expert", "Domain Expert", "Operational analyst"),
    ("regulator", "Regulator", "Assurance view"),
    ("ai_builder", "AI Builder", "Technical view"),
    ("executive", "Executive", "Leadership summary"),
]

PROJECT_SUMMARY_CARDS = [
    (
        "Project value",
        "Trustworthy wireless AI",
        "Shows how anomaly detection, threat typing, and human oversight can be combined into a credible wireless-AI story.",
    ),
    (
        "What visitors get",
        "Guided, role-aware journey",
        "Each audience sees the same system through a tailored explanation layer for demos, stakeholder briefings, and teaching.",
    ),
    (
        "Best starting point",
        "Pick a scenario, then a role",
        "Home explains the purpose first, then helps visitors move into Overview, Incidents, Insights, or Governance with the right context.",
    ),
]

MODEL_STACK = [
    (
        "insights",
        "Stage 1 · Anomaly detector",
        "A LightGBM binary classifier scores whether recent device behavior looks suspicious from rolling telemetry features.",
    ),
    (
        "governance",
        "Stage 2 · Threat typing",
        "A LightGBM multiclass model plus domain rules estimates whether the pattern looks like Jamming, Breach, Spoofing, or Tamper.",
    ),
    (
        "ready",
        "Confidence and oversight",
        "Thresholding, conformal calibration, and human review keep the demo focused on reviewable decision support.",
    ),
]

INCLUDED_CAPABILITIES = [
    ("Live monitoring", "Fleet posture, map context, risk rankings, and queue summaries."),
    ("Incident triage", "Review evidence, approve, dismiss, or escalate suspicious events."),
    ("Model transparency", "Feature importance, calibration, architecture views, and settings snapshots."),
    ("Governance views", "HITL status, audit trail, and trustworthy AI pillar framing."),
]


def _render_card(icon, title, copy, chip=None):
    chip_html = f"<div class='home-chip'>{chip}</div>" if chip else ""
    st.markdown(
        f"""
        <div class="home-card">
            <div class="home-card-icon">{icon_badge_html(icon, 'md')}</div>
            <div class="home-card-title">{title}</div>
            <div class="home-card-copy">{copy}</div>
            {chip_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_icon_tile(icon, title, copy, caption=None):
    caption_html = f"<div class='home-icon-caption'>{caption}</div>" if caption else ""
    st.markdown(
        f"""
        <div class="home-icon-tile">
            <div class="home-icon-badge">{icon_badge_html(icon, 'lg')}</div>
            <div class="home-icon-label">{title}</div>
            <div class="home-icon-copy">{copy}</div>
            {caption_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_project_banner(role, scenario, profile):
    scenario_copy = SCENARIO_COPY.get(scenario, SCENARIO_COPY["Normal"])
    model_ready = st.session_state.get("model") is not None
    model_source = st.session_state.get("model_artifact_source") or ("Setup required" if not model_ready else "Current session")
    st.markdown(
        f"""
        <div class="home-project-shell">
            <div class="home-project-kicker">Demo overview</div>
            <div class="home-project-title">TRUST AI — Wireless Threat Detection Demo Hub</div>
            <div class="home-project-copy">
                A presentation-ready overview of a trustworthy wireless threat detection workflow for smart-industry settings.
                Use this page to explain the demo, align the audience, and then move into monitoring, incidents, transparency, or governance.
            </div>
            <div class="home-project-chip-row">
                <span class="home-project-chip">Profile: {profile}</span>
                <span class="home-project-chip">Scenario: {scenario}</span>
                <span class="home-project-chip">Audience: {role}</span>
                <span class="home-project-chip">Model: {model_source}</span>
                <span class="home-project-chip">Watch for: {scenario_copy['signals']}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_project_summary_grid():
    columns = st.columns(len(PROJECT_SUMMARY_CARDS))
    for column, (kicker, title, copy) in zip(columns, PROJECT_SUMMARY_CARDS):
        with column:
            st.markdown(
                f"""
                <div class="home-mini-card">
                    <div class="home-mini-kicker">{kicker}</div>
                    <div class="home-mini-title">{title}</div>
                    <div class="home-mini-copy">{copy}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _open_home_destination(tab_name: str, message: str):
    st.session_state.active_primary_tab = tab_name
    st.session_state.home_message = message
    st.rerun()


def _render_presentation_overview(role, scenario, profile):
    role_copy = ROLE_HOME_COPY.get(role, ROLE_HOME_COPY["End User"])
    st.markdown(
        f"""
        <div class='home-presentation-card'>
            <div class='home-presentation-kicker'>Start here</div>
            <div class='home-presentation-title'>A lighter Home page for live demos</div>
            <div class='home-presentation-copy'>
                Use the guided onboarding for the full story, then use this page to pick the right audience framing
                and jump into monitoring, incidents, transparency, or governance.
            </div>
            <ul class='home-presentation-list'>
                <li>Use <strong>Restart guided onboarding</strong> whenever you want the slide-by-slide intro again.</li>
                <li>Use the controls below to tailor the scenario and audience for the people in front of you.</li>
                <li>Use the destination cards to move directly into the part of the demo you want to present next.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='home-hero'><div class='home-hero-title'>{role_copy['headline']}</div><div class='home-hero-copy'>{role_copy['body']}</div></div>",
        unsafe_allow_html=True,
    )


def _render_restart_onboarding_callout():
    callout_cols = st.columns([3.2, 1])
    with callout_cols[0]:
        st.caption("Need the guided intro again? Restart guided onboarding for the next audience using the current scenario and role as defaults.")
    with callout_cols[1]:
        if st.button(
            "Restart guided onboarding",
            key="home_restart_onboarding",
            use_container_width=True,
            type="secondary",
        ):
            st.session_state.onboarding_step = 1
            st.session_state.onboarding_scenario = st.session_state.get("scenario_selector", "Normal")
            st.session_state.onboarding_role = st.session_state.get("role_selector_preview", "AI Builder")
            st.session_state.welcome_prompt_dismissed = False
            st.rerun()


def _render_explore_destinations():
    render_section_card(
        "Where to explore next",
        "Use these four entry points when you want to move from the Home overview into the part of the demo that best matches your audience or presentation goal.",
        kicker="Explore",
    )
    path_cols = st.columns(len(QUICK_PATHS))
    for col, (icon, tab_name, copy, caption) in zip(path_cols, QUICK_PATHS):
        with col:
            _render_icon_tile(icon, tab_name, copy, caption=caption)
            if st.button(f"Open {tab_name}", key=f"home_open_{tab_name}", use_container_width=True):
                _open_home_destination(tab_name, f"Opened {tab_name}. Use the guidance in that tab to continue the walkthrough.")


def _render_customize_walkthrough(role, scenario):
    render_section_card(
        "Customize the walkthrough",
        "Adjust the scenario and audience framing here when you want the Home page to match the people in front of you before moving into the deeper tabs.",
        kicker="Customize",
    )
    scenario_options = [name for _, name, _ in SCENARIO_BUTTONS]
    role_options = [name for _, name, _ in ROLE_BUTTONS]
    control_cols = st.columns(2)
    selected_scenario = control_cols[0].selectbox(
        "Scenario",
        scenario_options,
        index=scenario_options.index(scenario) if scenario in scenario_options else 0,
        key="home_selected_scenario",
    )
    selected_role = control_cols[1].selectbox(
        "Audience view",
        role_options,
        index=role_options.index(role) if role in role_options else 0,
        key="home_selected_role",
    )
    action_cols = st.columns([1, 1.2, 1.2])
    if action_cols[0].button("Apply selections", key="home_apply_selection", use_container_width=True):
        st.session_state.pending_home_scenario = selected_scenario
        st.session_state.pending_home_role = selected_role
        st.session_state.home_message = f"Home walkthrough updated for {selected_role} under {selected_scenario}."
        st.rerun()
    if action_cols[1].button("Open live monitoring", key="home_open_overview", use_container_width=True):
        _open_home_destination("Overview", "Opened Overview. Start with the live posture and risk picture.")
    if action_cols[2].button("Open incident triage", key="home_open_incidents", use_container_width=True):
        _open_home_destination("Incidents", "Opened Incidents. Review the queue and evidence next.")


def _render_home_snapshot():
    metrics = st.session_state.get("metrics") or {}
    probs = list(st.session_state.get("latest_probs", {}).values())
    train_secs = st.session_state.get("last_train_secs")
    snapshot_cols = st.columns(4)
    snapshot_cols[0].metric("Devices", len(st.session_state.devices))
    snapshot_cols[1].metric("Incidents", len(st.session_state.incidents))
    snapshot_cols[2].metric("AUC", f"{metrics.get('auc', 0.0):.2f}")
    snapshot_cols[3].metric("Avg risk", f"{(sum(probs) / len(probs)):.2f}" if probs else "0.00")
    if train_secs:
        st.caption(f"Latest setup completed in {int(train_secs)}s.")


def render_home_tab(role, scenario, profile, help_mode, show_eu_status):
    _render_project_banner(role, scenario, profile)
    _render_presentation_overview(role, scenario, profile)
    _render_restart_onboarding_callout()
    _render_explore_destinations()
    _render_customize_walkthrough(role, scenario)

    scenario_copy = SCENARIO_COPY.get(scenario, SCENARIO_COPY["Normal"])

    with st.expander("Model and setup", expanded=st.session_state.get("model") is None):
        render_section_card(
            "Model status",
            "Check whether the detector is ready, whether artifacts were loaded from cache or fresh training, and whether the app is prepared for live monitoring.",
            kicker="System readiness",
        )
        render_model_status_card(compact=False)
        setup_cols = st.columns([1, 2])
        with setup_cols[0]:
            if st.button("Run model setup", key="home_train_model", use_container_width=True):
                train_model_with_progress(n_ticks=350)
                st.session_state.home_message = "Model setup completed. You can now use the live monitoring tabs."
                st.rerun()
        with setup_cols[1]:
            with st.container(border=True):
                st.markdown(
                    "- **Anomaly detector**: LightGBM binary classifier.  \n"
                    "- **Threat typing**: LightGBM multiclass model + rules.  \n"
                    "- **Confidence controls**: thresholding + conformal calibration."
                )

    with st.expander("Attack scenarios", expanded=False):
        render_section_card(
            "Learn the attacks",
            "This section explains each scenario in plain language first, then gives the technical cues that the rest of the demo will surface.",
            kicker="Education",
        )
        render_attack_academy(role, selected_scenario=scenario)

    with st.expander("Technical background", expanded=False):
        render_section_card(
            "About this demo",
            "Use this summary when you want a short explanation of what the demo does, how the model stack works, and what is included.",
            kicker="Storyline",
        )
        top_left, top_right = st.columns([1.15, 0.85])
        with top_left:
            with st.container(border=True):
                st.markdown(
                    "- Explains a trustworthy-AI workflow for wireless threat detection.  \n"
                    "- Uses synthetic telemetry so the full story can be shown safely.  \n"
                    "- Combines anomaly detection, threat typing, confidence controls, and human review.  \n"
                    "- Includes monitoring, incident handling, transparency views, and governance evidence.  \n"
                    "- Is designed for presentations and discussion rather than production deployment."
                )
        with top_right:
            scenario_icon = {
                "Normal": "normal",
                "Jamming (localized)": "jamming",
                "Access Breach (AP/gNB)": "breach",
                "GPS Spoofing (subset)": "spoofing",
                "Data Tamper (gateway)": "tamper",
            }.get(scenario, "scenario")
            _render_card(scenario_icon, scenario, scenario_copy["summary"], chip=f"Includes: monitoring, triage, transparency, governance")
        render_section_card(
            "Current demo snapshot",
            "This quick snapshot is useful once you already understand the demo and want a compact readout of the current session state.",
            kicker="Snapshot",
        )
        with st.container(border=True):
            _render_home_snapshot()
        with st.container(border=True):
            render_quickstart(help_mode, show_eu_status, scenario)

    with st.expander("Optional guided onboarding", expanded=False):
        render_section_card(
            "Start here",
            "This three-step path gives any audience a quick way to begin the demo without needing to understand the full interface first.",
            kicker="Quick onboarding",
        )
        st.markdown("<div class='home-section-note'>Pick a scenario, choose an audience view, then move to the tab that matches your goal.</div>", unsafe_allow_html=True)
        explainer_cols = st.columns(3)
        with explainer_cols[0]:
            _render_card("step_1", "Pick a scenario", "Choose the threat story you want to demonstrate.")
        with explainer_cols[1]:
            _render_card("step_2", "Pick a view", "Switch the explanation style for the audience in front of you.")
        with explainer_cols[2]:
            _render_card("step_3", "Open a tab", "Go to Overview, Incidents, Insights, or Governance next.")

    if st.session_state.get("home_message"):
        st.success(st.session_state.home_message)
        st.caption("Tabs cannot auto-switch in Streamlit, so use the tab bar above to continue.")

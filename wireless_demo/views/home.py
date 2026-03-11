import streamlit as st

from ..attack_education import render_attack_academy, render_current_attack_brief
from ..training import train_model_with_progress
from ..ux import (
    SCENARIO_COPY,
    icon_badge_html,
    render_model_status_card,
    render_section_card,
)

QUICK_PATHS = [
    ("overview", "Overview", "Start with the live posture of the fleet and current risk pattern.", "Recommended first stop", True),
    ("incidents", "Incidents", "Review alerts, evidence, and human decisions.", "Triage queue", False),
    ("insights", "Insights", "Explain the AI behavior, confidence checks, and trust story.", "Explain + trust", False),
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

def _render_icon_tile(icon, title, copy, caption=None, recommended=False):
    caption_html = f"<div class='home-icon-caption'>{caption}</div>" if caption else ""
    recommended_class = " home-icon-tile--recommended" if recommended else ""
    st.markdown(
        f"""
        <div class="home-icon-tile{recommended_class}">
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
            <div class="home-project-kicker">Home hub</div>
            <div class="home-project-title">TRUST AI — Scenario landing page</div>
            <div class="home-project-copy">
                Use this page to understand the current threat scenario, align the audience, and then jump into the right part of the demo.
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


def _open_home_destination(tab_name: str, message: str):
    st.session_state.active_primary_tab = tab_name
    st.session_state.home_message = message
    st.rerun()


def _render_attack_academy_home(role, scenario):
    render_section_card(
        "Understand the current scenario",
        "Use this section to explain what the selected attack means, why it matters, and what viewers should expect to see in the rest of the demo.",
        kicker="Attack Academy",
    )
    render_current_attack_brief(scenario, role, title="Current scenario explainer")
    with st.expander("Compare all attack scenarios", expanded=False):
        render_attack_academy(role, selected_scenario=scenario)


def _render_restart_onboarding_callout():
    callout_cols = st.columns([3.2, 1])
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
        "Once the audience understands the current scenario, choose one of these three routes to begin the walkthrough.",
        kicker="Explore",
    )
    path_cols = st.columns(len(QUICK_PATHS))
    for col, (icon, tab_name, copy, caption, recommended) in zip(path_cols, QUICK_PATHS):
        with col:
            _render_icon_tile(icon, tab_name, copy, caption=caption, recommended=recommended)
            button_label = f"Start with {tab_name}" if recommended else f"Open {tab_name}"
            button_type = "primary" if recommended else "secondary"
            if st.button(button_label, key=f"home_open_{tab_name}", use_container_width=True, type=button_type):
                _open_home_destination(tab_name, f"Opened {tab_name}. Use the guidance in that tab to continue the walkthrough.")


def _render_customize_walkthrough(role, scenario):
    render_section_card(
        "Set scenario and audience",
        "Adjust the scenario and audience framing here before you move into the deeper tabs.",
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
    if action_cols[2].button("Open incidents", key="home_open_incidents", use_container_width=True):
        _open_home_destination("Incidents", "Opened Incidents. Review the queue and evidence next.")


def _render_setup_status():
    render_section_card(
        "Model setup status",
        "Keep setup visible here so you can quickly explain whether the demo is ready or refresh the models when needed.",
        kicker="System readiness",
    )
    render_model_status_card(compact=False)
    setup_cols = st.columns([1, 1, 2])
    if setup_cols[0].button("Run model setup", key="home_train_model", use_container_width=True):
        train_model_with_progress(n_ticks=350)
        st.session_state.home_message = "Model setup completed. You can now use the live monitoring tabs."
        st.rerun()
    if setup_cols[1].button("Open Insights", key="home_open_insights", use_container_width=True, type="secondary"):
        _open_home_destination("Insights", "Opened Insights. Use this view to explain model behavior and trust controls.")
    with setup_cols[2]:
        with st.container(border=True):
            st.markdown(
                "- **Anomaly detector**: LightGBM binary classifier.  \n"
                "- **Threat typing**: LightGBM multiclass model + rules.  \n"
                "- **Confidence controls**: thresholding + conformal calibration."
            )


def render_home_tab(role, scenario, profile, help_mode, show_eu_status):
    _render_project_banner(role, scenario, profile)
    _render_restart_onboarding_callout()
    _render_attack_academy_home(role, scenario)

    lower_cols = st.columns([1.05, 1.25])
    with lower_cols[0]:
        _render_customize_walkthrough(role, scenario)
    with lower_cols[1]:
        _render_explore_destinations()

    with st.expander("Model setup and readiness", expanded=st.session_state.get("model") is None):
        _render_setup_status()

    if st.session_state.get("home_message"):
        st.success(st.session_state.home_message)

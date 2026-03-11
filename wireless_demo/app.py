import warnings
from typing import Optional

import streamlit as st

from .config import CFG, DEVICE_TYPES, MODEL_KEY
from .logic import tick_once
from .persistence import load_model_artifacts
from .state import init_state, model_store, reset_live_simulation
from .training import train_model_with_progress
from .ux import (
    ROLE_TAB_ORDER,
    TAB_DISPLAY_LABELS,
    inject_global_styles,
    render_app_footer,
    render_disclaimer_banner,
    render_onboarding_destination_card,
    render_onboarding_panel,
    render_sidebar_hint,
    render_sidebar_intro_card,
    render_status_strip,
    render_sidebar_summary_card,
    sidebar_role_copy,
)
from .views.fleet import render_fleet_tab
from .views.governance import render_governance_tab
from .views.home import render_home_tab
from .views.incidents import render_incidents_tab
from .views.insights import render_insights_tab
from .views.overview import render_overview_tab


ONBOARDING_SCENARIOS = [
    "Normal",
    "Jamming (localized)",
    "Access Breach (AP/gNB)",
    "GPS Spoofing (subset)",
    "Data Tamper (gateway)",
]

ONBOARDING_ROLES = ["End User", "Domain Expert", "Regulator", "AI Builder", "Executive"]
ONBOARDING_TOTAL_STEPS = 6
ONBOARDING_STEP_TITLES = {
    1: "Intro",
    2: "Context",
    3: "Models",
    4: "Included",
    5: "Workflow",
    6: "Next",
}


def _apply_pending_home_actions():
    pending_scenario = st.session_state.pop("pending_home_scenario", None)
    if pending_scenario is not None:
        st.session_state.scenario_selector = pending_scenario

    pending_role = st.session_state.pop("pending_home_role", None)
    if pending_role is not None:
        st.session_state.role_selector_preview = pending_role


def _apply_onboarding_choices():
    selected_scenario = st.session_state.get("onboarding_scenario")
    selected_role = st.session_state.get("onboarding_role")
    if selected_scenario:
        st.session_state.scenario_selector = selected_scenario
    if selected_role:
        st.session_state.role_selector_preview = selected_role


def _close_onboarding(open_tab: Optional[str] = None, open_setup: bool = False):
    _apply_onboarding_choices()
    st.session_state.welcome_prompt_dismissed = True
    st.session_state.onboarding_step = 1
    if open_tab is not None:
        st.session_state.active_primary_tab = open_tab
    if open_setup:
        st.session_state.open_training_dialog = True


def _restart_onboarding():
    st.session_state.onboarding_step = 1
    st.session_state.onboarding_scenario = st.session_state.get("scenario_selector", "Normal")
    st.session_state.onboarding_role = st.session_state.get("role_selector_preview", "AI Builder")
    st.session_state.welcome_prompt_dismissed = False


def _render_onboarding_progress(step: int):
    step_title = ONBOARDING_STEP_TITLES.get(step, "Onboarding")
    st.markdown(
        (
            "<div class='onboarding-progress-note'>"
            f"<span><strong>Slide {step} of {ONBOARDING_TOTAL_STEPS}</strong> · {step_title}</span>"
            "<span>Use the blue button to continue</span>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )
    st.progress(step / ONBOARDING_TOTAL_STEPS)


def _render_onboarding_action_hint(message: str):
    st.markdown(f"<div class='onboarding-actions-note'>{message}</div>", unsafe_allow_html=True)


@st.dialog("Welcome to the demo")
def _render_first_open_welcome_dialog():
    step = st.session_state.get("onboarding_step", 1)
    st.session_state.setdefault("onboarding_scenario", st.session_state.get("scenario_selector", "Normal"))
    st.session_state.setdefault("onboarding_role", st.session_state.get("role_selector_preview", "AI Builder"))
    _render_onboarding_progress(step)

    if step == 1:
        render_onboarding_panel(
            title="What this demo is",
            body="This demo shows how AI flags suspicious wireless behavior, suggests a likely threat type, and keeps a human reviewer in control of the final decision.",
            bullets=[
                "Designed for presentations, research demos, teaching, and stakeholder briefings.",
                "Combines live monitoring, incident triage, transparency, and governance in one flow.",
                "A simple path is: Home overview first, then the live tabs when you are ready.",
            ],
            kicker="Welcome",
            variant="info",
        )
        _render_onboarding_action_hint("First time here? Click the blue button: Continue guided onboarding. Skip only if you already know the demo.")
        cols = st.columns([1, 1.7])
        if cols[0].button("Skip intro", key="onboarding_skip_step1", use_container_width=True, type="secondary"):
            _close_onboarding(open_tab="Home")
            st.rerun()
        if cols[1].button("Continue guided onboarding", key="onboarding_next_step1", use_container_width=True, type="primary"):
            st.session_state.onboarding_step = 2
            st.rerun()
        return

    if step == 2:
        render_onboarding_panel(
            title="Choose your context",
            body="Choose the scenario and audience view before you start. This changes how the demo story is framed without changing the underlying system behavior.",
            bullets=[
                "Scenario changes the threat story being demonstrated.",
                "Audience view changes the explanation style, not the underlying system behavior.",
            ],
            kicker="Step 2",
            variant="info",
        )
        select_cols = st.columns(2)
        select_cols[0].selectbox("Scenario", ONBOARDING_SCENARIOS, key="onboarding_scenario")
        select_cols[1].selectbox("Audience view", ONBOARDING_ROLES, key="onboarding_role")
        _render_onboarding_action_hint("Recommended defaults are already selected. Change them only if you want to tell a different story.")
        cols = st.columns([1, 1.2, 1.7])
        if cols[0].button("Back", key="onboarding_back_step2", use_container_width=True, type="secondary"):
            st.session_state.onboarding_step = 1
            st.rerun()
        if cols[1].button("Use recommended defaults", key="onboarding_defaults_step2", use_container_width=True, type="secondary"):
            st.session_state.onboarding_scenario = "Normal"
            st.session_state.onboarding_role = "AI Builder"
            st.rerun()
        if cols[2].button("Next: see the model story", key="onboarding_next_step2", use_container_width=True, type="primary"):
            st.session_state.onboarding_step = 3
            st.rerun()
        return

    if step == 3:
        render_onboarding_panel(
            title="What models are used",
            body="The demo uses a staged AI workflow rather than a single black-box score.",
            bullets=[
                "Stage 1: a LightGBM anomaly detector scores suspicious behavior from rolling telemetry features.",
                "Stage 2: threat typing combines multiclass prediction with domain rules for Jamming, Breach, Spoofing, and Tamper.",
                "Confidence controls and human review keep the final outcome explainable and accountable.",
            ],
            kicker="Step 3",
            variant="info",
        )
        _render_onboarding_action_hint("Continue to see which parts of the demo are included in the walkthrough.")
        cols = st.columns([1, 1])
        if cols[0].button("Back", key="onboarding_back_step3", use_container_width=True, type="secondary"):
            st.session_state.onboarding_step = 2
            st.rerun()
        if cols[1].button("Next: what is included", key="onboarding_next_step3", use_container_width=True, type="primary"):
            st.session_state.onboarding_step = 4
            st.rerun()
        return

    if step == 4:
        render_onboarding_panel(
            title="What is included",
            body="The app is designed to tell both the operational story and the trust story from one place.",
            bullets=[
                "Live monitoring for posture, risk, map context, and fleet behavior.",
                "Incident triage for evidence review, approval, dismissal, or escalation.",
                "Transparency and governance views for calibration, feature importance, auditability, and oversight framing.",
            ],
            kicker="Step 4",
            variant="info",
        )
        _render_onboarding_action_hint("Continue to see the simple operator workflow used throughout the demo.")
        cols = st.columns([1, 1])
        if cols[0].button("Back", key="onboarding_back_step4", use_container_width=True, type="secondary"):
            st.session_state.onboarding_step = 3
            st.rerun()
        if cols[1].button("Next: see the workflow", key="onboarding_next_step4", use_container_width=True, type="primary"):
            st.session_state.onboarding_step = 5
            st.rerun()
        return

    if step == 5:
        render_onboarding_panel(
            title="How the demo works",
            body="The walkthrough is intentionally simple for first-time users.",
            bullets=[
                "Detect anomaly from recent telemetry.",
                "Explain the likely threat family with model output plus rules.",
                "Send the alert to human review with traceable oversight.",
            ],
            kicker="Step 5",
            variant="info",
        )
        _render_onboarding_action_hint("One more step: choose where to begin the live demo.")
        cols = st.columns([1, 1])
        if cols[0].button("Back", key="onboarding_back_step5", use_container_width=True, type="secondary"):
            st.session_state.onboarding_step = 4
            st.rerun()
        if cols[1].button("Next: choose a starting view", key="onboarding_next_step5", use_container_width=True, type="primary"):
            st.session_state.onboarding_step = 6
            st.rerun()
        return

    render_onboarding_panel(
        title="Where to go next",
        body="Pick the best starting point for your session.",
        bullets=[
            "Home gives the lightweight presentation overview and lets you adjust the audience and scenario.",
            "Overview shows live monitoring and fleet risk.",
            "Incidents, Insights, and Governance provide deeper operational and assurance views.",
        ],
        kicker="Step 6",
        variant="info",
    )
    _render_onboarding_action_hint("Recommended first stop: Home overview. Use the alternatives only if you already know where you want to jump.")
    destination_cols = st.columns(3)
    with destination_cols[0]:
        render_onboarding_destination_card(
            icon="home",
            title="Home overview",
            body="Best first stop for most users. It gives the presentation view and lets you tailor the scenario and audience.",
            note="Recommended for first-time visitors.",
            kicker="Recommended",
            recommended=True,
        )
        if st.button("Open Home overview", key="onboarding_open_home", use_container_width=True, type="primary"):
            _close_onboarding(open_tab="Home")
            st.rerun()
    with destination_cols[1]:
        render_onboarding_destination_card(
            icon="overview",
            title="Live monitoring",
            body="Jump straight into the operational picture with current fleet posture, map context, and risk patterns.",
            note="Use this if you want to start with the live story.",
            kicker="Operations",
        )
        if st.button(
            "Jump to live monitoring",
            key="onboarding_open_overview",
            use_container_width=True,
            type="secondary",
        ):
            _close_onboarding(open_tab="Overview")
            st.rerun()
    with destination_cols[2]:
        render_onboarding_destination_card(
            icon="setup",
            title="Model setup guide",
            body="Open the setup walkthrough if you want to refresh or explain the detector and threat-typing models first.",
            note="Use this when setup or refresh is part of the presentation.",
            kicker="Preparation",
        )
        if st.button(
            "Open model setup guide",
            key="onboarding_open_setup",
            use_container_width=True,
            type="secondary",
        ):
            _close_onboarding(open_tab="Home", open_setup=True)
            st.rerun()
    if st.button("Back", key="onboarding_back_step6", use_container_width=True, type="secondary"):
        st.session_state.onboarding_step = 5
        st.rerun()


def _render_first_open_welcome():
    _render_first_open_welcome_dialog()


@st.dialog("Model setup guide")
def _render_initial_training_prompt_dialog():
    render_onboarding_panel(
        title="Open model setup guide",
        body="This demo needs its anomaly detector and attack-type classifier before it can generate alerts, explanations, and transparency views.",
        bullets=[
            "Binary detector learns normal vs anomalous device behavior.",
            "Attack typing learns Jamming, Breach, Spoofing, and Tamper classification.",
            "Transparency views unlock global importance, calibration, and governance context after training.",
        ],
        kicker="Setup required",
        variant="warning",
    )
    action_cols = st.columns(2)
    if action_cols[0].button("Start model setup", key="initial_train_now", use_container_width=True):
        st.session_state.open_training_dialog = False
        train_model_with_progress(n_ticks=350)
        st.rerun()
    if action_cols[1].button("Skip for now", key="initial_train_later", use_container_width=True):
        st.session_state.open_training_dialog = False
        st.rerun()


def _render_initial_training_prompt():
    _render_initial_training_prompt_dialog()


def _render_primary_navigation(tab_order):
    current_tab = st.session_state.get("active_primary_tab")
    if current_tab not in tab_order:
        current_tab = tab_order[0]
        st.session_state.active_primary_tab = current_tab

    selected_tab = st.radio(
        "Primary navigation",
        options=tab_order,
        index=tab_order.index(current_tab),
        format_func=lambda tab_name: TAB_DISPLAY_LABELS.get(tab_name, tab_name),
        horizontal=True,
        label_visibility="collapsed",
        key="active_primary_tab",
    )
    return selected_tab


def _reset_simulation_if_context_changed(scenario, cellular_mode):
    prev_scenario = st.session_state.get("_active_scenario")
    prev_cellular_mode = st.session_state.get("_active_cellular_mode")

    if prev_scenario is None or prev_cellular_mode is None:
        st.session_state._active_scenario = scenario
        st.session_state._active_cellular_mode = cellular_mode
        return

    if prev_scenario != scenario or prev_cellular_mode != cellular_mode:
        reset_live_simulation()
        st.session_state._active_scenario = scenario
        st.session_state._active_cellular_mode = cellular_mode
        st.session_state.context_change_message = f"Simulation reset for {scenario} in {'Road' if cellular_mode else 'Yard'} mode."


def _render_live_workflow(refresh_ms, auto, speed, scenario, use_conformal, role, help_mode, show_eu_status, show_map, type_filter, show_heatmap, profile):
    refresh_interval = refresh_ms / 1000 if auto and st.session_state.get("model") is not None else None
    tab_order = ROLE_TAB_ORDER.get(role, ROLE_TAB_ORDER["End User"])
    tab_renderers = {
        "Home": lambda: render_home_tab(role, scenario, profile, help_mode, show_eu_status),
        "Overview": lambda: render_overview_tab(scenario, show_map, type_filter, use_conformal, role),
        "Fleet View": lambda: render_fleet_tab(show_heatmap, role),
        "Incidents": lambda: render_incidents_tab(role),
        "Insights": lambda: render_insights_tab(role),
        "Governance": lambda: render_governance_tab(role),
    }
    live_tabs = {"Overview", "Fleet View", "Incidents"}

    if st.session_state.get("model") is None:
        st.warning("Model setup has not been run yet. Start with the Home tab or use **Run model setup / refresh** in the sidebar.")
    else:
        st.caption("Use the Home tab for onboarding, or jump directly into the live workflow tabs below.")

    selected_tab = _render_primary_navigation(tab_order)

    if st.session_state.get("model") is not None and not auto:
        if st.button("Step once"):
            tick_once(scenario, use_conformal)
            st.rerun()

    if st.session_state.get("model") is None or not auto:
        tab_renderers[selected_tab]()
        return

    if selected_tab not in live_tabs:
        tab_renderers[selected_tab]()

        @st.fragment(run_every=refresh_interval)
        def run_background_tick_fragment():
            for _ in range(speed):
                tick_once(scenario, use_conformal)

        run_background_tick_fragment()
        return

    @st.fragment(run_every=refresh_interval)
    def render_live_workflow_fragment():
        for _ in range(speed):
            tick_once(scenario, use_conformal)
        tab_renderers[selected_tab]()

    render_live_workflow_fragment()


def main():
    warnings.filterwarnings(
        "ignore",
        message="LightGBM binary classifier .* TreeExplainer shap values output has changed to a list of ndarray",
        category=UserWarning,
    )

    _apply_pending_home_actions()

    st.set_page_config(page_title="TRUST AI — Wireless Threats (Sundsvall)", layout="wide")
    inject_global_styles()
    render_disclaimer_banner()

    with st.sidebar:
        sidebar_copy = sidebar_role_copy(st.session_state.get("role_selector_preview", "AI Builder"))
        profile = st.session_state.get("cellular_mode")
        current_profile_label = "Road" if profile else "Yard"
        render_sidebar_intro_card("Demo controls", "Configure the scenario, playback, model behavior, and audience view from one place.")
        render_sidebar_summary_card(current_profile_label, st.session_state.get("scenario_selector", "Normal"), st.session_state.get("role_selector_preview", "AI Builder"))
        render_sidebar_hint("Current guidance", sidebar_copy["controls"], variant="info")
        with st.expander("Scenario setup", expanded=True):
            profile = st.selectbox(
                "Comms profile",
                ["Yard (Wi-Fi/private-5G dominant)", "Road (Cellular 5G/LTE dominant)"],
                index=1,
            )
            st.session_state["cellular_mode"] = profile.startswith("Road")

            scenario = st.selectbox(
                "Scenario",
                ["Normal", "Jamming (localized)", "Access Breach (AP/gNB)", "GPS Spoofing (subset)", "Data Tamper (gateway)"],
                index=0,
                key="scenario_selector",
            )
            render_sidebar_hint("Scenario focus", sidebar_copy["scenario"])

            if scenario.startswith("Jamming"):
                st.radio("Jamming type", ["Broadband noise", "Reactive", "Burst interference"], index=0, key="jam_mode")
                CFG.jam_radius_m = st.slider("Jam coverage (m)", 50, 500, CFG.jam_radius_m, 10, key="jam_radius")

            if scenario.startswith("Access Breach"):
                st.radio("Breach mode", ["Evil Twin", "Rogue Open AP", "Credential hammer", "Deauth flood"], index=0, key="breach_mode")
                CFG.breach_radius_m = st.slider("Rogue node lure radius (m)", 50, 300, CFG.breach_radius_m, 10, key="breach_radius")

            if scenario.startswith("GPS Spoofing"):
                st.radio("Spoofing scope", ["Single device", "Localized area", "Site-wide"], index=1, key="spoof_mode")
                st.checkbox("Affect mobile (AMR/Truck) only", True, key="spoof_mobile_only")
                CFG.spoof_radius_m = st.slider("Spoof coverage (m)", 50, 500, CFG.spoof_radius_m, 10, key="spoof_radius")

            if scenario.startswith("Data Tamper"):
                st.radio(
                    "Tamper mode",
                    ["Replay", "Constant injection", "Bias/Drift", "Bitflip/Noise", "Scale/Unit mismatch"],
                    index=0,
                    key="tamper_mode",
                )

        with st.expander("Playback", expanded=False):
            speed = st.slider("Playback speed (ticks/refresh)", 1, 10, 3)
            auto = st.checkbox("Auto stream", True)
            refresh_ms = st.slider("Auto refresh cadence (ms)", 300, 3000, 1200, 100, disabled=not auto)
            reset = st.button("Reset session", use_container_width=True)
            render_sidebar_hint("Playback tip", "Use slower cadence for presentations and faster cadence when you want incidents to populate quickly.")

        with st.expander("Model behavior", expanded=False):
            use_conformal = st.checkbox("Conformal risk (calibrated p-value)", True)
            threshold_value = st.slider("Incident threshold (model prob.)", 0.30, 0.95, CFG.threshold, 0.01, key="th_slider")
            CFG.threshold = threshold_value
            if st.session_state.get("suggested_threshold") is not None:
                if st.button(f"Apply suggested threshold ({st.session_state.suggested_threshold:.2f})", use_container_width=True):
                    st.session_state.th_slider = float(st.session_state.suggested_threshold)
            render_sidebar_hint("Model behavior", "Alerts fire when probability ≥ threshold; p-value refines severity if enabled.")
            render_sidebar_hint("Role guidance", sidebar_copy["model"])
            retrain = st.button("Run model setup / refresh", use_container_width=True)

        with st.expander("HITL policy", expanded=False):
            st.checkbox(
                "Suppress repeat false positives",
                value=st.session_state.get("hitl_suppression_enabled", CFG.hitl_suppression_enabled),
                key="hitl_suppression_enabled",
            )
            st.slider(
                "False-positive suppression window (ticks)",
                0,
                100,
                int(st.session_state.get("hitl_suppression_ticks", CFG.hitl_suppression_ticks)),
                1,
                key="hitl_suppression_ticks",
            )
            st.slider(
                "Escalation queue boost",
                0.0,
                1.0,
                float(st.session_state.get("hitl_escalation_boost", CFG.hitl_escalation_boost)),
                0.05,
                key="hitl_escalation_boost",
            )
            render_sidebar_hint("Policy effect", "These controls change how prior human reviews influence duplicate suppression and triage ordering.")

        with st.expander("Display and audience", expanded=False):
            show_map = st.checkbox("Show geospatial map", True)
            show_heatmap = st.checkbox("Show fleet heatmap (metric z-scores)", True)
            type_filter = st.multiselect("Show device types", DEVICE_TYPES, default=DEVICE_TYPES)
            role = st.selectbox(
                "Viewer role",
                ["End User", "Domain Expert", "Regulator", "AI Builder", "Executive"],
                index=3,
                key="role_selector_preview",
            )
            sidebar_copy = sidebar_role_copy(role)
            render_sidebar_hint("Display guidance", sidebar_copy["display"])

        with st.expander("Guidance", expanded=False):
            help_mode = st.checkbox("Help mode (inline hints)", True)
            show_eu_status = st.checkbox("Show EU AI Act status banner", True)
            render_sidebar_hint("When to use this", sidebar_copy["guidance"])
            if st.button("Restart guided onboarding", use_container_width=True, type="secondary"):
                _restart_onboarding()
                st.rerun()
            if st.button("Open model setup guide", use_container_width=True):
                st.session_state.open_training_dialog = True
                st.rerun()

    if "devices" not in st.session_state or reset:
        init_state()

    _reset_simulation_if_context_changed(scenario, st.session_state.get("cellular_mode", False))

    if st.session_state.get("context_change_message"):
        st.info(st.session_state.pop("context_change_message"))

    if not st.session_state.get("welcome_prompt_dismissed", False):
        _render_first_open_welcome()

    store = model_store()
    if (not CFG.retrain_on_start) and (st.session_state.get("model") is None) and (MODEL_KEY not in store):
        disk_artifacts = load_model_artifacts(MODEL_KEY)
        if disk_artifacts is not None:
            disk_artifacts["artifact_source"] = disk_artifacts.get("artifact_source", "Disk cache")
            store[MODEL_KEY] = disk_artifacts

    if (not CFG.retrain_on_start) and (st.session_state.get("model") is None) and (MODEL_KEY in store):
        artifacts = store[MODEL_KEY]
        st.session_state.model = artifacts["model"]
        st.session_state.scaler = artifacts["scaler"]
        st.session_state.explainer = artifacts["explainer"]
        st.session_state.conformal_scores = artifacts["conformal_scores"]
        st.session_state.metrics = artifacts["metrics"]
        st.session_state.baseline = artifacts["baseline"]
        st.session_state.global_importance = artifacts.get("global_importance")
        st.session_state.eval = artifacts["eval"]
        st.session_state.suggested_threshold = artifacts.get("suggested_threshold")
        st.session_state.type_clf = artifacts.get("type_clf")
        st.session_state.type_cols = artifacts.get("type_cols", [])
        st.session_state.type_labels = artifacts.get("type_labels", [])
        st.session_state.type_explainer = artifacts.get("type_explainer")
        st.session_state.type_metrics = artifacts.get("type_metrics", {})
        st.session_state.training_info = artifacts.get("training_info", {})
        st.session_state.artifact_trained_at = artifacts.get("trained_at")
        st.session_state.model_artifact_source = artifacts.get("artifact_source", "Memory cache")
        artifact_source = st.session_state.model_artifact_source
        trained_at = artifacts.get("trained_at")
        trained_note = f" (saved at {trained_at})" if trained_at else ""
        title = "Bundled startup cache loaded" if artifact_source == "Bundled startup cache" else "Cached model loaded"
        if not st.session_state.get("startup_cache_notice_dismissed", False):
            notice_cols = st.columns([8, 1.2])
            with notice_cols[0]:
                render_status_strip(
                    title=title,
                    body=f"Loaded cached model{trained_note}. No setup refresh is needed unless you want to rebuild the models from scratch.",
                    icon="cache" if artifact_source == "Bundled startup cache" else "ready",
                )
            with notice_cols[1]:
                st.write("")
                if st.button("Hide", key="dismiss_startup_cache_notice", use_container_width=True):
                    st.session_state.startup_cache_notice_dismissed = True
                    st.rerun()
        else:
            st.caption(
                f"{title} · Loaded cached model{trained_note}. Use model setup only if you want to rebuild from scratch."
            )

    if retrain or (CFG.retrain_on_start and st.session_state.get("model") is None and MODEL_KEY not in store):
        st.session_state.open_training_dialog = False
        train_model_with_progress(n_ticks=350)

    if st.session_state.get("open_training_dialog", False):
        _render_initial_training_prompt()

    _render_live_workflow(
        refresh_ms=refresh_ms,
        auto=auto,
        speed=speed,
        scenario=scenario,
        use_conformal=use_conformal,
        role=role,
        help_mode=help_mode,
        show_eu_status=show_eu_status,
        show_map=show_map,
        type_filter=type_filter,
        show_heatmap=show_heatmap,
        profile=profile,
    )
    render_app_footer()

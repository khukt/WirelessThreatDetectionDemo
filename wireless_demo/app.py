import warnings
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from .config import CFG, DEVICE_TYPES, MODEL_KEY
from .logic import tick_once
from .persistence import load_model_artifacts
from .state import init_state, model_store, reset_live_simulation
from .training import train_model_with_progress
from .ux import (
    ROLE_TAB_ORDER,
    TAB_DISPLAY_LABELS,
    inject_global_styles,
    render_sidebar_summary_card,
    sidebar_role_copy,
)
from .views.fleet import render_fleet_tab
from .views.governance import render_governance_tab
from .views.home import render_home_tab
from .views.incidents import render_incidents_tab
from .views.insights import render_insights_tab
from .views.overview import render_overview_tab


def _apply_pending_home_actions():
    pending_scenario = st.session_state.pop("pending_home_scenario", None)
    if pending_scenario is not None:
        st.session_state.scenario_selector = pending_scenario

    pending_role = st.session_state.pop("pending_home_role", None)
    if pending_role is not None:
        st.session_state.role_selector_preview = pending_role


def _render_first_open_welcome():
    def render_prompt_body():
        st.markdown(
            "### Welcome to the demo\n"
            "Start with the **⌂ Home** tab to pick a scenario, choose an audience view, and understand the story of the demo before exploring the detailed tabs."
        )
        st.markdown(
            "- **Home:** quick icon-style choices for scenario, role, and next step.  \n"
            "- **Overview:** live wireless posture and fleet risk.  \n"
            "- **Incidents:** alert triage with human review actions.  \n"
            "- **Insights / Governance:** model explanation and trust controls."
        )
        cols = st.columns(2)
        if cols[0].button("Got it", key="welcome_dismiss", use_container_width=True):
            st.session_state.welcome_prompt_dismissed = True
            st.rerun()
        if cols[1].button("Open model setup guide", key="welcome_open_setup", use_container_width=True):
            st.session_state.welcome_prompt_dismissed = True
            st.session_state.training_prompt_dismissed = False
            st.rerun()

    with st.container(border=True):
        st.info("New here? Start with the Home tab for the guided demo path.")
        render_prompt_body()


def _render_initial_training_prompt():
    def render_prompt_body():
        st.markdown(
            "### Open model setup guide\n"
            "This demo needs its anomaly detector and attack-type classifier before it can generate alerts, explanations, and transparency views."
        )
        st.markdown(
            "- **Binary detector:** learns normal vs anomalous device behavior.  \n"
            "- **Attack typing:** learns Jamming, Breach, Spoofing, and Tamper classification.  \n"
            "- **Transparency views:** global importance, calibration, and governance become available after training."
        )
        action_cols = st.columns(2)
        if action_cols[0].button("Start model setup", key="initial_train_now", use_container_width=True):
            st.session_state.training_prompt_dismissed = True
            train_model_with_progress(n_ticks=350)
            st.rerun()
        if action_cols[1].button("Skip for now", key="initial_train_later", use_container_width=True):
            st.session_state.training_prompt_dismissed = True
            st.rerun()

    with st.container(border=True):
        st.warning("Model setup is required before the demo can stream incidents.")
        render_prompt_body()


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


def main():
    warnings.filterwarnings(
        "ignore",
        message="LightGBM binary classifier .* TreeExplainer shap values output has changed to a list of ndarray",
        category=UserWarning,
    )

    _apply_pending_home_actions()

    st.set_page_config(page_title="TRUST AI — Wireless Threats (Sundsvall)", layout="wide")
    inject_global_styles()
    st.warning(
        "Disclaimer: This demo is intended solely for educational purposes."
        " It is provided as a demonstration of concept or functionality and should not be used for commercial, production, or operational deployment."
        " All content, data, and examples used in this demo are for learning and research purposes only."
        " The authors or presenters assume no responsibility for any misuse or unintended application of this material.",
        icon="⚠️",
    )

    with st.sidebar:
        st.header("Demo Controls")
        st.caption("Configure the scenario, playback, model behavior, and audience view.")
        sidebar_copy = sidebar_role_copy(st.session_state.get("role_selector_preview", "AI Builder"))
        profile = st.session_state.get("cellular_mode")
        current_profile_label = "Road" if profile else "Yard"
        render_sidebar_summary_card(current_profile_label, st.session_state.get("scenario_selector", "Normal"), st.session_state.get("role_selector_preview", "AI Builder"))
        st.info(sidebar_copy["controls"])
        with st.expander("🧭 Scenario setup", expanded=True):
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
            st.caption(sidebar_copy["scenario"])

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

        with st.expander("⏯ Playback", expanded=False):
            speed = st.slider("Playback speed (ticks/refresh)", 1, 10, 3)
            auto = st.checkbox("Auto stream", True)
            refresh_ms = st.slider("Auto refresh cadence (ms)", 300, 3000, 1200, 100, disabled=not auto)
            reset = st.button("Reset session", use_container_width=True)

        with st.expander("🧠 Model behavior", expanded=False):
            use_conformal = st.checkbox("Conformal risk (calibrated p-value)", True)
            threshold_value = st.slider("Incident threshold (model prob.)", 0.30, 0.95, CFG.threshold, 0.01, key="th_slider")
            CFG.threshold = threshold_value
            if st.session_state.get("suggested_threshold") is not None:
                if st.button(f"Apply suggested threshold ({st.session_state.suggested_threshold:.2f})", use_container_width=True):
                    st.session_state.th_slider = float(st.session_state.suggested_threshold)
            st.caption("Alerts fire when probability ≥ threshold; p-value refines severity if enabled.")
            st.caption(sidebar_copy["model"])
            retrain = st.button("Run model setup / refresh", use_container_width=True)

        with st.expander("👥 HITL policy", expanded=False):
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
            st.caption("These controls change how prior human reviews influence duplicate suppression and triage ordering.")

        with st.expander("🎛 Display and audience", expanded=False):
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
            st.caption(sidebar_copy["display"])

        with st.expander("💡 Guidance", expanded=False):
            help_mode = st.checkbox("Help mode (inline hints)", True)
            show_eu_status = st.checkbox("Show EU AI Act status banner", True)
            st.caption(sidebar_copy["guidance"])
            if st.button("Open model setup guide", use_container_width=True):
                st.session_state.training_prompt_dismissed = False
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
            disk_artifacts["artifact_source"] = "Disk cache"
            store[MODEL_KEY] = disk_artifacts

    if (not CFG.retrain_on_start) and (st.session_state.get("model") is None) and (MODEL_KEY in store):
        artifacts = store[MODEL_KEY]
        st.session_state.model = artifacts["model"]
        st.session_state.scaler = artifacts["scaler"]
        st.session_state.explainer = artifacts["explainer"]
        st.session_state.conformal_scores = artifacts["conformal_scores"]
        st.session_state.metrics = artifacts["metrics"]
        st.session_state.baseline = artifacts["baseline"]
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
        trained_at = artifacts.get("trained_at")
        trained_note = f" (saved at {trained_at})" if trained_at else ""
        st.info(f"Loaded cached model{trained_note} — no setup refresh needed. Use **Run model setup / refresh** to rebuild the models if required.")
        st.session_state.training_prompt_dismissed = False

    if retrain or (CFG.retrain_on_start and st.session_state.get("model") is None and MODEL_KEY not in store):
        st.session_state.training_prompt_dismissed = True
        train_model_with_progress(n_ticks=350)

    if (
        st.session_state.get("model") is None
        and not st.session_state.get("training_prompt_dismissed", False)
        and st.session_state.get("welcome_prompt_dismissed", False)
    ):
        _render_initial_training_prompt()

    if st.session_state.get("model") is not None:
        if auto:
            for _ in range(speed):
                tick_once(scenario, use_conformal)
        elif st.button("Step once"):
            tick_once(scenario, use_conformal)

    if st.session_state.get("model") is None:
        st.warning("Model setup has not been run yet. Start with the Home tab or use **Run model setup / refresh** in the sidebar.")
    else:
        st.caption("Use the Home tab for onboarding, or jump directly into the live workflow tabs below.")

    tab_order = ROLE_TAB_ORDER.get(role, ROLE_TAB_ORDER["End User"])
    tab_renderers = {
        "Home": lambda: render_home_tab(role, scenario, profile, help_mode, show_eu_status),
        "Overview": lambda: render_overview_tab(scenario, show_map, type_filter, use_conformal, role),
        "Fleet View": lambda: render_fleet_tab(show_heatmap, role),
        "Incidents": lambda: render_incidents_tab(role),
        "Insights": lambda: render_insights_tab(role),
        "Governance": lambda: render_governance_tab(role),
    }

    selected_tab = _render_primary_navigation(tab_order)
    tab_renderers[selected_tab]()

    if st.session_state.get("model") is not None and auto:
        st_autorefresh(interval=refresh_ms, key="demo_auto_stream_refresh")

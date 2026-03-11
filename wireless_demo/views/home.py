from contextlib import nullcontext

import numpy as np
import streamlit as st

from ..attack_education import render_attack_academy
from ..training import train_model_with_progress
from ..ux import (
    SCENARIO_COPY,
    metric_role_copy,
    render_demo_storyline,
    render_footerline,
    render_funding_acknowledgement,
    render_header,
    render_model_status_card,
    render_quickstart,
    render_role_flow_hint,
    render_section_card,
    render_tab_intro,
)


ROLE_HOME_COPY = {
    "End User": {
        "headline": "Start the demo with a simple guided path.",
        "body": "This demo shows how AI can monitor wireless operations, raise suspicious events, and keep people in control of the final decision.",
    },
    "Domain Expert": {
        "headline": "Start with the scenario and analyst workflow.",
        "body": "This demo combines wireless telemetry, anomaly detection, threat typing, and human review so you can validate whether the signals match operational reality.",
    },
    "Regulator": {
        "headline": "Start with a high-level assurance view.",
        "body": "This demo is designed to show not only AI outputs, but also the transparency, confidence controls, and human oversight around those outputs.",
    },
    "AI Builder": {
        "headline": "Start by choosing what system behavior you want to test.",
        "body": "This demo lets you explore the full loop from synthetic telemetry to anomaly scoring, attack typing, review actions, and governance evidence.",
    },
    "Executive": {
        "headline": "Start with the business story of the demo.",
        "body": "This demo explains how the system detects wireless threats, highlights operational risk, and shows where trust and accountability controls sit around the AI.",
    },
}


QUICK_PATHS = [
    ("🛰️", "Overview", "See the live posture of the fleet and current risk pattern.", "Live monitoring"),
    ("🚨", "Incidents", "Review alerts, evidence, and human decisions.", "Triage queue"),
    ("🧠", "Insights", "Understand the model logic and confidence checks.", "Explain AI"),
    ("🛡️", "Governance", "Review oversight, auditability, and trustworthy AI concepts.", "Trust controls"),
]

SCENARIO_BUTTONS = [
    ("🟢", "Normal", "Baseline"),
    ("📡", "Jamming (localized)", "RF interference"),
    ("📶", "Access Breach (AP/gNB)", "Access attack"),
    ("🛰️", "GPS Spoofing (subset)", "Location attack"),
    ("🧾", "Data Tamper (gateway)", "Integrity issue"),
]

ROLE_BUTTONS = [
    ("👤", "End User", "Simple guided view"),
    ("🧪", "Domain Expert", "Operational analyst"),
    ("🏛️", "Regulator", "Assurance view"),
    ("🤖", "AI Builder", "Technical view"),
    ("📊", "Executive", "Leadership summary"),
]


def _render_card(icon, title, copy, chip=None):
    chip_html = f"<div class='home-chip'>{chip}</div>" if chip else ""
    st.markdown(
        f"""
        <div class="home-card">
            <div class="home-card-icon">{icon}</div>
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
            <div class="home-icon-badge">{icon}</div>
            <div class="home-icon-label">{title}</div>
            <div class="home-icon-copy">{copy}</div>
            {caption_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _section_container(title, compact_mode, expanded=False):
    if compact_mode:
        return st.expander(title, expanded=expanded)
    st.markdown(f"### {title}")
    return nullcontext()


def render_home_tab(role, scenario, profile, help_mode, show_eu_status):
    render_header(profile, scenario, role)
    render_quickstart(help_mode, show_eu_status, scenario)
    render_demo_storyline(
        model_ready=st.session_state.get("model") is not None,
        incident_count=len(st.session_state.get("incidents", [])),
        scenario=scenario,
    )

    metric_copy = metric_role_copy(role)
    metric_keys = {
        "devices": metric_copy["devices"],
        "incidents": metric_copy["incidents"],
        "quality": metric_copy["quality"],
        "risk": metric_copy["risk"],
        "train": metric_copy["train"],
    }
    probs = list(st.session_state.latest_probs.values())
    metrics = st.session_state.get("metrics") or {}
    train_secs = st.session_state.get("last_train_secs")

    render_section_card(
        "Demo snapshot",
        "These high-level metrics help the audience quickly understand scale, current alert load, model quality, and how recently the demo was refreshed.",
        kicker="At a glance",
    )
    with st.container(border=True):
        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            st.metric(metric_keys["devices"][0], len(st.session_state.devices), help=metric_keys["devices"][1])
        with k2:
            st.metric(metric_keys["incidents"][0], len(st.session_state.incidents), help=metric_keys["incidents"][1])
        with k3:
            st.metric(metric_keys["quality"][0], f"{metrics.get('auc', 0.0):.2f}", help=metric_keys["quality"][1])
        with k4:
            st.metric(metric_keys["risk"][0], f"{(np.mean(probs) if probs else 0):.2f}", help=metric_keys["risk"][1])
        with k5:
            st.metric(metric_keys["train"][0], f"{int(train_secs)}s" if train_secs else "—", help=metric_keys["train"][1])

    render_role_flow_hint(role)
    render_tab_intro("Home", role)

    mode_cols = st.columns([1.2, 3])
    compact_mode = mode_cols[0].toggle("Compact Home", value=True, key="home_compact_mode")
    mode_cols[1].caption(
        "Compact mode collapses the Home sections for faster scanning. Turn it off for the full walkthrough on one page."
    )

    role_copy = ROLE_HOME_COPY.get(role, ROLE_HOME_COPY["End User"])
    scenario_copy = SCENARIO_COPY.get(scenario, SCENARIO_COPY["Normal"])

    st.markdown(
        f"""
        <div class="home-hero">
            <div class="home-hero-title">{role_copy['headline']}</div>
            <div class="home-hero-copy">{role_copy['body']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with _section_container("Model status", compact_mode, expanded=st.session_state.get("model") is not None):
        render_section_card(
            "Model status",
            "Check whether the detector is ready, whether artifacts were loaded from cache or fresh training, and whether the app is prepared for the live monitoring workflow.",
            kicker="System readiness",
        )
        render_model_status_card(compact=False)

    with _section_container("Learn the attacks", compact_mode, expanded=False):
        render_section_card(
            "Learn the attacks",
            "This section explains each scenario in plain language first, then gives the technical cues that the rest of the demo will surface.",
            kicker="Education",
        )
        render_attack_academy(role, selected_scenario=scenario)

    with _section_container("About this demo", compact_mode, expanded=True):
        render_section_card(
            "About this demo",
            "Use this summary to explain the end-to-end story: telemetry comes in, AI highlights suspicious behavior, attack typing adds meaning, and humans stay in control of the final decision.",
            kicker="Storyline",
        )
        top_left, top_right = st.columns([1.15, 0.85])
        with top_left:
            with st.container(border=True):
                st.markdown(
                    "- Watches simulated wireless and logistics telemetry across a fleet.  \n"
                    "- Detects suspicious behavior with an anomaly model.  \n"
                    "- Explains the likely threat type with model output plus domain rules.  \n"
                    "- Keeps a human reviewer in the loop for approve, dismiss, or escalate decisions."
                )
        with top_right:
            _render_card("📍", scenario, scenario_copy["summary"], chip=f"Watch for: {scenario_copy['signals']}")

    with _section_container("Start here", compact_mode, expanded=not st.session_state.get("model") is not None):
        render_section_card(
            "Start here",
            "This three-step path gives any audience a quick way to begin the demo without needing to understand the full interface first.",
            kicker="Quick onboarding",
        )
        st.markdown("<div class='home-section-note'>Pick a scenario, choose an audience view, then move to the tab that matches your goal.</div>", unsafe_allow_html=True)
        explainer_cols = st.columns(3)
        with explainer_cols[0]:
            _render_card("1️⃣", "Pick a scenario", "Choose the threat story you want to demonstrate.")
        with explainer_cols[1]:
            _render_card("2️⃣", "Pick a view", "Switch the explanation style for the audience in front of you.")
        with explainer_cols[2]:
            _render_card("3️⃣", "Open a tab", "Go to Overview, Incidents, Insights, or Governance next.")

    with _section_container("Quick scenario selection", compact_mode):
        render_section_card(
            "Quick scenario selection",
            "Choose the threat story you want to demonstrate. Each button changes the operational narrative for the rest of the app.",
            kicker="Scenario picker",
        )
        scenario_cols = st.columns(len(SCENARIO_BUTTONS))
        for col, (icon, scenario_name, caption) in zip(scenario_cols, SCENARIO_BUTTONS):
            with col:
                _render_icon_tile(icon, scenario_name, SCENARIO_COPY[scenario_name]["summary"], caption=caption)
                if st.button("Choose", key=f"home_scenario_{scenario_name}", use_container_width=True):
                    st.session_state.pending_home_scenario = scenario_name
                    st.session_state.home_message = f"Scenario set to {scenario_name}. Open Overview or Incidents next."
                    st.rerun()

    with _section_container("Choose your audience view", compact_mode):
        render_section_card(
            "Choose your audience view",
            "Switch the narrative framing for the person in front of you without changing the underlying demo behavior.",
            kicker="Audience mode",
        )
        role_cols = st.columns(len(ROLE_BUTTONS))
        for col, (icon, role_name, caption) in zip(role_cols, ROLE_BUTTONS):
            with col:
                _render_icon_tile(icon, role_name, ROLE_HOME_COPY[role_name]["headline"], caption=caption)
                if st.button("Use view", key=f"home_role_{role_name}", use_container_width=True):
                    st.session_state.pending_home_role = role_name
                    st.session_state.home_message = f"Viewer role changed to {role_name}. The guidance across the demo has been updated."
                    st.rerun()

    with _section_container("Explore the demo", compact_mode):
        render_section_card(
            "Explore the demo",
            "Use these quick paths when you already know which part of the story you want to show next: live posture, incidents, explanation, or trust controls.",
            kicker="Navigation",
        )
        path_cols = st.columns(len(QUICK_PATHS))
        for col, (icon, tab_name, copy, caption) in zip(path_cols, QUICK_PATHS):
            with col:
                _render_icon_tile(icon, tab_name, copy, caption=caption)
                if st.button("Go next", key=f"home_path_{tab_name}", use_container_width=True):
                    st.session_state.home_message = f"Next step: open the {tab_name} tab."

    with _section_container("Model setup", compact_mode):
        render_section_card(
            "Model setup",
            "Run setup when you want fresh model artifacts, updated thresholds, and the full transparency workflow enabled across the demo.",
            kicker="Setup",
        )
        setup_cols = st.columns([1, 2])
        with setup_cols[0]:
            if st.button("⚙️ Run model setup", key="home_train_model", use_container_width=True):
                st.session_state.training_prompt_dismissed = True
                train_model_with_progress(n_ticks=350)
                st.session_state.home_message = "Model setup completed. You can now use the live monitoring tabs."
                st.rerun()
        with setup_cols[1]:
            with st.container(border=True):
                st.info("Run model setup when you want fresh model artifacts, updated thresholds, and full transparency views.")

    with _section_container("Project context", compact_mode):
        render_section_card(
            "Project context",
            "This demo is supported by public and research funding partners. Use these links when you want to acknowledge the project context behind the work.",
            kicker="Acknowledgement",
        )
        render_funding_acknowledgement()
        render_footerline()

    if st.session_state.get("home_message"):
        st.success(st.session_state.home_message)
        st.caption("Tabs cannot auto-switch in Streamlit, so use the tab bar above to continue.")

"""Plain-language views for visitors who do not need the analyst controls."""

import streamlit as st

from .config import CFG
from .helpers import feature_base, feature_label
from .hitl import get_review_status, incident_review_key, record_review
from .ux import SCENARIO_COPY


def _go_to(tab_name):
    st.session_state.pending_primary_tab = tab_name
    st.rerun()


def render_simple_home(scenario, profile, refresh_interval=None):
    st.title("Understand wireless threats in a few clicks")
    st.write(
        "This demo watches a simulated fleet, spots unusual wireless activity, "
        "and lets a person review each alert. No real devices or personal data are used."
    )

    if st.session_state.get("model") is None:
        st.warning("The demo model is not ready yet.")
        if st.button("Set up demo model", type="primary"):
            st.session_state.open_training_dialog = True
            st.rerun()
        return

    st.markdown("### Start here")
    st.write("1. Choose a scenario in the sidebar.  2. Watch the live activity.  3. Review any alerts.")
    with st.container(border=True):
        st.markdown(f"**Current scenario: {scenario}**")
        st.write(SCENARIO_COPY[scenario]["summary"])
        st.caption(f"Simulation setting: {'Road' if profile.startswith('Road') else 'Yard'}. You can change this in Advanced view.")
        action_cols = st.columns(2)
        if action_cols[0].button("Watch live activity", type="primary", use_container_width=True):
            st.session_state.pending_auto_stream = True
            _go_to("Overview")
        if action_cols[1].button("Try changed device data", use_container_width=True):
            st.session_state.pending_home_scenario = "Data Tamper (gateway)"
            st.session_state.pending_auto_stream = True
            _go_to("Overview")

    st.markdown("### What is happening now")

    def status_body():
        tick = int(st.session_state.get("tick", 0))
        incidents = st.session_state.get("incidents", [])
        latest_probs = st.session_state.get("latest_probs", {})
        summary = st.columns(3)
        summary[0].metric("Devices monitored", len(st.session_state.get("devices", [])))
        summary[1].metric("Devices needing attention", sum(prob >= CFG.threshold for prob in latest_probs.values()))
        summary[2].metric("Alerts recorded", len(incidents))
        if tick < CFG.rolling_len:
            st.info(f"The live view needs about {CFG.rolling_len} simulation steps before it can score devices.")
        elif incidents:
            if st.button("Review alerts", use_container_width=True):
                _go_to("Incidents")
        else:
            st.success("No alerts have been recorded yet. Try changed device data to see how detection works.")

    if refresh_interval:
        @st.fragment(run_every=refresh_interval)
        def live_status():
            status_body()

        live_status()
    else:
        status_body()

    with st.expander("How does the demo decide what to flag?"):
        st.write(
            "It compares recent signal, network, location, and data-integrity readings "
            "with patterns learned from synthetic examples. An alert is a prompt for human review, "
            "not a confirmed attack."
        )


def render_simple_overview(scenario, refresh_interval=None):
    st.title("Live activity")
    st.caption("Synthetic fleet data · alerts need human review")

    def body():
        tick = int(st.session_state.get("tick", 0))
        latest_probs = st.session_state.get("latest_probs", {})
        active = [(device_id, prob) for device_id, prob in latest_probs.items() if prob >= CFG.threshold]
        st.markdown(f"**Scenario:** {scenario}")
        st.write(SCENARIO_COPY[scenario]["summary"])
        metrics = st.columns(3)
        metrics[0].metric("Simulation step", tick)
        metrics[1].metric("Devices monitored", len(st.session_state.get("devices", [])))
        metrics[2].metric("Devices needing attention", len(active))

        if tick < CFG.rolling_len:
            st.info(f"Collecting recent readings. Device scores appear after about {CFG.rolling_len} steps.")
        elif active:
            st.warning(f"{len(active)} device(s) have unusual readings. Open Alerts to review them.")
        else:
            st.success("No devices are above the alert threshold right now.")

        if latest_probs:
            st.markdown("### Devices to watch")
            for device_id, prob in sorted(latest_probs.items(), key=lambda item: item[1], reverse=True)[:5]:
                label = "Needs review" if prob >= CFG.threshold else "Looks normal"
                st.write(f"{device_id} · {label}")
        if st.button("Open alerts", type="primary", use_container_width=True):
            _go_to("Incidents")
        st.caption("Need maps, charts, or model details? Turn off Simple view in the sidebar.")

    if refresh_interval:
        @st.fragment(run_every=refresh_interval)
        def live_body():
            body()

        live_body()
    else:
        body()


def _latest_incidents_by_device(incidents):
    seen = set()
    latest = []
    for incident in reversed(incidents):
        device_id = incident["device_id"]
        if device_id in seen:
            continue
        seen.add(device_id)
        latest.append(incident)
    return latest


def render_simple_incidents(refresh_interval=None):
    st.title("Alerts to review")
    st.write("An alert means the simulated readings look unusual. You decide what to do with it.")

    def body():
        incidents = _latest_incidents_by_device(st.session_state.get("incidents", []))
        pending = [item for item in incidents if get_review_status(item) == "Pending Review"]
        reviewed = [item for item in incidents if get_review_status(item) != "Pending Review"]
        st.caption(f"{len(pending)} device(s) waiting for review")
        if not incidents:
            st.info("No alerts yet. Keep the simulation running or try changed device data from Start.")
            return

        show_reviewed = st.checkbox("Show reviewed alerts", value=False, key="simple_show_reviewed")
        visible = (pending + reviewed if show_reviewed else pending)[:8]
        if not visible:
            st.success("All current device alerts have been reviewed.")
        for incident in visible:
            status = get_review_status(incident)
            with st.container(border=True):
                st.subheader(f"{incident['device_id']} · {incident.get('severity', 'Alert')} alert")
                st.write(f"Possible issue: {incident.get('type_label') or 'Unusual wireless activity'}")
                st.caption(f"{incident.get('scenario', 'Scenario')} · simulation step {incident.get('tick', '—')} · Review: {status}")
                reasons = incident.get("reasons", [])[:2]
                if reasons:
                    names = ", ".join(feature_label(feature_base(item["feature"])) for item in reasons)
                    st.write(f"Readings that influenced this alert: {names}.")
                if status == "Pending Review":
                    actions = st.columns(3)
                    choices = [
                        ("Looks real", "Approved"),
                        ("False alarm", "False Positive"),
                        ("Need expert help", "Escalated"),
                    ]
                    for column, (label, decision) in zip(actions, choices):
                        if column.button(label, key=f"simple_{decision}_{incident_review_key(incident)}", use_container_width=True):
                            record_review(incident, decision, "End User")
                            st.rerun()
                else:
                    st.write(f"Decision recorded: {status}.")
        st.caption("For full evidence, filtering, and review notes, turn off Simple view.")

    if refresh_interval:
        @st.fragment(run_every=refresh_interval)
        def live_body():
            body()

        live_body()
    else:
        body()

import pandas as pd
import plotly.express as px
import streamlit as st

from ..ux import render_section_card, render_tab_intro


ROLE_FLEET_CALLOUT = {
    "End User": "Use this page to compare devices quickly without going deep into model internals.",
    "Domain Expert": "Compare devices here to separate localized anomalies from broader fleet-wide effects.",
    "Regulator": "Treat this as supporting evidence for consistency across devices rather than the main accountability view.",
    "AI Builder": "Use fleet comparisons to spot feature drift, outliers, and telemetry patterns that may affect model quality.",
    "Executive": "Use this page only when you need to know how broadly a scenario affects the fleet.",
}


def render_fleet_tab(show_heatmap, role):
    render_tab_intro("Fleet View", role)
    st.info(f"{role} focus: {ROLE_FLEET_CALLOUT.get(role, ROLE_FLEET_CALLOUT['End User'])}")
    render_section_card(
        "Fleet workspace",
        "Use this tab to compare device behavior, scan for broad drift patterns, and check whether the current scenario is isolated or fleet-wide.",
        kicker="Comparison view",
    )
    fleet_records = pd.DataFrame(list(st.session_state.fleet_records))
    latest_probs = st.session_state.get("latest_probs", {})
    top_device, top_prob = (max(latest_probs.items(), key=lambda item: item[1]) if latest_probs else ("—", 0.0))
    summary_cols = st.columns(3)
    summary_cols[0].metric("Devices in fleet", len(st.session_state.devices))
    summary_cols[1].metric("Latest tick", st.session_state.get("tick", 0))
    summary_cols[2].metric("Top device risk", f"{top_device} · {top_prob:.2f}" if latest_probs else "Waiting for telemetry")

    with st.container(border=True):
        control_cols = st.columns([1.3, 1, 1.1])
        device_query = control_cols[0].text_input("Search devices", placeholder="Device ID", key="fleet_device_query").strip().lower()
        available_types = sorted(st.session_state.devices["type"].unique().tolist())
        selected_types = control_cols[1].multiselect("Device types", available_types, default=available_types, key="fleet_type_filter")
        control_cols[2].caption("Use the heatmap for fleet-wide drift, then narrow the inventory to inspect the affected devices.")

    if len(fleet_records) > 0 and show_heatmap:
        recent = fleet_records[fleet_records["tick"] >= st.session_state.tick - 40]
        cols = [
            "snr",
            "packet_loss",
            "latency_ms",
            "jitter_ms",
            "pos_error_m",
            "crc_err",
            "throughput_mbps",
            "channel_util",
            "noise_floor_dbm",
            "cca_busy_frac",
            "phy_error_rate",
            "deauth_rate",
            "assoc_churn",
            "eapol_retry_rate",
            "dhcp_fail_rate",
        ]
        cols = [col for col in cols if col in recent.columns]
        if len(cols) > 0:
            mat = recent.groupby("device_id")[cols].mean()
            z_values = (mat - mat.mean()) / mat.std(ddof=0).replace(0, 1)
            st.plotly_chart(
                px.imshow(
                    z_values.T,
                    color_continuous_scale="RdBu_r",
                    aspect="auto",
                    labels=dict(color="z-score"),
                    title="Fleet heatmap (recent mean z-scores)",
                ),
                use_container_width=True,
                key="fleet_heatmap",
            )
        else:
            st.info("Recent fleet telemetry does not yet contain enough comparable metrics for the heatmap.")
    elif not show_heatmap:
        st.info("Enable the fleet heatmap from the sidebar to compare recent device behavior at a glance.")
    else:
        st.info("Start playback to populate fleet telemetry before comparing device behavior.")

    render_section_card(
        "Fleet inventory",
        "Filter the current device list to inspect which asset types are in scope and which devices deserve deeper review next.",
        kicker="Inventory",
    )
    devices_df = st.session_state.devices.copy()
    if selected_types:
        devices_df = devices_df[devices_df["type"].isin(selected_types)]
    if device_query:
        devices_df = devices_df[devices_df["device_id"].str.lower().str.contains(device_query)]
    devices_df["live_risk"] = devices_df["device_id"].map(latest_probs).fillna(0.0)
    st.caption(f"Showing {len(devices_df)} of {len(st.session_state.devices)} devices.")
    st.dataframe(
        devices_df.sort_values(["live_risk", "device_id"], ascending=[False, True]),
        width="stretch",
        hide_index=True,
    )

import pandas as pd
import plotly.express as px
import streamlit as st

from ..config import CFG
from ..ux import render_focus_callout, render_section_card, render_tab_intro, style_plotly_figure


ROLE_FLEET_CALLOUT = {
    "End User": "Use this page to compare devices quickly without going deep into model internals.",
    "Domain Expert": "Compare devices here to separate localized anomalies from broader fleet-wide effects.",
    "Regulator": "Treat this as supporting evidence for consistency across devices rather than the main accountability view.",
    "AI Builder": "Use fleet comparisons to spot feature drift, outliers, and telemetry patterns that may affect model quality.",
    "Executive": "Use this page only when you need to know how broadly a scenario affects the fleet.",
}

FLEET_METRIC_LABELS = {
    "snr": "SNR",
    "packet_loss": "Packet loss",
    "latency_ms": "Latency",
    "jitter_ms": "Jitter",
    "pos_error_m": "Position error",
    "crc_err": "CRC errors",
    "throughput_mbps": "Throughput",
    "channel_util": "Channel util.",
    "noise_floor_dbm": "Noise floor",
    "cca_busy_frac": "CCA busy",
    "phy_error_rate": "PHY errors",
    "deauth_rate": "Deauth rate",
    "assoc_churn": "Assoc. churn",
    "eapol_retry_rate": "EAPOL retries",
    "dhcp_fail_rate": "DHCP fails",
}

RISK_BAND_STYLES = {
    "High": "background-color: rgba(239, 68, 68, 0.14); color: #991b1b; font-weight: 700;",
    "Watch": "background-color: rgba(245, 158, 11, 0.16); color: #92400e; font-weight: 700;",
    "Normal": "background-color: rgba(22, 163, 74, 0.12); color: #166534; font-weight: 700;",
    "Unknown": "background-color: rgba(71, 85, 105, 0.12); color: #475569; font-weight: 700;",
}


def _fleet_risk_band(probability):
    try:
        probability = float(probability)
    except Exception:
        return "Unknown"
    if probability >= 0.85:
        return "High"
    if probability >= CFG.threshold:
        return "Watch"
    return "Normal"


def _style_fleet_inventory(df: pd.DataFrame):
    def highlight_risk_band(value):
        return RISK_BAND_STYLES.get(str(value), "")

    def highlight_top_rows(row):
        if float(row.get("live_risk", 0.0)) >= CFG.threshold:
            return ["background-color: rgba(255, 248, 235, 0.75);"] * len(row)
        return [""] * len(row)

    return (
        df.style
        .apply(highlight_top_rows, axis=1)
        .map(highlight_risk_band, subset=["risk_band"])
        .format({"live_risk": "{:.2f}", "speed_mps": "{:.2f}"})
    )


def render_fleet_tab(show_heatmap, role, refresh_interval=None):
    render_tab_intro("Fleet View", role)
    render_section_card(
        "Fleet workspace",
        "Use this tab to compare device behavior, scan for drift, and decide whether the current scenario is isolated or fleet-wide.",
        kicker="Comparison view",
    )

    with st.container(border=True):
        control_cols = st.columns([1.3, 1, 1.1])
        device_query = control_cols[0].text_input("Search devices", placeholder="Device ID", key="fleet_device_query").strip().lower()
        available_types = sorted(st.session_state.devices["type"].unique().tolist())
        selected_types = control_cols[1].multiselect("Device types", available_types, default=available_types, key="fleet_type_filter")
        control_cols[2].caption("Use the heatmap for fleet-wide drift, then narrow the inventory to inspect affected devices.")

    summary_interval = max(float(refresh_interval), 1.0) if refresh_interval else None
    body_interval = max(float(refresh_interval), 2.2) if refresh_interval else None

    def _render_fleet_summary_content():
        latest_probs = st.session_state.get("latest_probs", {})
        active_alerts = sum(prob >= CFG.threshold for prob in latest_probs.values())
        mean_risk = (sum(latest_probs.values()) / len(latest_probs)) if latest_probs else 0.0
        top_device, top_prob = (max(latest_probs.items(), key=lambda item: item[1]) if latest_probs else ("—", 0.0))
        summary_cols = st.columns(4)
        summary_cols[0].metric("Devices in fleet", len(st.session_state.devices))
        summary_cols[1].metric("Devices above threshold", active_alerts)
        summary_cols[2].metric("Average fleet risk", f"{mean_risk:.2f}" if latest_probs else "—")
        summary_cols[3].metric("Top device risk", f"{top_device} · {top_prob:.2f}" if latest_probs else "Waiting for telemetry")

        if latest_probs:
            st.markdown(
                "<div class='quick-chip-row'>"
                f"<span class='quick-chip'>Latest tick: {st.session_state.get('tick', 0)}</span>"
                f"<span class='quick-chip'>Threshold: {CFG.threshold:.2f}</span>"
                f"<span class='quick-chip'>Top device: {top_device}</span>"
                "</div>",
                unsafe_allow_html=True,
            )

    def _render_fleet_body_content():
        fleet_records = pd.DataFrame(list(st.session_state.fleet_records))
        latest_probs = st.session_state.get("latest_probs", {})
        devices_df = st.session_state.devices.copy()
        devices_df["live_risk"] = devices_df["device_id"].map(latest_probs).fillna(0.0)
        devices_df["risk_band"] = devices_df["live_risk"].map(_fleet_risk_band)

        top_cols = st.columns([1.45, 0.9])

        with top_cols[0]:
            render_section_card(
                "Fleet heatmap",
                "Use the heatmap to spot which metrics are drifting most across devices in the recent window.",
                kicker="Heatmap view",
            )
            render_focus_callout(
                "What a z-score means",
                "A z-score shows how far a device is from the recent fleet average for one metric. `0` means near the fleet norm, positive values mean above the norm, and negative values mean below it. Larger magnitudes mean a stronger deviation.",
                variant="info",
            )

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
                    z_values = z_values.rename(index=FLEET_METRIC_LABELS)
                    fig = px.imshow(
                        z_values.T,
                        color_continuous_scale="RdBu_r",
                        aspect="auto",
                        labels=dict(color="z-score"),
                        title="Fleet heatmap (recent mean z-scores)",
                    )
                    st.plotly_chart(
                        style_plotly_figure(fig, height=420),
                        use_container_width=True,
                        config={"displayModeBar": False},
                        key="fleet_heatmap",
                    )
                    st.markdown(
                        "<div class='quick-chip-row'>"
                        "<span class='quick-chip'>Red = above fleet norm</span>"
                        "<span class='quick-chip'>Blue = below fleet norm</span>"
                        "<span class='quick-chip'>0 = near fleet norm</span>"
                        "<span class='quick-chip'>Window = recent 40 ticks</span>"
                        "</div>",
                        unsafe_allow_html=True,
                    )
                    st.caption("Read across each row to see which devices deviate most from the recent fleet baseline for that metric.")
                else:
                    st.info("Recent fleet telemetry does not yet contain enough comparable metrics for the heatmap.")
            elif not show_heatmap:
                render_focus_callout("Heatmap hidden", "Enable the fleet heatmap in the sidebar to compare recent device behavior at a glance.")
            else:
                render_focus_callout("Heatmap waiting", "Start playback to populate fleet telemetry before comparing device behavior.")

        with top_cols[1]:
            render_section_card(
                "Fleet readout",
                "Use this panel to quickly judge spread, asset mix, and which devices deserve a closer look next.",
                kicker="Snapshot",
            )
            with st.container(border=True):
                risk_counts = devices_df["risk_band"].value_counts().reindex(["High", "Watch", "Normal"], fill_value=0)
                band_cols = st.columns(3)
                band_cols[0].metric("High risk", int(risk_counts["High"]))
                band_cols[1].metric("Watch", int(risk_counts["Watch"]))
                band_cols[2].metric("Normal", int(risk_counts["Normal"]))

            with st.container(border=True):
                st.caption("Asset mix")
                type_counts = devices_df.groupby("type").size().reset_index(name="count")
                fig = px.bar(type_counts, x="type", y="count", title="Devices by type")
                st.plotly_chart(
                    style_plotly_figure(fig, height=260),
                    use_container_width=True,
                    config={"displayModeBar": False},
                    key="fleet_asset_mix",
                )

            top_risk = devices_df.sort_values(["live_risk", "device_id"], ascending=[False, True]).head(5)
            with st.container(border=True):
                st.caption("Top devices to review")
                st.markdown(
                    "<div class='quick-chip-row'>"
                    + "".join(
                        [
                            f"<span class='quick-chip'>{row.device_id} · {row.risk_band} · {row.live_risk:.2f}</span>"
                            for row in top_risk.itertuples()
                        ]
                    )
                    + "</div>",
                    unsafe_allow_html=True,
                )
                st.dataframe(
                    top_risk[["device_id", "type", "live_risk", "risk_band"]],
                    width="stretch",
                    hide_index=True,
                )

        render_section_card(
            "Fleet inventory",
            "Filter the device list to see which asset types are in scope and which devices deserve deeper review next.",
            kicker="Inventory",
        )
        if selected_types:
            devices_df = devices_df[devices_df["type"].isin(selected_types)]
        if device_query:
            devices_df = devices_df[devices_df["device_id"].str.lower().str.contains(device_query)]

        inventory_df = devices_df[["device_id", "type", "live_risk", "risk_band", "speed_mps", "active"]].copy()
        st.caption(f"Showing {len(devices_df)} of {len(st.session_state.devices)} devices.")
        st.dataframe(
            _style_fleet_inventory(inventory_df.sort_values(["live_risk", "device_id"], ascending=[False, True])),
            width="stretch",
            hide_index=True,
        )

    if summary_interval:
        @st.fragment(run_every=summary_interval)
        def _render_fleet_summary_fragment():
            _render_fleet_summary_content()

        _render_fleet_summary_fragment()
    else:
        _render_fleet_summary_content()

    if body_interval:
        @st.fragment(run_every=body_interval)
        def _render_fleet_body_fragment():
            _render_fleet_body_content()

        _render_fleet_body_fragment()
    else:
        _render_fleet_body_content()

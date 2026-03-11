import pandas as pd
import plotly.express as px
import streamlit as st

from ..ux import render_tab_intro


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
    fleet_records = pd.DataFrame(list(st.session_state.fleet_records))
    summary_cols = st.columns(3)
    summary_cols[0].metric("Devices in fleet", len(st.session_state.devices))
    summary_cols[1].metric("Latest tick", st.session_state.get("tick", 0))
    summary_cols[2].metric("Records buffered", len(fleet_records))

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

    st.markdown("### Fleet inventory")
    st.dataframe(st.session_state.devices, width="stretch")

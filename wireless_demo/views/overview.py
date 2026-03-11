import math

import numpy as np
import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

from ..config import CFG, DEVICE_TYPES
from ..hitl import current_hitl_policy, latest_review_for_device
from ..helpers import conformal_pvalue, haversine_m, meters_to_latlon_offset, severity
from ..ux import render_focus_callout, render_scenario_context, render_section_card, render_tab_intro, style_plotly_figure


ROLE_OVERVIEW_CALLOUT = {
    "End User": "Watch the risk summary, map, and triage queue to see what needs action now.",
    "Domain Expert": "Correlate the scenario, top contributors, and queue ranking to judge whether the pattern looks operationally plausible.",
    "Regulator": "Use this as the entry point for understanding how the system surfaces risk before a human review decision is made.",
    "AI Builder": "Connect live alerting behavior to the thresholds, confidence controls, and queue policy behind it.",
    "Executive": "Use this page to understand current exposure, where it is concentrated, and whether response remains controlled.",
}


@st.cache_data(show_spinner=False)
def _cached_circle_path(center_lat, center_lon, radius_m, lat_mean, n_points=60):
    angles = np.linspace(0, 2 * np.pi, n_points)
    path = []
    for angle in angles:
        north = radius_m * math.sin(angle)
        east = radius_m * math.cos(angle)
        dlat, dlon = meters_to_latlon_offset(north, east, lat_mean)
        path.append([center_lon + dlon, center_lat + dlat])
    return path


def _spotlight_device_rows(df):
    rows = []
    for _, row in df.iterrows():
        severity_label, severity_color = severity(float(row.risk), None)
        rows.append(
            "<div style='display:flex;align-items:center;gap:0.45rem;margin:0.2rem 0;'>"
            f"<span style='display:inline-block;width:0.65rem;height:0.65rem;border-radius:999px;background:{severity_color};'></span>"
            f"<span><strong>{row.device_id}</strong> · risk {row.risk:.2f} · {severity_label}</span>"
            "</div>"
        )
    return rows


def _scenario_spotlight(df_map, scenario):
    if df_map is None or len(df_map) == 0 or scenario == "Normal":
        return None

    if scenario.startswith("Jamming"):
        center = st.session_state.jammer
        radius_m = CFG.jam_radius_m
        label = "jammer zone"
    elif scenario.startswith("Access Breach"):
        center = st.session_state.rogue
        radius_m = CFG.breach_radius_m
        label = "rogue access zone"
    elif scenario.startswith("GPS Spoofing"):
        center = st.session_state.spoofer
        radius_m = CFG.spoof_radius_m
        label = "spoofing zone"
    elif scenario.startswith("Data Tamper"):
        gateway_df = df_map[df_map["type"] == "Gateway"].copy()
        gateways = int(len(gateway_df))
        hot_gateways = int((gateway_df["risk"] >= CFG.threshold).sum())
        top_gateways = gateway_df.sort_values(["risk", "device_id"], ascending=[False, True]).head(3)
        return {
            "title": "Gateway-side tamper path",
            "message": f"This scenario targets gateway or payload-integrity behavior. Watch the {gateways} gateway device(s), with {hot_gateways} currently above the incident threshold.",
            "devices": _spotlight_device_rows(top_gateways),
        }
    else:
        return None

    distances = np.array([haversine_m(row.lat, row.lon, center["lat"], center["lon"]) for row in df_map.itertuples(index=False)])
    zone_df = df_map.loc[distances <= radius_m].copy()
    in_zone = int(len(zone_df))
    hot_in_zone = int((zone_df["risk"] >= CFG.threshold).sum())
    top_zone = zone_df.sort_values(["risk", "device_id"], ascending=[False, True]).head(3)
    return {
        "title": f"Active {label}",
        "message": f"{in_zone} device(s) are currently inside the scenario radius, with {hot_in_zone} already above the incident threshold.",
        "devices": _spotlight_device_rows(top_zone),
    }


def render_overview_tab(scenario, show_map, type_filter, use_conformal, role):
    render_tab_intro("Overview", role)
    render_scenario_context(scenario)
    render_section_card(
        "Live operational picture",
        "Use the map, fleet trends, and queue summary together: the left side shows where the pattern is emerging, while the right side shows how the system prioritizes response.",
        kicker="Live posture",
    )

    df_map = None
    current_tick = int(st.session_state.get("tick", 0))
    latest_probs = st.session_state.get("latest_probs", {})
    incident_count = len(st.session_state.get("incidents", []))
    active_alerts = sum(prob >= CFG.threshold for prob in latest_probs.values())
    elevated_risk = sum(prob >= 0.70 for prob in latest_probs.values())
    top_device, top_prob = (max(latest_probs.items(), key=lambda item: item[1]) if latest_probs else ("—", 0.0))

    if st.session_state.get("model") is not None:
        df_map = st.session_state.devices.copy()
        if type_filter and len(type_filter) < len(DEVICE_TYPES):
            df_map = df_map[df_map["type"].isin(type_filter)].copy()
        df_map["risk"] = df_map["device_id"].map(latest_probs).fillna(0.0)

    with st.container(border=True):
        snapshot_cols = st.columns(4)
        snapshot_cols[0].metric("Current tick", current_tick)
        snapshot_cols[1].metric("Devices above threshold", active_alerts)
        snapshot_cols[2].metric("Elevated-risk devices", elevated_risk)
        snapshot_cols[3].metric("Top live risk", f"{top_device} · {top_prob:.2f}" if latest_probs else "Waiting for telemetry")
        if current_tick < CFG.rolling_len:
            st.caption(f"Warm-up in progress: the detector needs about {CFG.rolling_len} ticks of rolling history before live incidents can appear.")
        elif incident_count > 0:
            st.caption(f"Session status: {incident_count} incident(s) have already been generated in this run.")

    left, right = st.columns([2, 1])

    with left:
        with st.container(border=True):
            st.caption("Geospatial view")
            st.markdown("#### Fleet map and scenario overlays")
        if not show_map:
            render_focus_callout("Map hidden", "Enable geospatial map in the sidebar to visualize devices and scenario radius overlays.")
        elif st.session_state.get("model") is not None:
            latest_device_metrics = {
                device_id: (buf[-1] if buf and len(buf) > 0 else {})
                for device_id, buf in st.session_state.dev_buf.items()
            }
            df_map["snr"] = df_map["device_id"].map(lambda device_id: float(latest_device_metrics.get(device_id, {}).get("snr", np.nan)))
            df_map["packet_loss"] = df_map["device_id"].map(lambda device_id: float(latest_device_metrics.get(device_id, {}).get("packet_loss", np.nan)))

            type_colors = {
                "AMR": [0, 128, 255, 220],
                "Truck": [255, 165, 0, 220],
                "Sensor": [34, 197, 94, 220],
                "Gateway": [147, 51, 234, 220],
            }
            df_map["fill_color"] = df_map["type"].map(type_colors)
            df_map["label"] = df_map.apply(lambda row: f"{row.device_id} ({row.type})", axis=1)
            df_map["radius"] = 6 + (df_map["risk"] * 16)

            layers = [
                pdk.Layer(
                    "ScatterplotLayer",
                    data=df_map,
                    get_position="[lon, lat]",
                    get_fill_color="fill_color",
                    get_radius="radius",
                    get_line_color=[0, 0, 0, 140],
                    get_line_width=1,
                    pickable=True,
                ),
                pdk.Layer(
                    "TextLayer",
                    data=df_map,
                    get_position="[lon, lat]",
                    get_text="label",
                    get_color=[20, 20, 20, 255],
                    get_size=12,
                    get_alignment_baseline="top",
                    get_pixel_offset=[0, 10],
                ),
            ]

            cellular_mode = st.session_state.get("cellular_mode", False)
            infra_label = "gNB" if cellular_mode else "AP"
            rogue_label = "Rogue gNB" if cellular_mode else "Rogue AP"
            ap_df = pd.DataFrame([{"lat": st.session_state.ap["lat"], "lon": st.session_state.ap["lon"], "label": infra_label}])
            layers += [
                pdk.Layer("ScatterplotLayer", data=ap_df, get_position="[lon, lat]", get_fill_color="[30,144,255,240]", get_radius=12),
                pdk.Layer(
                    "TextLayer",
                    data=ap_df,
                    get_position="[lon, lat]",
                    get_text="label",
                    get_color=[30, 144, 255, 255],
                    get_size=14,
                    get_alignment_baseline="bottom",
                    get_pixel_offset=[0, -10],
                ),
            ]

            warn_df = df_map[df_map["risk"] >= CFG.threshold].copy()
            if len(warn_df) > 0:
                warn_df["warn"] = "⚠"
                layers += [
                    pdk.Layer(
                        "TextLayer",
                        data=warn_df,
                        get_position="[lon, lat]",
                        get_text="warn",
                        get_color=[255, 0, 0, 255],
                        get_size=18,
                        get_alignment_baseline="bottom",
                        get_pixel_offset=[0, -18],
                    ),
                    pdk.Layer(
                        "ScatterplotLayer",
                        data=warn_df,
                        get_position="[lon, lat]",
                        get_fill_color="[0,0,0,0]",
                        get_radius=26,
                        stroked=True,
                        get_line_color=[255, 0, 0, 200],
                        get_line_width=2,
                    ),
                ]

            def circle_layer(center, radius_m, color):
                lat_mean = float(st.session_state.devices.lat.mean())
                path = _cached_circle_path(center["lat"], center["lon"], radius_m, lat_mean)
                return pdk.Layer("PathLayer", [{"path": path}], get_path="path", get_color=color, width_scale=4, width_min_pixels=1, opacity=0.25)

            if scenario.startswith("Jamming"):
                jammer = st.session_state.jammer
                jam_df = pd.DataFrame([{"lat": jammer["lat"], "lon": jammer["lon"], "label": "Jammer"}])
                layers += [
                    pdk.Layer("ScatterplotLayer", data=jam_df, get_position="[lon, lat]", get_fill_color="[255,0,0,240]", get_radius=12),
                    pdk.Layer(
                        "TextLayer",
                        data=jam_df,
                        get_position="[lon, lat]",
                        get_text="label",
                        get_color=[255, 0, 0, 255],
                        get_size=14,
                        get_alignment_baseline="bottom",
                        get_pixel_offset=[0, -10],
                    ),
                    circle_layer(jammer, CFG.jam_radius_m, [255, 0, 0]),
                ]
            if scenario.startswith("Access Breach"):
                rogue = st.session_state.rogue
                rogue_df = pd.DataFrame([{"lat": rogue["lat"], "lon": rogue["lon"], "label": rogue_label}])
                layers += [
                    pdk.Layer("ScatterplotLayer", data=rogue_df, get_position="[lon, lat]", get_fill_color="[0,255,255,240]", get_radius=12),
                    pdk.Layer(
                        "TextLayer",
                        data=rogue_df,
                        get_position="[lon, lat]",
                        get_text="label",
                        get_color=[0, 200, 200, 255],
                        get_size=14,
                        get_alignment_baseline="bottom",
                        get_pixel_offset=[0, -10],
                    ),
                    circle_layer(rogue, CFG.breach_radius_m, [0, 200, 200]),
                ]
            if scenario.startswith("GPS Spoofing"):
                spoofer = st.session_state.spoofer
                spf_df = pd.DataFrame([{"lat": spoofer["lat"], "lon": spoofer["lon"], "label": "Spoofer"}])
                layers += [
                    pdk.Layer("ScatterplotLayer", data=spf_df, get_position="[lon, lat]", get_fill_color="[255,215,0,240]", get_radius=12),
                    pdk.Layer(
                        "TextLayer",
                        data=spf_df,
                        get_position="[lon, lat]",
                        get_text="label",
                        get_color=[255, 215, 0, 255],
                        get_size=14,
                        get_alignment_baseline="bottom",
                        get_pixel_offset=[0, -10],
                    ),
                    circle_layer(spoofer, CFG.spoof_radius_m, [255, 215, 0]),
                ]

            deck = pdk.Deck(
                layers=layers,
                initial_view_state=pdk.ViewState(
                    latitude=float(st.session_state.devices.lat.mean()),
                    longitude=float(st.session_state.devices.lon.mean()),
                    zoom=14,
                    pitch=0,
                ),
                map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
                tooltip={
                    "html": "<b>{device_id}</b> • {type}<br/>Risk: {risk:.2f}<br/>SNR: {snr} dB<br/>Loss: {packet_loss}%",
                    "style": {"backgroundColor": "rgba(255,255,255,0.95)", "color": "#111"},
                },
            )
            st.pydeck_chart(deck, use_container_width=True)
            with st.expander("Map legend", expanded=False):
                st.markdown(
                    "- **Blue / Orange / Green / Purple dots**: AMRs, Trucks, Sensors, Gateways  \n"
                    "- **Red ring marker**: device currently above incident threshold  \n"
                    "- **Larger marker radius**: higher live anomaly probability  \n"
                    "- **Colored radius overlays**: active scenario coverage zone"
                )
        else:
            render_focus_callout("Model setup needed", "Run model setup to unlock the live map, risk overlays, and anomaly timeline charts.", variant="warning")

        fleet_records = pd.DataFrame(list(st.session_state.fleet_records))
        render_section_card(
            "Fleet trends",
            "These charts show how average fleet telemetry moves over time, which helps connect local incidents to broader system behavior.",
            kicker="Trend view",
        )
        if len(fleet_records) > 0:
            trend_cols = ["snr", "packet_loss", "latency_ms", "pos_error_m"]
            fleet_trends = fleet_records.groupby("tick")[trend_cols].mean().reset_index()
            chart_cols = st.columns(2)
            for idx, y_axis in enumerate(["snr", "packet_loss", "latency_ms", "pos_error_m"]):
                title = f"Fleet average {y_axis.replace('_', ' ')}"
                fig = px.line(fleet_trends, x="tick", y=y_axis, title=title)
                with chart_cols[idx % 2]:
                    with st.container(border=True):
                        st.plotly_chart(
                            style_plotly_figure(fig, title=title, height=280),
                            use_container_width=True,
                            config={"displayModeBar": False},
                            key=f"overview_{y_axis}",
                        )
        else:
            st.caption("Telemetry charts will populate once the stream begins collecting fleet samples.")

    with right:
        spotlight = _scenario_spotlight(df_map, scenario)
        if spotlight:
            with st.container(border=True):
                st.markdown(f"#### {spotlight['title']}")
                render_focus_callout(
                    "Scenario spotlight",
                    spotlight["message"],
                    variant="warning" if active_alerts > 0 else "info",
                )
                spotlight_devices = spotlight.get("devices", [])
                if spotlight_devices:
                    st.caption("Most affected devices in the active zone")
                    st.markdown("".join(spotlight_devices), unsafe_allow_html=True)

        render_section_card(
            "Queue controls",
            "This column summarizes how human oversight and queue ranking change the order in which operators should inspect devices.",
            kicker="Response focus",
        )
        policy = current_hitl_policy()
        with st.container(border=True):
            st.caption(
                f"HITL policy: suppression {'on' if policy['suppression_enabled'] else 'off'} · "
                f"window {policy['suppression_ticks']} ticks · escalation boost {policy['escalation_boost']:.2f}"
            )
            hitl_stats = st.session_state.get("hitl_live_stats", {})
            if hitl_stats.get("suppressed_alerts") or hitl_stats.get("prioritized_alerts"):
                st.markdown("#### Human oversight effect")
                info_cols = st.columns(2)
                info_cols[0].metric("Suppressed repeats", hitl_stats.get("suppressed_alerts", 0))
                info_cols[1].metric("Prioritized alerts", hitl_stats.get("prioritized_alerts", 0))
                last_effect = hitl_stats.get("last_effect")
                if last_effect:
                    st.caption(
                        f"Latest HITL action: {last_effect['effect']} {last_effect['device_id']} at tick {last_effect['tick']} · {last_effect.get('reason') or 'No reason recorded.'}"
                    )

        leaderboard = []
        if st.session_state.get("model") is not None:
            for _, row in st.session_state.devices.iterrows():
                prob = st.session_state.latest_probs.get(row.device_id, 0.0)
                p_value = conformal_pvalue(prob) if use_conformal else None
                severity_label, _ = severity(prob, p_value)
                latest_review = latest_review_for_device(row.device_id, scenario)
                review_status = latest_review.get("status") if latest_review else "Pending Review"
                queue_score = prob + (policy["escalation_boost"] if review_status == "Escalated" else 0.0)
                leaderboard.append(
                    {
                        "device_id": row.device_id,
                        "type": row.type,
                        "prob": prob,
                        "p_value": p_value,
                        "severity": severity_label,
                        "review_status": review_status,
                        "queue_score": queue_score,
                    }
                )
        if leaderboard:
            with st.container(border=True):
                st.markdown("#### Triage queue")
                st.caption("Escalated devices are boosted to the top; recently false-positive devices can be suppressed from the incident stream.")
                st.dataframe(pd.DataFrame(leaderboard).sort_values(["queue_score", "prob"], ascending=False).head(10), width="stretch")
        else:
            render_focus_callout("No queue yet", "Start playback or run model setup first to generate live risk rankings.")

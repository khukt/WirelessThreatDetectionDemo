import math
from functools import lru_cache

import numpy as np
import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

from ..config import CFG, DEVICE_TYPES
from ..hitl import current_hitl_policy, latest_review_for_device
from ..helpers import conformal_pvalue, haversine_m, meters_to_latlon_offset, severity
from ..ux import render_focus_callout, render_scenario_context, render_section_card, render_tab_intro, style_plotly_figure


TREND_LABELS = {
    "snr": "Signal quality",
    "packet_loss": "Packet loss",
    "latency_ms": "Latency",
    "pos_error_m": "Position error",
}

TREND_DIRECTIONS = {
    "snr": {"higher_is_worse": False, "unit": "dB"},
    "packet_loss": {"higher_is_worse": True, "unit": "%"},
    "latency_ms": {"higher_is_worse": True, "unit": "ms"},
    "pos_error_m": {"higher_is_worse": True, "unit": "m"},
}


def _scenario_watch_text(scenario):
    if scenario.startswith("Jamming"):
        return "Watch for falling signal quality and rising packet loss near the interference radius."
    if scenario.startswith("Access Breach"):
        return "Watch for access-layer disruption near the rogue infrastructure and queue movement toward nearby devices."
    if scenario.startswith("GPS Spoofing"):
        return "Watch for localized position error and navigation drift, especially on mobile assets in the spoofed area."
    if scenario.startswith("Data Tamper"):
        return "Watch for gateway-led anomalies and downstream integrity issues before they spread into the wider queue."
    return "Watch for any device or area that breaks from baseline and starts climbing the queue."


def _scenario_overlay_label(scenario):
    if scenario.startswith("Jamming"):
        return "Interference radius"
    if scenario.startswith("Access Breach"):
        return "Rogue infrastructure zone"
    if scenario.startswith("GPS Spoofing"):
        return "Spoofing radius"
    if scenario.startswith("Data Tamper"):
        return "Gateway integrity focus"
    return "Baseline view"


def _overview_snapshot(df_map):
    if df_map is None or df_map.empty:
        return {
            "visible_devices": 0,
            "avg_risk": 0.0,
            "above_threshold": 0,
            "top_device": "—",
            "top_risk": 0.0,
        }

    top_row = df_map.sort_values(["risk", "device_id"], ascending=[False, True]).iloc[0]
    return {
        "visible_devices": len(df_map),
        "avg_risk": float(df_map["risk"].mean()),
        "above_threshold": int((df_map["risk"] >= CFG.threshold).sum()),
        "top_device": str(top_row["device_id"]),
        "top_risk": float(top_row["risk"]),
    }


def _queue_dataframe(leaderboard, use_conformal):
    queue_df = pd.DataFrame(leaderboard).sort_values(["queue_score", "prob"], ascending=False).head(8).copy()
    queue_df = queue_df.rename(
        columns={
            "device_id": "Device",
            "type": "Type",
            "prob": "Live risk",
            "p_value": "Conformal p-value",
            "severity": "Severity",
            "review_status": "Review",
            "queue_score": "Queue score",
        }
    )
    formatters = {
        "Live risk": "{:.2f}",
        "Queue score": "{:.2f}",
    }
    if use_conformal:
        formatters["Conformal p-value"] = lambda value: "—" if value is None else f"{value:.2f}"
    else:
        queue_df = queue_df.drop(columns=["Conformal p-value"])
    return queue_df, formatters


def _trend_window_summary(fleet_trends, metric):
    if fleet_trends is None or fleet_trends.empty or metric not in fleet_trends.columns:
        return None

    window_size = max(8, min(20, len(fleet_trends) // 3 if len(fleet_trends) >= 12 else len(fleet_trends)))
    baseline = fleet_trends.head(window_size)
    recent = fleet_trends.tail(window_size)
    if baseline.empty or recent.empty:
        return None

    baseline_mean = float(baseline[metric].mean())
    recent_mean = float(recent[metric].mean())
    delta = recent_mean - baseline_mean
    trend_meta = TREND_DIRECTIONS.get(metric, {"higher_is_worse": True, "unit": ""})
    higher_is_worse = trend_meta["higher_is_worse"]
    if abs(delta) < 1e-9:
        status = "Flat"
    elif (delta > 0 and higher_is_worse) or (delta < 0 and not higher_is_worse):
        status = "Worsening"
    else:
        status = "Improving"

    return {
        "baseline_mean": baseline_mean,
        "recent_mean": recent_mean,
        "delta": delta,
        "status": status,
        "unit": trend_meta["unit"],
        "window_size": window_size,
    }


@lru_cache(maxsize=64)
def _cached_circle_path(lat, lon, radius_m, lat_ref, points=72):
    path = []
    for idx in range(points + 1):
        theta = 2 * math.pi * idx / points
        d_north = radius_m * math.cos(theta)
        d_east = radius_m * math.sin(theta)
        dlat, dlon = meters_to_latlon_offset(d_north, d_east, lat_ref)
        path.append([lon + dlon, lat + dlat])
    return path


def _spotlight_target(df_map, scenario):
    if df_map is None or df_map.empty:
        return None

    if scenario.startswith("Jamming"):
        return {
            "title": "Jamming hotspot",
            "center": st.session_state.get("jammer"),
            "radius_m": CFG.jam_radius_m,
            "message": "Devices in the interference radius should trend toward lower signal quality and higher loss.",
        }
    if scenario.startswith("Access Breach"):
        return {
            "title": "Access breach hotspot",
            "center": st.session_state.get("rogue"),
            "radius_m": CFG.breach_radius_m,
            "message": "Devices nearest the rogue infrastructure usually surface first in the triage queue.",
        }
    if scenario.startswith("GPS Spoofing"):
        return {
            "title": "Spoofing hotspot",
            "center": st.session_state.get("spoofer"),
            "radius_m": CFG.spoof_radius_m,
            "message": "Mobile assets in the spoofing radius should show elevated position error and navigation drift.",
        }
    if scenario.startswith("Data Tamper"):
        gateways = df_map[df_map["type"].eq("Gateway")].copy()
        if gateways.empty:
            return None
        return {
            "title": "Gateway integrity watch",
            "subset": gateways.sort_values("risk", ascending=False).head(5),
            "message": "Gateway integrity issues typically concentrate on the relay path before spreading into downstream alerts.",
        }
    return None


def _scenario_spotlight(df_map, scenario):
    target = _spotlight_target(df_map, scenario)
    if not target:
        return None

    subset = target.get("subset")
    center = target.get("center")
    radius_m = target.get("radius_m")
    if subset is None and center and radius_m:
        subset = df_map.copy()
        subset["distance_m"] = subset.apply(
            lambda row: haversine_m(row["lat"], row["lon"], center["lat"], center["lon"]),
            axis=1,
        )
        subset = subset[subset["distance_m"] <= radius_m].sort_values(["risk", "distance_m"], ascending=[False, True])

    if subset is None or subset.empty:
        subset = df_map.sort_values("risk", ascending=False).head(5)
        if subset.empty:
            return None

    mean_risk = float(subset["risk"].mean()) if "risk" in subset else 0.0
    top_devices = [
        f"<span class='quick-chip'>{row.device_id} · {row.risk:.2f}</span>"
        for row in subset.head(4).itertuples()
    ]
    return {
        "title": target["title"],
        "message": f"{target['message']} {len(subset)} device(s) are currently in focus with average live risk {mean_risk:.2f}.",
        "devices": top_devices,
    }


def _paced_interval(refresh_interval, minimum_seconds):
    if not refresh_interval:
        return None
    return max(float(refresh_interval), float(minimum_seconds))


def _build_overview_map_df(type_filter):
    latest_probs = st.session_state.get("latest_probs", {})
    if st.session_state.get("model") is None:
        return None

    df_map = st.session_state.devices.copy()
    if type_filter and len(type_filter) < len(DEVICE_TYPES):
        df_map = df_map[df_map["type"].isin(type_filter)].copy()
    df_map["risk"] = df_map["device_id"].map(latest_probs).fillna(0.0)
    return df_map


def render_overview_tab(scenario, show_map, type_filter, use_conformal, role, refresh_interval=None):
    render_tab_intro("Overview", role)
    render_scenario_context(scenario)
    render_section_card(
        "Live operational picture",
        "Use the map, fleet trends, and queue summary together: the left side shows where the pattern is forming, while the right side shows how response is prioritized.",
        kicker="Live posture",
    )

    summary_interval = _paced_interval(refresh_interval, 1.0)
    visual_interval = _paced_interval(refresh_interval, 2.4)

    def _render_overview_status_content():
        current_tick = int(st.session_state.get("tick", 0))
        latest_probs = st.session_state.get("latest_probs", {})
        incident_count = len(st.session_state.get("incidents", []))
        active_alerts = sum(prob >= CFG.threshold for prob in latest_probs.values())
        elevated_risk = sum(prob >= 0.70 for prob in latest_probs.values())
        top_device, top_prob = (max(latest_probs.items(), key=lambda item: item[1]) if latest_probs else ("—", 0.0))

        with st.container(border=True):
            snapshot_cols = st.columns(4)
            snapshot_cols[0].metric("Current tick", current_tick)
            snapshot_cols[1].metric("Devices above threshold", active_alerts)
            snapshot_cols[2].metric("Elevated-risk devices", elevated_risk)
            snapshot_cols[3].metric("Top live risk", f"{top_device} · {top_prob:.2f}" if latest_probs else "Waiting for telemetry")
            st.markdown(
                "<div class='quick-chip-row'>"
                f"<span class='quick-chip'>Scenario: {scenario}</span>"
                f"<span class='quick-chip'>Threshold: {CFG.threshold:.2f}</span>"
                f"<span class='quick-chip'>Conformal: {'On' if use_conformal else 'Off'}</span>"
                f"<span class='quick-chip'>Type filter: {len(type_filter) if type_filter else len(DEVICE_TYPES)} selected</span>"
                "</div>",
                unsafe_allow_html=True,
            )
            if current_tick < CFG.rolling_len:
                st.caption(f"Warm-up in progress: the detector needs about {CFG.rolling_len} ticks before incidents appear.")
            elif incident_count > 0:
                st.caption(f"Session status: {incident_count} incident(s) generated so far.")

    def _render_overview_left_content():
        df_map = _build_overview_map_df(type_filter)
        snapshot = _overview_snapshot(df_map)
        spotlight = _scenario_spotlight(df_map, scenario)

        with st.container(border=True):
            st.caption("Geospatial view")
            st.markdown("#### Fleet map and scenario overlays")
            st.markdown(
                "<div class='quick-chip-row'>"
                f"<span class='quick-chip'>Devices in view: {snapshot['visible_devices']}</span>"
                f"<span class='quick-chip'>Avg visible risk: {snapshot['avg_risk']:.2f}</span>"
                f"<span class='quick-chip'>Above threshold: {snapshot['above_threshold']}</span>"
                "</div>",
                unsafe_allow_html=True,
            )

        render_focus_callout("What to watch", _scenario_watch_text(scenario), variant="info")

        if not show_map:
            render_focus_callout("Map hidden", "Enable the geospatial map in the sidebar to see devices and scenario overlays.")
        elif st.session_state.get("model") is not None and df_map is not None:
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
            label_df = df_map[df_map["risk"] >= CFG.threshold].copy().sort_values(["risk", "device_id"], ascending=[False, True]).head(6)
            if label_df.empty and not df_map.empty:
                label_df = df_map.sort_values(["risk", "device_id"], ascending=[False, True]).head(3).copy()

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
                    data=label_df,
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
            map_cols = st.columns([1.45, 0.85])
            with map_cols[0]:
                st.pydeck_chart(deck, use_container_width=True)
                st.markdown(
                    "<div class='quick-chip-row'>"
                    "<span class='quick-chip'>Blue/Orange/Green/Purple = device type</span>"
                    "<span class='quick-chip'>Red ring = above threshold</span>"
                    "<span class='quick-chip'>Bigger marker = higher live risk</span>"
                    f"<span class='quick-chip'>{_scenario_overlay_label(scenario)}</span>"
                    "</div>",
                    unsafe_allow_html=True,
                )
                st.caption("Only priority devices are labeled to keep the live map readable during demos.")
            with map_cols[1]:
                with st.container(border=True):
                    st.markdown("#### Map readout")
                    readout_cols = st.columns(2)
                    readout_cols[0].metric("Visible devices", snapshot["visible_devices"])
                    readout_cols[1].metric("Avg risk", f"{snapshot['avg_risk']:.2f}" if snapshot["visible_devices"] else "—")
                    readout_cols = st.columns(2)
                    readout_cols[0].metric("Above threshold", snapshot["above_threshold"])
                    readout_cols[1].metric(
                        "Top device",
                        f"{snapshot['top_device']} · {snapshot['top_risk']:.2f}" if snapshot["visible_devices"] else "Waiting",
                    )
                    st.caption("Use this side panel to read the map quickly without hovering over every device.")
                    st.markdown(
                        "<div class='quick-chip-row'>"
                        f"<span class='quick-chip'>Types: {', '.join(type_filter) if type_filter else 'All'}</span>"
                        f"<span class='quick-chip'>Overlay: {scenario}</span>"
                        "</div>",
                        unsafe_allow_html=True,
                    )
                with st.container(border=True):
                    st.markdown("#### Overlay focus")
                    st.caption(_scenario_overlay_label(scenario))
                    if spotlight:
                        st.markdown(
                            "<div class='quick-chip-row'>"
                            + "".join(spotlight.get("devices", [])[:3])
                            + "</div>",
                            unsafe_allow_html=True,
                        )
                        st.caption(spotlight["message"])
                    else:
                        st.caption("No concentrated hotspot is visible yet. Use the map and queue together as the scenario develops.")
        else:
            render_focus_callout("Model setup needed", "Run model setup to unlock the live map, risk overlays, and trend charts.", variant="warning")

        fleet_records = pd.DataFrame(list(st.session_state.fleet_records))
        render_section_card(
            "Fleet trends",
            "These charts compare the recent window with the session baseline so it is easier to explain what changed, not just what is currently high or low.",
            kicker="Trend view",
        )
        if len(fleet_records) > 0:
            trend_cols = ["snr", "packet_loss", "latency_ms", "pos_error_m"]
            fleet_trends = fleet_records.groupby("tick")[trend_cols].mean().reset_index()
            trend_summaries = {
                metric: _trend_window_summary(fleet_trends, metric)
                for metric in trend_cols
            }
            summary_chips = []
            for metric in trend_cols:
                summary = trend_summaries.get(metric)
                if not summary:
                    continue
                direction = "up" if summary["delta"] > 0 else ("down" if summary["delta"] < 0 else "flat")
                summary_chips.append(
                    f"<span class='quick-chip'>{TREND_LABELS.get(metric, metric)}: {summary['status']} ({direction})</span>"
                )
            if summary_chips:
                st.markdown("<div class='quick-chip-row'>" + "".join(summary_chips) + "</div>", unsafe_allow_html=True)
                st.caption("Baseline uses the early part of the session; recent uses the latest window of fleet telemetry.")
            chart_cols = st.columns(2)
            for idx, y_axis in enumerate(["snr", "packet_loss", "latency_ms", "pos_error_m"]):
                title = TREND_LABELS.get(y_axis, y_axis.replace("_", " ").title())
                fig = px.line(fleet_trends, x="tick", y=y_axis, title=title)
                summary = trend_summaries.get(y_axis)
                if summary:
                    fig.add_hline(
                        y=summary["baseline_mean"],
                        line_dash="dash",
                        line_color="rgba(71,85,105,0.55)",
                        annotation_text="baseline",
                        annotation_position="top left",
                    )
                with chart_cols[idx % 2]:
                    with st.container(border=True):
                        if summary:
                            metric_cols = st.columns(3)
                            metric_cols[0].metric("Recent", f"{summary['recent_mean']:.2f}{summary['unit']}")
                            metric_cols[1].metric("Baseline", f"{summary['baseline_mean']:.2f}{summary['unit']}")
                            metric_cols[2].metric("Direction", summary["status"], delta=f"{summary['delta']:+.2f}{summary['unit']}")
                        st.plotly_chart(
                            style_plotly_figure(fig, title=title, height=280),
                            use_container_width=True,
                            config={"displayModeBar": False},
                            key=f"overview_{y_axis}",
                        )
                        if summary:
                            st.caption(
                                f"Recent {title.lower()} is {summary['status'].lower()} versus the session baseline over the last {summary['window_size']} ticks."
                            )
        else:
            st.caption("Telemetry charts will populate once the stream starts collecting fleet samples.")

    def _render_overview_right_content():
        df_map = _build_overview_map_df(type_filter)
        latest_probs = st.session_state.get("latest_probs", {})
        active_alerts = sum(prob >= CFG.threshold for prob in latest_probs.values())
        escalated_count = 0
        suppressed_count = 0

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
            "Response queue",
            "Use this column to see what needs review first, how confidence checks affect the queue, and where human review remains in control.",
            kicker="Response focus",
        )
        render_focus_callout(
            "How queue ranking works",
            "Higher live risk moves a device up the queue. Escalations add priority, and conformal p-values act as confidence checks that show whether the alert looks typical or uncertain.",
            variant="info",
        )
        policy = current_hitl_policy()
        hitl_stats = st.session_state.get("hitl_live_stats", {})

        leaderboard = []
        if st.session_state.get("model") is not None:
            for _, row in st.session_state.devices.iterrows():
                prob = st.session_state.latest_probs.get(row.device_id, 0.0)
                p_value = conformal_pvalue(prob) if use_conformal else None
                severity_label, _ = severity(prob, p_value)
                latest_review = latest_review_for_device(row.device_id, scenario)
                review_status = latest_review.get("status") if latest_review else "Pending Review"
                if review_status == "Escalated":
                    escalated_count += 1
                if review_status == "False Positive":
                    suppressed_count += 1
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
        with st.container(border=True):
            summary_cols = st.columns(3)
            summary_cols[0].metric("Devices to review", active_alerts)
            summary_cols[1].metric("Escalated", escalated_count)
            summary_cols[2].metric("Suppressed history", suppressed_count)
            st.markdown(
                "<div class='quick-chip-row'>"
                f"<span class='quick-chip'>Suppression: {'On' if policy['suppression_enabled'] else 'Off'}</span>"
                f"<span class='quick-chip'>Window: {policy['suppression_ticks']} ticks</span>"
                f"<span class='quick-chip'>Escalation boost: {policy['escalation_boost']:.2f}</span>"
                "</div>",
                unsafe_allow_html=True,
            )
            last_effect = hitl_stats.get("last_effect")
            if last_effect:
                st.caption(
                    f"Latest reviewer effect: {last_effect['effect']} on {last_effect['device_id']} at tick {last_effect['tick']}."
                )
            elif hitl_stats.get("suppressed_alerts") or hitl_stats.get("prioritized_alerts"):
                st.caption("Human review actions are influencing queue order in this session.")
        if leaderboard:
            with st.container(border=True):
                st.markdown("#### Triage queue")
                st.caption("The first rows are the best candidates for human review right now.")
                top_devices = [
                    f"<span class='quick-chip'>{row['device_id']} · {row['severity']} · {row['prob']:.2f}</span>"
                    for row in sorted(leaderboard, key=lambda item: (item["queue_score"], item["prob"]), reverse=True)[:4]
                ]
                if top_devices:
                    st.markdown("<div class='quick-chip-row'>" + "".join(top_devices) + "</div>", unsafe_allow_html=True)
                queue_df, formatters = _queue_dataframe(leaderboard, use_conformal)
                st.dataframe(queue_df.style.format(formatters), width="stretch", hide_index=True)
        else:
            render_focus_callout("No queue yet", "Start playback or run model setup to generate live risk rankings.")

    if summary_interval:
        @st.fragment(run_every=summary_interval)
        def _render_overview_status_fragment():
            _render_overview_status_content()

        _render_overview_status_fragment()
    else:
        _render_overview_status_content()

    left, right = st.columns([2, 1])
    with left:
        if visual_interval:
            @st.fragment(run_every=visual_interval)
            def _render_overview_left_fragment():
                _render_overview_left_content()

            _render_overview_left_fragment()
        else:
            _render_overview_left_content()

    with right:
        if summary_interval:
            @st.fragment(run_every=summary_interval)
            def _render_overview_right_fragment():
                _render_overview_right_content()

            _render_overview_right_fragment()
        else:
            _render_overview_right_content()

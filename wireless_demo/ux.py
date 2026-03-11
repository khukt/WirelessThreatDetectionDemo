import base64
import time
from textwrap import dedent
from typing import Optional

import requests
import streamlit as st


SCENARIO_COPY = {
    "Normal": {
        "summary": "Baseline fleet behavior with normal RF, GNSS, access, and integrity patterns.",
        "signals": "Healthy SNR/SINR, stable latency, low auth churn, low integrity errors.",
        "action": "Use this as the reference view before switching into attack scenarios.",
    },
    "Jamming (localized)": {
        "summary": "Simulates localized wireless interference that degrades connectivity quality.",
        "signals": "Noise floor, PHY/BLER errors, loss, latency, and lower SNR/SINR.",
        "action": "Watch the map radius, then inspect which devices enter elevated risk first.",
    },
    "Access Breach (AP/gNB)": {
        "summary": "Simulates rogue infrastructure or credential abuse targeting association flows.",
        "signals": "Deauth bursts, association churn, retry spikes, DHCP/auth failures, rogue RSSI gap.",
        "action": "Compare affected device types and inspect the incident cards for access-layer evidence.",
    },
    "GPS Spoofing (subset)": {
        "summary": "Simulates location manipulation for a single device, area, or site-wide scope.",
        "signals": "Position error, HDOP anomalies, fewer satellites, clock drift, C/N0 oddities.",
        "action": "Use the map and GNSS plots together to distinguish spatial vs. system-wide anomalies.",
    },
    "Data Tamper (gateway)": {
        "summary": "Simulates payload integrity issues such as replay, drift, or schema corruption.",
        "signals": "Timestamp skew, duplicates, sequence gaps, CRC/HMAC failures, schema violations.",
        "action": "Inspect the incident details to understand whether evidence points to replay, drift, or noise.",
    },
}

TAB_COPY = {
    "Home": {
        "summary": "Start here to understand the demo, choose a scenario, and pick the user journey you want to follow.",
        "focus": "Use the quick actions to select a role, choose a scenario, and decide which part of the demo to explore next.",
        "next": "Move to Overview for live posture, Incidents for triage, or Insights/Governance for explanation and trust.",
    },
    "Overview": {
        "summary": "See the live operational story first: where risk is emerging, how it spreads, and which devices need attention.",
        "focus": "Watch the map, fleet KPIs, and triage queue together to spot the active scenario pattern.",
        "next": "Move to Incidents once a device or region looks suspicious.",
    },
    "Fleet View": {
        "summary": "Compare device behavior side by side to understand whether a problem is isolated or fleet-wide.",
        "focus": "Use the heatmap and device inventory to find which parts of the fleet drift from baseline.",
        "next": "Return to Incidents for device-level review once you identify the affected group.",
    },
    "Incidents": {
        "summary": "Triage suspicious events, review evidence, and apply human oversight actions.",
        "focus": "Filter by severity and review status, then approve, reject, or escalate the most important alerts.",
        "next": "Use Insights to explain why the model behaved this way, or Governance to review oversight artifacts.",
    },
    "Insights": {
        "summary": "Explain how the model works, what drives its decisions, and how confidence is calibrated.",
        "focus": "Review the model transparency card, feature importance, and reliability curve to understand behavior.",
        "next": "Use Governance to connect technical behavior to oversight and policy requirements.",
    },
    "Governance": {
        "summary": "Show the control story: human oversight, audit logs, and alignment with EU Trustworthy AI concepts.",
        "focus": "Review the 7 Pillars status, HITL evidence, and audit trail to assess operational readiness.",
        "next": "Use the roadmap expanders to plan the next improvements.",
    },
}

TAB_DISPLAY_LABELS = {
    "Home": "⌂ Home",
    "Overview": "🛰 Overview",
    "Fleet View": "🚚 Fleet",
    "Incidents": "🚨 Incidents",
    "Insights": "🧠 Insights",
    "Governance": "🛡 Governance",
}

ROLE_TAB_ORDER = {
    "End User": ["Home", "Overview", "Incidents", "Fleet View", "Insights", "Governance"],
    "Domain Expert": ["Home", "Overview", "Incidents", "Insights", "Fleet View", "Governance"],
    "Regulator": ["Home", "Governance", "Insights", "Overview", "Incidents", "Fleet View"],
    "AI Builder": ["Home", "Insights", "Overview", "Incidents", "Governance", "Fleet View"],
    "Executive": ["Home", "Overview", "Governance", "Incidents", "Insights", "Fleet View"],
}

ROLE_FLOW_COPY = {
    "End User": "Recommended path: start with live posture, review incidents, then inspect fleet details if something looks wrong.",
    "Domain Expert": "Recommended path: watch the scenario develop, triage incidents, then use Insights to validate the model's reasoning.",
    "Regulator": "Recommended path: begin with Governance, then review Insights to connect technical behavior to accountability and transparency.",
    "AI Builder": "Recommended path: start with Insights, then verify live behavior in Overview and Incidents, and finish in Governance.",
    "Executive": "Recommended path: start with Overview for the operational picture, then Governance for trust and accountability context.",
}

ROLE_FOCUS_COPY = {
    "End User": {
        "Home": "Use Home to choose a scenario quickly and understand where to go next without reading technical details.",
        "Overview": "Focus on whether operations look normal and which devices need immediate attention.",
        "Fleet View": "Use this when you want to compare devices without diving into model details.",
        "Incidents": "Your main job here is to review alerts and decide which ones matter operationally.",
        "Insights": "Use this only when you need a clearer explanation of why the system raised an alert.",
        "Governance": "This section shows the controls behind the demo but is not the main operational workspace.",
    },
    "Domain Expert": {
        "Home": "Use Home to select a scenario quickly, then move into the analyst flow with the right context.",
        "Overview": "Watch the live operational pattern first, then connect it to RF, GNSS, or integrity behavior.",
        "Fleet View": "Use the fleet comparison to distinguish isolated device anomalies from wider system effects.",
        "Incidents": "This is your core workspace for triage, evidence review, and device-level interpretation.",
        "Insights": "Use this to validate whether model behavior aligns with domain expectations and physical intuition.",
        "Governance": "Review governance after triage to confirm that human oversight and logging are working as intended.",
    },
    "Regulator": {
        "Home": "Use Home to understand the demo at a high level before reviewing governance and transparency evidence.",
        "Overview": "Look here for a high-level picture of what the system is monitoring and how risk is surfaced.",
        "Fleet View": "Use this as supporting evidence rather than the primary place to assess accountability.",
        "Incidents": "Check whether incidents are understandable, reviewable, and subject to human oversight.",
        "Insights": "Use this to understand the model logic, confidence controls, and technical transparency artifacts.",
        "Governance": "This is your primary workspace for the 7 Pillars, auditability, and oversight controls.",
    },
    "AI Builder": {
        "Home": "Use Home to choose the scenario and audience perspective you want to test before validating the workflow.",
        "Overview": "Use this to connect technical model behavior to the live scenario and alert stream.",
        "Fleet View": "Check how telemetry shifts across devices before reasoning about feature engineering quality.",
        "Incidents": "Inspect how model output becomes operator-facing incidents and how human feedback changes behavior.",
        "Insights": "This is your main workspace for model logic, feature importance, calibration, and transparency artifacts.",
        "Governance": "Use this to assess which controls are implemented and where the technical roadmap still has gaps.",
    },
    "Executive": {
        "Home": "Use Home as the landing page for the business story, then decide whether to look at operations, trust, or incidents.",
        "Overview": "Start here to understand the live business story: what changed, where, and how serious it is.",
        "Fleet View": "Use this only if you need extra detail on how broadly the scenario affects the fleet.",
        "Incidents": "Use this to see what actions operators would take and how much human review is involved.",
        "Insights": "This explains the model in simplified terms when you need confidence in how the AI behaves.",
        "Governance": "This is a key section for understanding trust, accountability, and compliance readiness.",
    },
}

ROLE_SIDEBAR_COPY = {
    "End User": {
        "controls": "Keep the setup simple: choose the scenario, start playback, and review incidents that need action.",
        "scenario": "Choose the operational story you want to observe, then use playback to watch it unfold.",
        "model": "Use the default settings unless you need to tighten or relax alert sensitivity.",
        "display": "Keep the map on for spatial awareness and switch roles only when you want a different explanation style.",
        "guidance": "Inline help keeps the demo easy to follow without requiring technical background.",
    },
    "Domain Expert": {
        "controls": "Use the controls to shape the scenario, then validate whether the resulting signal pattern matches domain expectations.",
        "scenario": "Scenario mode lets you stress RF, access, GNSS, or integrity behaviors and compare how they propagate across the fleet.",
        "model": "Tune threshold and conformal settings when you want to inspect sensitivity versus operational plausibility.",
        "display": "Keep both map and heatmap enabled to compare spatial spread with device-level telemetry drift.",
        "guidance": "Inline hints help connect the UI back to operational evidence rather than only model output.",
    },
    "Regulator": {
        "controls": "Use the controls to understand what the operator can change and what remains governed by visible safeguards.",
        "scenario": "Switch scenarios to see how the system explains different risk situations and whether oversight remains visible.",
        "model": "Review model controls as transparency artifacts rather than as operational tuning knobs.",
        "display": "The role selector changes the narrative emphasis so you can review accountability and transparency more directly.",
        "guidance": "Enable help and EU status to keep governance cues visible during the walkthrough.",
    },
    "AI Builder": {
        "controls": "Use the controls to connect scenario generation, playback, model behavior, and reviewer feedback in one loop.",
        "scenario": "Each scenario stresses a different feature family, which helps explain detection and classification behavior.",
        "model": "This is the main place to inspect thresholding, conformal behavior, and refresh the model artifacts.",
        "display": "Use role switching to check how the same system explains itself to different stakeholders.",
        "guidance": "Inline hints are useful for verifying whether the story shown to users matches the underlying technical design.",
    },
    "Executive": {
        "controls": "Keep the walkthrough focused on the business story: what happened, how serious it is, and whether controls are working.",
        "scenario": "Scenario changes let you compare different risk stories without needing to inspect technical details first.",
        "model": "Treat model settings as confidence controls rather than low-level engineering parameters.",
        "display": "Use the role selector to keep the interface focused on leadership-level meaning and trust signals.",
        "guidance": "Inline help and EU status make the demo easier to explain to non-technical stakeholders.",
    },
}

ROLE_METRIC_COPY = {
    "End User": {
        "devices": ("Devices in view", "How many assets are being monitored right now."),
        "incidents": ("Open incidents", "How many alerts are active in this session."),
        "quality": ("Model health", "A simple signal that the detector is behaving reliably."),
        "risk": ("Average fleet risk", "The current fleet-wide alert level."),
        "train": ("Last setup time", "How long the latest model refresh took."),
        "tip": "Start in Overview, then move to Incidents when a device or region looks suspicious.",
    },
    "Domain Expert": {
        "devices": ("Devices monitored", "Fleet scope for the current scenario."),
        "incidents": ("Incident queue", "Alerts available for analyst triage."),
        "quality": ("Detector AUC", "Validation quality of the anomaly model."),
        "risk": ("Mean anomaly prob.", "Average probability of anomalous behavior across the fleet."),
        "train": ("Refresh duration", "Latest model setup time."),
        "tip": "Use Overview to spot the pattern, then Incidents and Insights to validate the diagnosis.",
    },
    "Regulator": {
        "devices": ("Assets observed", "Scope of the monitored system."),
        "incidents": ("Reviewable alerts", "Alerts that can be assessed under human oversight."),
        "quality": ("Model validation", "A technical quality indicator supporting transparency."),
        "risk": ("Current risk level", "Overall risk surfaced by the system."),
        "train": ("Latest model refresh", "When the current model configuration was last rebuilt."),
        "tip": "Start in Governance and Insights if you want accountability context before reviewing live operations.",
    },
    "AI Builder": {
        "devices": ("Fleet entities", "Number of devices contributing telemetry."),
        "incidents": ("Session incidents", "Current outputs emitted by the detection and typing stack."),
        "quality": ("Model AUC", "Validation AUC for the anomaly detector."),
        "risk": ("Fleet risk mean", "Average detector probability across active devices."),
        "train": ("Train duration", "Elapsed time for the latest model setup run."),
        "tip": "Start in Insights, then verify how those model behaviors appear in Overview and Incidents.",
    },
    "Executive": {
        "devices": ("Assets monitored", "How much of the operation is in scope."),
        "incidents": ("Active alerts", "How many situations currently need review."),
        "quality": ("AI confidence signal", "A high-level quality check for the underlying model."),
        "risk": ("Fleet risk level", "The overall operational risk picture right now."),
        "train": ("Last model refresh", "How recently the AI setup was refreshed."),
        "tip": "Start in Overview for the live story, then move to Governance for trust and accountability context.",
    },
}

PROJECT_URL = "https://www.vinnova.se/en/p/trustworthy-ai-and-mobile-generative-ai-for-6g-networks-and-smart-industry-applications/"
PROJECT_REF = "2024-03570"
VINNOVA_LOGO_URL = (
    "https://www.vinnova.se/globalassets/mikrosajter/nyhetsrum/bilder/logotyp/"
    "vinnova_green_payoff_eng_rgb.png"
)
KKS_URL = "https://www.kks.se/"
KKS_LOGO_URL = "https://cdn-assets-cloud.frontify.com/s3/frontify-cloud-files-us/eyJwYXRoIjoiZnJvbnRpZnlcL2FjY291bnRzXC8zYVwvMjMxNjAwXC9wcm9qZWN0c1wvMzI5NjQzXC9hc3NldHNcLzY4XC82NDI3MTMxXC8xMDViMjlhNjRlZTkyNDhmZjljZTFhY2M2MzIyN2JmZi0xNjQ4Nzk2NDM1LnBuZyJ9:frontify:UwA956mBpIj76Iqr95OIrjj07Wb0ztxt1lHlwfBpH8Y"
AURORA_URL = "https://www.miun.se/en/Research/research-projects/ongoing-research-projects/trust---enhancing-wireless-communication--sensing-with-secure-resilient-and-trustworthy-solutions/"
AURORA_LOGO_URL = "https://www.interregaurora.eu/wp-content/uploads/AURORA-RGB-Color-1-1024x308.png"


def render_section_card(title: str, copy: str, kicker: str = "Section"):
    st.markdown(
        dedent(
            f"""
        <div class="transparency-card">
            <div class="transparency-side-kicker">{kicker}</div>
            <div class="transparency-title">{title}</div>
            <div class="transparency-copy">{copy}</div>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )


def style_plotly_figure(fig, title: Optional[str] = None, height: Optional[int] = None, show_legend: bool = False):
    if title is not None:
        fig.update_layout(title=title)
    fig.update_layout(
        height=height or fig.layout.height,
        margin=dict(l=12, r=12, t=52 if title else 18, b=12),
        paper_bgcolor="white",
        plot_bgcolor="white",
        title_font=dict(size=16, color="#0f172a"),
        font=dict(color="#334155"),
    )
    if show_legend:
        fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig.update_xaxes(showgrid=True, gridcolor="rgba(226,232,240,0.65)", zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(226,232,240,0.65)", zeroline=False)
    return fig


@st.cache_data(show_spinner=False, ttl=86400)
def fetch_logo_bytes(url: str) -> Optional[bytes]:
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return response.content


def logo_src(url: str, logo_bytes: Optional[bytes]) -> str:
    if not logo_bytes:
        return url
    lower_url = url.lower()
    if lower_url.endswith(".svg"):
        mime = "image/svg+xml"
    elif lower_url.endswith(".jpg") or lower_url.endswith(".jpeg"):
        mime = "image/jpeg"
    else:
        mime = "image/png"
    encoded = base64.b64encode(logo_bytes).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def inject_global_styles():
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.4rem; padding-bottom: 1.5rem;}
        .demo-hero {
            padding: 1.1rem 1.2rem;
            border: 1px solid rgba(49, 51, 63, 0.12);
            border-radius: 18px;
            background: linear-gradient(135deg, rgba(14, 116, 144, 0.08), rgba(59, 130, 246, 0.04));
            margin-bottom: 0.8rem;
        }
        .demo-hero h2 {margin: 0 0 0.35rem 0; font-size: 1.6rem;}
        .demo-muted {color: rgba(49, 51, 63, 0.75); font-size: 0.95rem;}
        .summary-card {
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: 16px;
            padding: 0.85rem 1rem;
            background: rgba(255,255,255,0.65);
            min-height: 108px;
        }
        .summary-kicker {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: rgba(49, 51, 63, 0.6);
            margin-bottom: 0.3rem;
        }
        .summary-value {font-size: 1.02rem; font-weight: 600; margin-bottom: 0.2rem;}
        .summary-copy {font-size: 0.88rem; color: rgba(49, 51, 63, 0.75);}
        .section-card {
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: 16px;
            padding: 0.9rem 1rem;
            background: rgba(255,255,255,0.70);
            margin-bottom: 0.8rem;
        }
        .incident-card {
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: 18px;
            padding: 0.95rem 1rem;
            background: rgba(255,255,255,0.82);
            margin-bottom: 0.75rem;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
        }
        .incident-header {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            align-items: flex-start;
            margin-bottom: 0.55rem;
        }
        .incident-title {
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 0.15rem;
        }
        .incident-meta {
            color: rgba(49, 51, 63, 0.72);
            font-size: 0.88rem;
        }
        .severity-pill {
            color: white;
            padding: 0.28rem 0.7rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 700;
            white-space: nowrap;
        }
        .metric-strip {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.55rem;
            margin: 0.6rem 0 0.45rem;
        }
        .metric-chip {
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: 14px;
            padding: 0.55rem 0.7rem;
            background: rgba(248,250,252,0.95);
        }
        .metric-chip-label {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: rgba(49, 51, 63, 0.58);
            margin-bottom: 0.15rem;
        }
        .metric-chip-value {
            font-size: 0.98rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.95);
        }
        .reason-list {
            margin: 0.35rem 0 0;
            padding-left: 1.1rem;
            color: rgba(49, 51, 63, 0.85);
            font-size: 0.9rem;
        }
        .inspector-note {
            border-left: 4px solid rgba(14, 116, 144, 0.35);
            padding: 0.7rem 0.9rem;
            background: rgba(14, 116, 144, 0.05);
            border-radius: 12px;
            margin-bottom: 0.8rem;
            color: rgba(30, 41, 59, 0.9);
        }
        .transparency-card {
            border: 1px solid rgba(49, 51, 63, 0.12);
            border-radius: 18px;
            padding: 1rem 1.1rem;
            background: linear-gradient(180deg, rgba(255,255,255,0.90), rgba(248,250,252,0.92));
            margin-bottom: 0.9rem;
        }
        .transparency-title {
            font-size: 1.15rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
            color: rgba(15, 23, 42, 0.98);
        }
        .transparency-copy {
            font-size: 0.92rem;
            color: rgba(49, 51, 63, 0.78);
            margin-bottom: 0.65rem;
        }
        .transparency-side-panel {
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: 18px;
            padding: 1rem 1rem 0.95rem;
            background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(248,250,252,0.94));
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
        }
        .transparency-side-kicker {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 700;
            color: rgba(71, 85, 105, 0.72);
            margin-bottom: 0.18rem;
        }
        .transparency-side-title {
            font-size: 1.04rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.96);
            margin-bottom: 0.2rem;
        }
        .transparency-side-copy {
            font-size: 0.88rem;
            color: rgba(49, 51, 63, 0.76);
            margin-bottom: 0.8rem;
            line-height: 1.45;
        }
        .transparency-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin-bottom: 0.9rem;
        }
        .transparency-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
            padding: 0.33rem 0.58rem;
            border-radius: 999px;
            font-size: 0.77rem;
            font-weight: 600;
            border: 1px solid transparent;
        }
        .transparency-chip-blue {
            color: rgb(29, 78, 216);
            background: rgba(219, 234, 254, 0.8);
            border-color: rgba(96, 165, 250, 0.45);
        }
        .transparency-chip-purple {
            color: rgb(109, 40, 217);
            background: rgba(237, 233, 254, 0.88);
            border-color: rgba(167, 139, 250, 0.45);
        }
        .transparency-chip-amber {
            color: rgb(180, 83, 9);
            background: rgba(254, 243, 199, 0.88);
            border-color: rgba(251, 191, 36, 0.45);
        }
        .transparency-stat-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.65rem;
            margin-bottom: 0.95rem;
        }
        .transparency-stat-card {
            border-radius: 14px;
            padding: 0.72rem 0.8rem;
            border: 1px solid rgba(49, 51, 63, 0.08);
            background: rgba(255,255,255,0.82);
        }
        .transparency-section-label {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 700;
            color: rgba(100, 116, 139, 0.78);
            margin: 0 0 0.45rem;
        }
        .transparency-stat-label {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: rgba(49, 51, 63, 0.58);
            margin-bottom: 0.2rem;
        }
        .transparency-stat-value {
            font-size: 1.35rem;
            line-height: 1.1;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.96);
        }
        .transparency-stage-stack {
            display: grid;
            gap: 0.6rem;
        }
        .transparency-stage-card {
            border-radius: 14px;
            padding: 0.75rem 0.82rem;
            border: 1px solid rgba(49, 51, 63, 0.08);
            background: rgba(255,255,255,0.84);
            border-left-width: 4px;
        }
        .transparency-stage-kicker {
            font-size: 0.71rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 0.18rem;
            font-weight: 700;
        }
        .transparency-stage-title {
            font-size: 0.93rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.96);
            margin-bottom: 0.18rem;
        }
        .transparency-stage-copy {
            font-size: 0.83rem;
            color: rgba(49, 51, 63, 0.78);
            line-height: 1.4;
        }
        .transparency-stage-red { border-left-color: rgba(239, 68, 68, 0.72); }
        .transparency-stage-purple { border-left-color: rgba(168, 85, 247, 0.72); }
        .transparency-stage-amber { border-left-color: rgba(245, 158, 11, 0.72); }
        .transparency-stage-red .transparency-stage-kicker { color: rgb(220, 38, 38); }
        .transparency-stage-purple .transparency-stage-kicker { color: rgb(124, 58, 237); }
        .transparency-stage-amber .transparency-stage-kicker { color: rgb(217, 119, 6); }
        .transparency-footnote {
            margin-top: 0.8rem;
            font-size: 0.8rem;
            color: rgba(71, 85, 105, 0.86);
            line-height: 1.45;
            border-top: 1px solid rgba(226, 232, 240, 0.95);
            padding-top: 0.7rem;
        }
        .transparency-figure-note {
            margin-top: 0.35rem;
            padding: 0.45rem 0.65rem;
            border-radius: 12px;
            background: rgba(248, 250, 252, 0.92);
            border: 1px solid rgba(226, 232, 240, 0.95);
            color: rgba(71, 85, 105, 0.86);
            font-size: 0.8rem;
        }
        .journey-card {
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: 16px;
            padding: 0.7rem 0.8rem;
            background: rgba(255,255,255,0.84);
            min-height: 122px;
        }
        .journey-step {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: rgba(49, 51, 63, 0.58);
            margin-bottom: 0.25rem;
        }
        .journey-title {
            font-size: 1rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.98);
            margin-bottom: 0.2rem;
        }
        .journey-status {
            display: inline-block;
            padding: 0.18rem 0.55rem;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 700;
            margin-bottom: 0.45rem;
        }
        .journey-copy {
            font-size: 0.88rem;
            color: rgba(49, 51, 63, 0.78);
        }
        .tab-intro {
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: 16px;
            padding: 0.9rem 1rem;
            background: rgba(255,255,255,0.78);
            margin-bottom: 0.8rem;
        }
        .tab-intro-title {
            font-size: 1rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.98);
            margin-bottom: 0.2rem;
        }
        .tab-intro-copy {
            font-size: 0.9rem;
            color: rgba(49, 51, 63, 0.78);
            margin-bottom: 0.25rem;
        }
        .pillar-card {
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: 16px;
            padding: 0.95rem 1rem;
            background: rgba(255,255,255,0.82);
            margin-bottom: 0.75rem;
        }
        .pillar-title {
            font-size: 1rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.98);
            margin-bottom: 0.2rem;
        }
        .pillar-status {
            display: inline-block;
            padding: 0.18rem 0.55rem;
            border-radius: 999px;
            font-size: 0.74rem;
            font-weight: 700;
            margin-bottom: 0.45rem;
        }
        .pillar-copy {
            font-size: 0.89rem;
            color: rgba(49, 51, 63, 0.78);
            margin-bottom: 0.35rem;
        }
        .home-hero {
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: 22px;
            padding: 0.95rem 1rem;
            background: linear-gradient(180deg, rgba(255,255,255,0.92), rgba(239,246,255,0.88));
            margin-bottom: 0.65rem;
        }
        .home-hero-title {
            font-size: 1.28rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.98);
            margin-bottom: 0.25rem;
        }
        .home-hero-copy {
            font-size: 0.94rem;
            color: rgba(49, 51, 63, 0.78);
        }
        .home-card {
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: 22px;
            padding: 0.8rem 0.85rem 0.7rem;
            background: rgba(255,255,255,0.90);
            min-height: 136px;
            margin-bottom: 0.55rem;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
        }
        .home-card-icon {
            font-size: 1.6rem;
            margin-bottom: 0.35rem;
        }
        .home-card-title {
            font-size: 1rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.98);
            margin-bottom: 0.18rem;
        }
        .home-card-copy {
            font-size: 0.88rem;
            color: rgba(49, 51, 63, 0.76);
            margin-bottom: 0.55rem;
        }
        .home-chip {
            display: inline-block;
            padding: 0.18rem 0.55rem;
            border-radius: 999px;
            background: rgba(37, 99, 235, 0.08);
            color: #1d4ed8;
            font-size: 0.76rem;
            font-weight: 700;
        }
        .home-icon-tile {
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: 24px;
            padding: 0.75rem 0.72rem 0.65rem;
            background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(248,250,252,0.92));
            box-shadow: 0 12px 26px rgba(15, 23, 42, 0.05);
            text-align: center;
            min-height: 156px;
            margin-bottom: 0.4rem;
        }
        .home-icon-badge {
            width: 56px;
            height: 56px;
            margin: 0 auto 0.45rem;
            border-radius: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.55rem;
            background: linear-gradient(180deg, rgba(37, 99, 235, 0.16), rgba(14, 165, 233, 0.12));
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.6), 0 8px 18px rgba(37, 99, 235, 0.12);
        }
        .home-icon-label {
            font-size: 0.96rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.98);
            margin-bottom: 0.24rem;
        }
        .home-icon-copy {
            font-size: 0.79rem;
            line-height: 1.35;
            color: rgba(49, 51, 63, 0.74);
            min-height: 40px;
        }
        .home-icon-caption {
            display: inline-block;
            margin-top: 0.28rem;
            padding: 0.16rem 0.48rem;
            border-radius: 999px;
            background: rgba(15, 23, 42, 0.06);
            color: rgba(51, 65, 85, 0.9);
            font-size: 0.72rem;
            font-weight: 600;
        }
        .home-section-note {
            color: rgba(49, 51, 63, 0.74);
            font-size: 0.84rem;
            margin-bottom: 0.3rem;
        }
        .home-compact-grid {
            margin-top: 0.25rem;
        }
        section[data-testid="stSidebar"] .stExpander {
            border: 1px solid rgba(49, 51, 63, 0.08);
            border-radius: 18px;
            background: rgba(255,255,255,0.72);
            box-shadow: 0 8px 20px rgba(15, 23, 42, 0.04);
            overflow: hidden;
            margin-bottom: 0.6rem;
        }
        section[data-testid="stSidebar"] .stExpander details summary {
            background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(248,250,252,0.92));
            border-radius: 18px;
            padding-top: 0.2rem;
            padding-bottom: 0.2rem;
        }
        .sidebar-card {
            border: 1px solid rgba(49, 51, 63, 0.08);
            border-radius: 18px;
            padding: 0.9rem 0.95rem;
            background: linear-gradient(180deg, rgba(255,255,255,0.94), rgba(248,250,252,0.9));
            box-shadow: 0 8px 20px rgba(15, 23, 42, 0.04);
            margin-bottom: 0.75rem;
        }
        .sidebar-card-title {
            font-size: 0.98rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.98);
            margin-bottom: 0.2rem;
        }
        .sidebar-card-copy {
            font-size: 0.84rem;
            line-height: 1.35;
            color: rgba(49, 51, 63, 0.74);
        }
        .sidebar-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
            margin-top: 0.55rem;
        }
        .sidebar-chip {
            display: inline-block;
            padding: 0.16rem 0.48rem;
            border-radius: 999px;
            background: rgba(37, 99, 235, 0.08);
            color: #1d4ed8;
            font-size: 0.72rem;
            font-weight: 700;
        }
        .sidebar-status-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            margin-top: 0.4rem;
            padding: 0.2rem 0.55rem;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 700;
            border: 1px solid transparent;
        }
        .sidebar-status-pill--ready {
            background: rgba(22, 163, 74, 0.10);
            color: #15803d;
            border-color: rgba(22, 163, 74, 0.18);
        }
        .sidebar-status-pill--fresh {
            background: rgba(37, 99, 235, 0.10);
            color: #1d4ed8;
            border-color: rgba(37, 99, 235, 0.18);
        }
        .sidebar-status-pill--idle {
            background: rgba(71, 85, 105, 0.10);
            color: #475569;
            border-color: rgba(71, 85, 105, 0.18);
        }
        .fundingWrap {
            text-align: center;
            margin: 1.2rem 0 0.75rem;
        }
        .fundingTitle {
            font-size: 1.05rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.98);
            margin-bottom: 0.35rem;
        }
        .fundingText {
            font-size: 0.92rem;
            color: rgba(49, 51, 63, 0.78);
            line-height: 1.5;
        }
        .fundingGrid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.9rem;
            margin: 0.8rem 0 1.1rem;
        }
        .fundingItem {
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: 18px;
            padding: 0.9rem 0.8rem;
            background: rgba(255,255,255,0.78);
            text-align: center;
        }
        .fundingLogoSlot {
            min-height: 88px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .fundingLogo {
            max-width: 100%;
            max-height: 56px;
            object-fit: contain;
        }
        .fundingLogo.aurora {
            max-height: 48px;
        }
        .fundingLink a {
            color: #1d4ed8;
            font-weight: 600;
            text-decoration: none;
        }
        .fundingLink a:hover {
            text-decoration: underline;
        }
        .footerline {
            margin: 1rem 0 0.4rem;
            padding-top: 0.9rem;
            border-top: 1px solid rgba(49, 51, 63, 0.10);
            text-align: center;
            font-size: 0.88rem;
            color: rgba(49, 51, 63, 0.72);
        }
        @media (max-width: 900px) {
            .fundingGrid {
                grid-template-columns: 1fr;
            }
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.35rem;
            background: rgba(15, 23, 42, 0.05);
            border: 1px solid rgba(49, 51, 63, 0.08);
            border-radius: 999px;
            padding: 0.28rem;
            width: fit-content;
            box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.05);
            margin-bottom: 0.35rem;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 999px;
            padding: 0.48rem 0.95rem;
            background: transparent;
            min-height: 42px;
            transition: all 0.18s ease;
        }
        .stTabs [data-baseweb="tab"] p {
            font-size: 0.9rem;
            font-weight: 600;
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,250,252,0.96));
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08), 0 6px 16px rgba(15, 23, 42, 0.06);
        }
        .stTabs [aria-selected="false"] {
            opacity: 0.82;
        }
        .stTabs [aria-selected="false"]:hover {
            background: rgba(255,255,255,0.56);
            opacity: 1;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(profile: str, scenario: str, role: str):
    scenario_copy = SCENARIO_COPY.get(scenario, SCENARIO_COPY["Normal"])
    st.markdown(
        f"""
        <div class="demo-hero">
            <h2>TRUST AI — Wireless Threat Detection Demo</h2>
            <div class="demo-muted">
                Interactive wireless + logistics security monitoring with transparent anomaly detection,
                attack typing, calibrated confidence, and governance views.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col1, col2, col3, col4 = st.columns(4)
    cards = [
        ("Profile", profile, "Communication mode driving the simulated RF and cellular conditions."),
        ("Scenario", scenario, scenario_copy["summary"]),
        ("Viewer Role", role, "Explanation depth and guidance are adapted to this audience."),
        ("Next Best Action", "Inspect Overview", scenario_copy["action"]),
    ]
    for col, (kicker, value, copy) in zip((col1, col2, col3, col4), cards):
        col.markdown(
            f"""
            <div class="summary-card">
                <div class="summary-kicker">{kicker}</div>
                <div class="summary-value">{value}</div>
                <div class="summary-copy">{copy}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_quickstart(help_mode: bool, show_eu_status: bool, scenario: str):
    if help_mode:
        scenario_copy = SCENARIO_COPY.get(scenario, SCENARIO_COPY["Normal"])
        with st.expander("Quick start guide", expanded=True):
            st.markdown(
                "1. Pick a **Scenario** in the sidebar.  \n"
                "2. Watch the **Overview** map and KPI strip for changes.  \n"
                "3. Open **Incidents** to triage devices and inspect explanations.  \n"
                "4. Use **Insights** for model behavior and **Governance** for transparency artifacts."
            )
            st.caption(f"Scenario focus: {scenario_copy['signals']}")
    if show_eu_status:
        st.success(
            "EU AI Act status: **Limited/Minimal risk demo** (synthetic telemetry; no safety control loop). "
            "If integrated as a **safety component** or for **critical infrastructure control**, it may become **High-risk** with additional obligations."
        )


def render_demo_storyline(model_ready: bool, incident_count: int, scenario: str):
    steps = [
        ("Step 1", "Set up models", "Complete" if model_ready else "Active", "Prepare the anomaly detector and attack-type model so the demo can generate evidence."),
        ("Step 2", "Watch live posture", "Complete" if model_ready and incident_count > 0 else ("Active" if model_ready else "Up next"), f"Observe how the {scenario} scenario changes fleet risk and coverage."),
        ("Step 3", "Triage incidents", "Active" if incident_count > 0 else "Up next", "Review suspicious devices, apply oversight, and prioritize what matters most."),
        ("Step 4", "Explain AI decisions", "Up next", "Use Insights to understand the model, feature impact, and confidence calibration."),
        ("Step 5", "Review governance", "Up next", "Use Governance to connect the demo to oversight, accountability, and EU Trustworthy AI pillars."),
    ]
    status_style = {
        "Complete": "background: rgba(22, 163, 74, 0.14); color: #166534;",
        "Active": "background: rgba(37, 99, 235, 0.14); color: #1d4ed8;",
        "Up next": "background: rgba(148, 163, 184, 0.18); color: #475569;",
    }
    st.markdown("### Demo journey")
    cols = st.columns(len(steps))
    for col, (step, title, status, copy) in zip(cols, steps):
        col.markdown(
            f"""
            <div class="journey-card">
                <div class="journey-step">{step}</div>
                <div class="journey-title">{title}</div>
                <div class="journey-status" style="{status_style[status]}">{status}</div>
                <div class="journey-copy">{copy}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_tab_intro(tab_name: str, role: Optional[str] = None):
    copy = TAB_COPY[tab_name]
    role_copy = None
    if role is not None:
        role_copy = ROLE_FOCUS_COPY.get(role, {}).get(tab_name)
    st.markdown(
        f"""
        <div class="tab-intro">
            <div class="tab-intro-title">{tab_name}</div>
            <div class="tab-intro-copy"><strong>Purpose:</strong> {copy['summary']}</div>
            <div class="tab-intro-copy"><strong>What to look for:</strong> {copy['focus']}</div>
            <div class="tab-intro-copy"><strong>Recommended next step:</strong> {copy['next']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if role_copy:
        st.caption(f"For {role}: {role_copy}")


def render_role_flow_hint(role: str):
    st.caption(ROLE_FLOW_COPY.get(role, ROLE_FLOW_COPY["End User"]))


def sidebar_role_copy(role: str) -> dict:
    return ROLE_SIDEBAR_COPY.get(role, ROLE_SIDEBAR_COPY["End User"])


def metric_role_copy(role: str) -> dict:
    return ROLE_METRIC_COPY.get(role, ROLE_METRIC_COPY["End User"])


def render_model_status_card(compact: bool = False):
    source = st.session_state.get("model_artifact_source")
    trained_at = st.session_state.get("artifact_trained_at")
    metrics = st.session_state.get("metrics") or {}
    threshold = st.session_state.get("suggested_threshold")

    if st.session_state.get("model") is None:
        st.warning("Model status: not trained yet.")
        return

    trained_text = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(trained_at)) if trained_at else "Unknown"
    source_text = source or "Current session"
    quality_text = f"AUC {metrics.get('auc', 0.0):.2f} · F1 {metrics.get('f1', 0.0):.2f}"
    threshold_text = f"Threshold {threshold:.2f}" if threshold is not None else "Threshold —"

    if compact:
        st.caption(f"Model: {source_text} · trained {trained_text} · {quality_text} · {threshold_text}")
        return

    st.markdown(
        f"""
        <div class="section-card">
            <div class="summary-kicker">Model status</div>
            <div class="summary-value">{source_text}</div>
            <div class="summary-copy"><strong>Trained at:</strong> {trained_text}</div>
            <div class="summary-copy" style="margin-top:0.35rem;"><strong>Quality:</strong> {quality_text}</div>
            <div class="summary-copy" style="margin-top:0.35rem;"><strong>Decision threshold:</strong> {threshold_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_summary_card(profile: str, scenario: str, role: str):
    scenario_copy = SCENARIO_COPY.get(scenario, SCENARIO_COPY["Normal"])
    model = st.session_state.get("model")
    source = st.session_state.get("model_artifact_source") or "Not trained"
    status_variant = "idle"
    if source in {"Bundled startup cache", "Writable disk cache", "Disk cache"}:
        status_variant = "ready"
    elif source in {"Fresh training", "Memory cache", "Current session"}:
        status_variant = "fresh"
    source_text = source if model is not None else "Setup required"
    st.markdown(
        f"""
        <div class="sidebar-card">
            <div class="sidebar-card-title">✨ Demo Navigator</div>
            <div class="sidebar-card-copy">Use the icon sections below to pick a scenario, adjust playback, and switch the explanation style for {role}.</div>
            <div class="sidebar-chip-row">
                <span class="sidebar-chip">{profile.split(' ')[0]}</span>
                <span class="sidebar-chip">{scenario}</span>
                <span class="sidebar-chip">{role}</span>
            </div>
            <div class="sidebar-card-copy" style="margin-top:0.55rem;"><strong>Current focus:</strong> {scenario_copy['signals']}</div>
            <div class="sidebar-card-copy" style="margin-top:0.35rem;"><strong>Model:</strong></div>
            <div class="sidebar-status-pill sidebar-status-pill--{status_variant}">{source_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_funding_acknowledgement():
        vinnova_logo_bytes: Optional[bytes] = None
        try:
                vinnova_logo_bytes = fetch_logo_bytes(VINNOVA_LOGO_URL)
        except Exception:
                vinnova_logo_bytes = None

        kks_logo_bytes: Optional[bytes] = None
        try:
                kks_logo_bytes = fetch_logo_bytes(KKS_LOGO_URL)
        except Exception:
                kks_logo_bytes = None

        aurora_logo_bytes: Optional[bytes] = None
        try:
                aurora_logo_bytes = fetch_logo_bytes(AURORA_LOGO_URL)
        except Exception:
                aurora_logo_bytes = None

        vinnova_logo_src = logo_src(VINNOVA_LOGO_URL, vinnova_logo_bytes)
        kks_logo_src = logo_src(KKS_LOGO_URL, kks_logo_bytes)
        aurora_logo_src = logo_src(AURORA_LOGO_URL, aurora_logo_bytes)

        st.markdown(
                f"""
                <div class="fundingWrap">
                    <div class="fundingTitle">Funding acknowledgement</div>
                    <div class="fundingText">
                        This demo hub is supported by <b>VINNOVA</b> (Sweden's Innovation Agency),
                        Project reference: <b>{PROJECT_REF}</b>, by <b>KK-stiftelsen</b> (The Knowledge Foundation),
                        and by <b>Interreg Aurora</b>.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
        )
        st.markdown(
                f"""
                <div class="fundingGrid">
                    <div class="fundingItem">
                        <div class="fundingLogoSlot">
                            <img class="fundingLogo vinnova" src="{vinnova_logo_src}" alt="VINNOVA logo" />
                        </div>
                        <div class="fundingText fundingLink" style="margin-top:8px;">
                            <a href="{PROJECT_URL}" target="_blank">View VINNOVA project page →</a>
                        </div>
                    </div>

                    <div class="fundingItem">
                        <div class="fundingLogoSlot">
                            <img class="fundingLogo kks" src="{kks_logo_src}" alt="KKS logo" />
                        </div>
                        <div class="fundingText fundingLink" style="margin-top:8px;">
                            <a href="{KKS_URL}" target="_blank">View KKS website →</a>
                        </div>
                    </div>

                    <div class="fundingItem">
                        <div class="fundingLogoSlot">
                            <img class="fundingLogo aurora" src="{aurora_logo_src}" alt="Interreg Aurora logo" />
                        </div>
                        <div class="fundingText fundingLink" style="margin-top:8px;">
                            <a href="{AURORA_URL}" target="_blank">View Interreg Aurora project →</a>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
        )


def render_footerline():
        st.markdown(
                """
                <div class="footerline">
                    Trustworthy AI Demo Hub — Developed and maintained by Kyi Thar • Contact: kyi.thar@miun.se
                </div>
                """,
                unsafe_allow_html=True,
        )


def render_scenario_context(scenario: str):
    scenario_copy = SCENARIO_COPY.get(scenario, SCENARIO_COPY["Normal"])
    st.markdown(
        f"""
        <div class="section-card">
            <div class="summary-kicker">Scenario context</div>
            <div class="summary-value">{scenario}</div>
            <div class="summary-copy"><strong>Watch for:</strong> {scenario_copy['signals']}</div>
            <div class="summary-copy" style="margin-top:0.35rem;"><strong>Suggested action:</strong> {scenario_copy['action']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

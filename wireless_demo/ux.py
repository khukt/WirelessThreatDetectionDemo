import base64
import time
from textwrap import dedent
from typing import Optional

import requests
import streamlit as st


ICON_BADGES = {
    "home": ("HM", "rgba(51, 65, 85, 0.05)", "rgba(51, 65, 85, 0.10)", "#475569"),
    "overview": ("OP", "rgba(51, 65, 85, 0.05)", "rgba(51, 65, 85, 0.10)", "#475569"),
    "fleet": ("FL", "rgba(100, 116, 139, 0.05)", "rgba(100, 116, 139, 0.10)", "#475569"),
    "incidents": ("IR", "rgba(127, 29, 29, 0.05)", "rgba(127, 29, 29, 0.10)", "#7f1d1d"),
    "insights": ("AI", "rgba(51, 65, 85, 0.05)", "rgba(51, 65, 85, 0.10)", "#475569"),
    "governance": ("GV", "rgba(51, 65, 85, 0.05)", "rgba(51, 65, 85, 0.10)", "#475569"),
    "normal": ("OK", "rgba(21, 128, 61, 0.05)", "rgba(21, 128, 61, 0.10)", "#166534"),
    "jamming": ("RF", "rgba(51, 65, 85, 0.05)", "rgba(51, 65, 85, 0.10)", "#475569"),
    "breach": ("AC", "rgba(51, 65, 85, 0.05)", "rgba(51, 65, 85, 0.10)", "#475569"),
    "spoofing": ("GN", "rgba(51, 65, 85, 0.05)", "rgba(51, 65, 85, 0.10)", "#475569"),
    "tamper": ("DT", "rgba(51, 65, 85, 0.05)", "rgba(51, 65, 85, 0.10)", "#475569"),
    "end_user": ("EU", "rgba(51, 65, 85, 0.05)", "rgba(51, 65, 85, 0.10)", "#475569"),
    "domain_expert": ("DE", "rgba(51, 65, 85, 0.05)", "rgba(51, 65, 85, 0.10)", "#475569"),
    "regulator": ("RG", "rgba(51, 65, 85, 0.05)", "rgba(51, 65, 85, 0.10)", "#475569"),
    "ai_builder": ("ML", "rgba(51, 65, 85, 0.05)", "rgba(51, 65, 85, 0.10)", "#475569"),
    "executive": ("EX", "rgba(51, 65, 85, 0.05)", "rgba(51, 65, 85, 0.10)", "#475569"),
    "step_1": ("1", "rgba(51, 65, 85, 0.05)", "rgba(51, 65, 85, 0.10)", "#475569"),
    "step_2": ("2", "rgba(51, 65, 85, 0.05)", "rgba(51, 65, 85, 0.10)", "#475569"),
    "step_3": ("3", "rgba(51, 65, 85, 0.05)", "rgba(51, 65, 85, 0.10)", "#475569"),
    "scenario": ("SC", "rgba(71, 85, 105, 0.05)", "rgba(71, 85, 105, 0.10)", "#475569"),
    "setup": ("UP", "rgba(51, 65, 85, 0.05)", "rgba(51, 65, 85, 0.10)", "#475569"),
    "navigator": ("UI", "rgba(15, 23, 42, 0.04)", "rgba(15, 23, 42, 0.08)", "#334155"),
    "notice": ("NT", "rgba(146, 64, 14, 0.05)", "rgba(146, 64, 14, 0.10)", "#92400e"),
    "cache": ("CH", "rgba(30, 64, 175, 0.05)", "rgba(30, 64, 175, 0.10)", "#1e40af"),
    "ready": ("OK", "rgba(21, 128, 61, 0.05)", "rgba(21, 128, 61, 0.10)", "#166534"),
}

ICON_SVG_PATHS = {
    "home": "<path d='M3 10.5 12 3l9 7.5'/><path d='M5.5 9.5V21h13V9.5'/>",
    "overview": "<path d='M4 12a8 8 0 0 1 16 0'/><path d='M7 12a5 5 0 0 1 10 0'/><path d='M12 12l4-4'/><circle cx='12' cy='12' r='1.2' fill='currentColor' stroke='none'/>",
    "fleet": "<rect x='3' y='7' width='11' height='8' rx='1.5'/><path d='M14 9h3l3 3v3h-6Z'/><circle cx='8' cy='17' r='1.5'/><circle cx='17' cy='17' r='1.5'/>",
    "incidents": "<path d='M12 4 21 20H3Z'/><path d='M12 9v5'/><circle cx='12' cy='17' r='1' fill='currentColor' stroke='none'/>",
    "insights": "<path d='M5 17 10 12l3 3 6-7'/><path d='M5 5v14h14'/>",
    "governance": "<path d='M12 3 19 6v6c0 4.5-2.8 7.4-7 9-4.2-1.6-7-4.5-7-9V6l7-3Z'/><path d='m9.5 12 1.7 1.7L15 10' />",
    "normal": "<circle cx='12' cy='12' r='8'/><path d='m8.5 12 2.2 2.2L15.8 9' />",
    "jamming": "<path d='M12 5v6'/><path d='M8 8a6 6 0 0 1 8 0'/><path d='M5 5a10 10 0 0 1 14 0'/><path d='m4 20 16-16' />",
    "breach": "<rect x='5' y='11' width='14' height='9' rx='2'/><path d='M9 11V8a3 3 0 0 1 5.5-1.8'/><path d='M15 8h3' />",
    "spoofing": "<circle cx='12' cy='12' r='7'/><path d='M12 5v2.5M12 16.5V19M5 12h2.5M16.5 12H19'/><circle cx='12' cy='12' r='1.6' fill='currentColor' stroke='none'/>",
    "tamper": "<path d='M8 3h6l4 4v14H8Z'/><path d='M14 3v4h4'/><path d='M10 12h6M10 16h4'/>",
    "end_user": "<circle cx='12' cy='8' r='3'/><path d='M6 19c1.5-3 4-4.5 6-4.5s4.5 1.5 6 4.5'/>",
    "domain_expert": "<circle cx='10' cy='10' r='4'/><path d='m13 13 5 5'/><path d='M8.5 10h3M10 8.5v3'/>",
    "regulator": "<path d='M12 5v14'/><path d='M7 8h10'/><path d='m8.5 8-2.5 4h5ZM18.5 8 16 12h5Z'/>",
    "ai_builder": "<rect x='7' y='7' width='10' height='10' rx='2'/><path d='M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3'/>",
    "executive": "<path d='M5 19V9M10 19V5M15 19v-7M20 19v-11'/>",
    "step_1": "<path d='M10 7h2v10'/><path d='M8 17h6'/>",
    "step_2": "<path d='M8.5 9a3.5 3.5 0 0 1 7 0c0 2.5-2.5 3.4-4.5 5.5h4.5'/><path d='M8 17h8'/>",
    "step_3": "<path d='M9 8.5c.6-.8 1.6-1.5 3-1.5 2 0 3.5 1.1 3.5 2.9 0 1.4-.8 2.1-2 2.6 1.5.4 2.5 1.3 2.5 2.9 0 2.1-1.8 3.6-4.2 3.6-1.9 0-3.2-.7-4-1.9'/>",
    "scenario": "<path d='M4 18h16'/><path d='M7 15 11 11l3 2 5-6'/>",
    "setup": "<circle cx='12' cy='12' r='3'/><path d='M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1'/>",
    "navigator": "<path d='M4 5h16v14H4Z'/><path d='M8 9h8M8 13h8M8 17h5'/>",
    "notice": "<circle cx='12' cy='12' r='8'/><path d='M12 8v5'/><circle cx='12' cy='16.5' r='1' fill='currentColor' stroke='none'/>",
    "cache": "<ellipse cx='12' cy='6.5' rx='6.5' ry='2.5'/><path d='M5.5 6.5v7c0 1.4 2.9 2.5 6.5 2.5s6.5-1.1 6.5-2.5v-7'/><path d='M5.5 10c0 1.4 2.9 2.5 6.5 2.5s6.5-1.1 6.5-2.5'/>",
    "ready": "<circle cx='12' cy='12' r='8'/><path d='m8.5 12 2.2 2.2L15.8 9' />",
}


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
    "Home": "Home",
    "Overview": "Overview",
    "Fleet View": "Fleet",
    "Incidents": "Incidents",
    "Insights": "Insights",
    "Governance": "Governance",
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
    response = requests.get(
        url,
        timeout=5,
        headers={"User-Agent": "TRUST-AI-Demo/1.0"},
    )
    response.raise_for_status()
    return response.content


def inject_global_styles():
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.0rem; padding-bottom: 1.2rem;}
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
        .pro-icon-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 14px;
            font-weight: 800;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            border: 1px solid transparent;
            box-sizing: border-box;
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.55);
        }
        .pro-icon-badge svg {
            width: 16px;
            height: 16px;
            stroke: currentColor;
            fill: none;
            stroke-width: 1.85;
            stroke-linecap: round;
            stroke-linejoin: round;
            flex: 0 0 auto;
        }
        .pro-icon-badge--sm {
            min-width: 28px;
            height: 28px;
            padding: 0 0.45rem;
            font-size: 0.68rem;
        }
        .pro-icon-badge--sm svg {
            width: 14px;
            height: 14px;
        }
        .pro-icon-badge--md {
            min-width: 34px;
            height: 34px;
            padding: 0 0.55rem;
            font-size: 0.7rem;
        }
        .pro-icon-badge--md svg {
            width: 16px;
            height: 16px;
        }
        .pro-icon-badge--lg {
            min-width: 42px;
            height: 42px;
            padding: 0 0.7rem;
            font-size: 0.78rem;
            border-radius: 16px;
        }
        .pro-icon-badge--lg svg {
            width: 18px;
            height: 18px;
        }
        .inline-icon-heading {
            display: flex;
            align-items: center;
            gap: 0.55rem;
            margin-bottom: 0.35rem;
        }
        .inline-icon-heading-title {
            font-size: 1.05rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.98);
        }
        .app-disclaimer {
            display: flex;
            align-items: flex-start;
            gap: 0.7rem;
            padding: 0.8rem 0.9rem;
            border-radius: 18px;
            border: 1px solid rgba(245, 158, 11, 0.20);
            background: linear-gradient(180deg, rgba(255,251,235,0.96), rgba(255,255,255,0.94));
            box-shadow: 0 8px 18px rgba(15, 23, 42, 0.03);
            margin-bottom: 0.75rem;
        }
        .app-disclaimer-icon {
            font-size: 1.1rem;
            line-height: 1;
            margin-top: 0.05rem;
        }
        .app-disclaimer-title {
            font-size: 0.92rem;
            font-weight: 700;
            color: rgba(146, 64, 14, 0.98);
            margin-bottom: 0.12rem;
        }
        .app-disclaimer-copy {
            font-size: 0.84rem;
            line-height: 1.45;
            color: rgba(120, 53, 15, 0.88);
        }
        .onboarding-panel {
            padding: 0.95rem 1rem;
            border-radius: 20px;
            border: 1px solid rgba(49, 51, 63, 0.10);
            background: linear-gradient(180deg, rgba(255,255,255,0.97), rgba(248,250,252,0.94));
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
            margin-bottom: 0.8rem;
        }
        .onboarding-panel--info {
            border-color: rgba(59, 130, 246, 0.18);
            background: linear-gradient(180deg, rgba(239,246,255,0.95), rgba(255,255,255,0.96));
        }
        .onboarding-panel--warning {
            border-color: rgba(245, 158, 11, 0.20);
            background: linear-gradient(180deg, rgba(255,251,235,0.96), rgba(255,255,255,0.96));
        }
        .onboarding-panel-kicker {
            display: inline-block;
            padding: 0.16rem 0.48rem;
            border-radius: 999px;
            font-size: 0.73rem;
            font-weight: 700;
            margin-bottom: 0.4rem;
            background: rgba(15, 23, 42, 0.06);
            color: rgba(51, 65, 85, 0.9);
        }
        .onboarding-panel-title {
            font-size: 1.08rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.98);
            margin-bottom: 0.2rem;
        }
        .onboarding-panel-copy {
            font-size: 0.9rem;
            line-height: 1.48;
            color: rgba(49, 51, 63, 0.78);
            margin-bottom: 0.55rem;
        }
        .onboarding-panel-list {
            margin: 0;
            padding-left: 1.1rem;
            color: rgba(49, 51, 63, 0.82);
            font-size: 0.88rem;
            line-height: 1.55;
        }
        .onboarding-fullscreen-shell {
            padding: 0.35rem 0 0.2rem 0;
            margin: 0 auto 0.25rem auto;
        }
        .onboarding-fullscreen-kicker {
            display: inline-block;
            padding: 0.18rem 0.55rem;
            border-radius: 999px;
            background: rgba(37, 99, 235, 0.08);
            color: #1d4ed8;
            font-size: 0.76rem;
            font-weight: 700;
            margin-bottom: 0.55rem;
        }
        .onboarding-fullscreen-title {
            font-size: 2rem;
            line-height: 1.15;
            font-weight: 800;
            color: rgba(15, 23, 42, 0.98);
            margin-bottom: 0.3rem;
        }
        .onboarding-fullscreen-copy {
            font-size: 1rem;
            line-height: 1.55;
            color: rgba(51, 65, 85, 0.82);
            max-width: 980px;
            margin-bottom: 0.5rem;
        }
        .onboarding-progress-note {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            margin: 0.25rem 0 0.65rem 0;
            font-size: 0.83rem;
            color: rgba(51, 65, 85, 0.8);
            flex-wrap: wrap;
        }
        .onboarding-progress-note strong {
            color: rgba(15, 23, 42, 0.95);
        }
        .onboarding-actions-note {
            margin: 0.25rem 0 0.75rem 0;
            font-size: 0.82rem;
            color: rgba(71, 85, 105, 0.82);
        }
        .onboarding-destination-card {
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: 20px;
            padding: 1rem 1rem 0.95rem 1rem;
            background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,250,252,0.95));
            min-height: 210px;
            box-shadow: 0 10px 22px rgba(15, 23, 42, 0.04);
            margin-bottom: 0.6rem;
        }
        .onboarding-destination-card--recommended {
            border-color: rgba(37, 99, 235, 0.22);
            background: linear-gradient(180deg, rgba(239,246,255,0.96), rgba(255,255,255,0.98));
            box-shadow: 0 12px 28px rgba(37, 99, 235, 0.08);
        }
        .onboarding-destination-kicker {
            display: inline-block;
            padding: 0.16rem 0.48rem;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 700;
            margin-bottom: 0.7rem;
            background: rgba(15, 23, 42, 0.06);
            color: rgba(51, 65, 85, 0.9);
        }
        .onboarding-destination-header {
            display: flex;
            align-items: center;
            gap: 0.7rem;
            margin-bottom: 0.6rem;
        }
        .onboarding-destination-title {
            font-size: 1rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.98);
        }
        .onboarding-destination-copy {
            font-size: 0.88rem;
            line-height: 1.52;
            color: rgba(49, 51, 63, 0.8);
            margin-bottom: 0.5rem;
        }
        .onboarding-destination-note {
            font-size: 0.8rem;
            color: rgba(71, 85, 105, 0.88);
        }
        .app-status-strip {
            display: flex;
            align-items: flex-start;
            gap: 0.7rem;
            padding: 0.72rem 0.85rem;
            border-radius: 16px;
            border: 1px solid rgba(37, 99, 235, 0.16);
            background: linear-gradient(180deg, rgba(239,246,255,0.96), rgba(255,255,255,0.95));
            box-shadow: 0 8px 18px rgba(15, 23, 42, 0.03);
            margin-bottom: 0.7rem;
        }
        .app-status-strip-icon {
            font-size: 1rem;
            line-height: 1;
            margin-top: 0.05rem;
        }
        .app-status-strip-title {
            font-size: 0.88rem;
            font-weight: 700;
            color: rgba(30, 64, 175, 0.98);
            margin-bottom: 0.08rem;
        }
        .app-status-strip-copy {
            font-size: 0.82rem;
            line-height: 1.4;
            color: rgba(30, 41, 59, 0.82);
        }
        .focus-callout {
            border: 1px solid rgba(49, 51, 63, 0.08);
            border-radius: 16px;
            padding: 0.65rem 0.8rem;
            background: rgba(255,255,255,0.82);
            margin-bottom: 0.55rem;
        }
        .focus-callout--info {
            border-color: rgba(37, 99, 235, 0.14);
            background: linear-gradient(180deg, rgba(239,246,255,0.92), rgba(255,255,255,0.96));
        }
        .focus-callout--warning {
            border-color: rgba(245, 158, 11, 0.16);
            background: linear-gradient(180deg, rgba(255,251,235,0.94), rgba(255,255,255,0.96));
        }
        .focus-callout-title {
            font-size: 0.9rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.96);
            margin-bottom: 0.12rem;
        }
        .focus-callout-copy {
            font-size: 0.85rem;
            line-height: 1.45;
            color: rgba(49, 51, 63, 0.78);
        }
        .summary-list-panel {
            border: 1px solid rgba(49, 51, 63, 0.08);
            border-radius: 16px;
            padding: 0.72rem 0.85rem;
            background: rgba(255,255,255,0.78);
            margin-bottom: 0.55rem;
        }
        .summary-list-kicker {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: rgba(71, 85, 105, 0.72);
            font-weight: 700;
            margin-bottom: 0.16rem;
        }
        .summary-list-title {
            font-size: 1rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.96);
            margin-bottom: 0.35rem;
        }
        .summary-list-items {
            margin: 0;
            padding-left: 1.05rem;
            color: rgba(49, 51, 63, 0.82);
            font-size: 0.88rem;
            line-height: 1.55;
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
            padding: 0.72rem 0.88rem;
            background: rgba(255,255,255,0.70);
            margin-bottom: 0.55rem;
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
            padding: 0.82rem 0.95rem;
            background: linear-gradient(180deg, rgba(255,255,255,0.90), rgba(248,250,252,0.92));
            margin-bottom: 0.65rem;
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
            padding: 0.72rem 0.88rem;
            background: rgba(255,255,255,0.78);
            margin-bottom: 0.55rem;
        }
        .tab-intro-title {
            font-size: 1rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.98);
            margin-bottom: 0.2rem;
        }
        .tab-intro-copy {
            font-size: 0.88rem;
            color: rgba(49, 51, 63, 0.78);
            margin-bottom: 0.15rem;
        }
        .tab-intro-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.5rem;
            margin-top: 0.45rem;
        }
        .tab-intro-card {
            border: 1px solid rgba(49, 51, 63, 0.08);
            border-radius: 14px;
            padding: 0.58rem 0.68rem;
            background: rgba(248,250,252,0.92);
        }
        .tab-intro-card-kicker {
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: rgba(71, 85, 105, 0.75);
            font-weight: 700;
            margin-bottom: 0.18rem;
        }
        .tab-intro-card-copy {
            font-size: 0.84rem;
            line-height: 1.45;
            color: rgba(49, 51, 63, 0.78);
        }
        .tab-role-note {
            margin-top: 0.4rem;
            padding: 0.38rem 0.58rem;
            border-radius: 12px;
            background: rgba(239,246,255,0.88);
            border: 1px solid rgba(147, 197, 253, 0.42);
            color: rgba(30, 64, 175, 0.88);
            font-size: 0.79rem;
        }
        .quick-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin: 0.15rem 0 0.55rem;
        }
        .quick-chip {
            display: inline-block;
            padding: 0.2rem 0.55rem;
            border-radius: 999px;
            background: rgba(15, 23, 42, 0.06);
            color: rgba(30, 41, 59, 0.88);
            font-size: 0.74rem;
            font-weight: 700;
        }
        @media (max-width: 900px) {
            .tab-intro-grid {
                grid-template-columns: 1fr;
            }
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
        .home-project-shell {
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: 24px;
            padding: 0.82rem 0.92rem;
            background: linear-gradient(135deg, rgba(239,246,255,0.98), rgba(255,255,255,0.94));
            box-shadow: 0 14px 30px rgba(15, 23, 42, 0.05);
            margin-bottom: 0.5rem;
        }
        .home-project-kicker {
            display: inline-block;
            padding: 0.18rem 0.55rem;
            border-radius: 999px;
            background: rgba(14, 165, 233, 0.10);
            color: #0369a1;
            font-size: 0.74rem;
            font-weight: 700;
            margin-bottom: 0.45rem;
        }
        .home-project-title {
            font-size: 1.3rem;
            line-height: 1.2;
            font-weight: 800;
            color: rgba(15, 23, 42, 0.98);
            margin-bottom: 0.18rem;
        }
        .home-project-copy {
            font-size: 0.9rem;
            line-height: 1.42;
            color: rgba(49, 51, 63, 0.78);
        }
        .home-project-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin-top: 0.65rem;
        }
        .home-project-chip {
            display: inline-block;
            padding: 0.22rem 0.58rem;
            border-radius: 999px;
            background: rgba(15, 23, 42, 0.06);
            color: rgba(15, 23, 42, 0.88);
            font-size: 0.75rem;
            font-weight: 700;
        }
        .home-presentation-grid {
            display: grid;
            grid-template-columns: 1.2fr 1fr 1fr;
            gap: 0.75rem;
            margin: 0.35rem 0 0.8rem;
        }
        .home-presentation-card {
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: 22px;
            padding: 0.95rem 1rem;
            background: rgba(255,255,255,0.92);
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
            min-height: 220px;
        }
        .home-presentation-kicker {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: rgba(71, 85, 105, 0.72);
            font-weight: 700;
            margin-bottom: 0.28rem;
        }
        .home-presentation-title {
            font-size: 1.08rem;
            font-weight: 800;
            color: rgba(15, 23, 42, 0.98);
            margin-bottom: 0.3rem;
        }
        .home-presentation-copy {
            font-size: 0.9rem;
            line-height: 1.5;
            color: rgba(49, 51, 63, 0.78);
            margin-bottom: 0.55rem;
        }
        .home-presentation-list {
            margin: 0;
            padding-left: 1.05rem;
            color: rgba(49, 51, 63, 0.82);
            font-size: 0.86rem;
            line-height: 1.55;
        }
        .home-stack-row {
            display: flex;
            align-items: flex-start;
            gap: 0.65rem;
            padding: 0.62rem 0;
            border-top: 1px solid rgba(49, 51, 63, 0.08);
        }
        .home-stack-row:first-of-type {
            border-top: none;
            padding-top: 0.1rem;
        }
        .home-stack-title {
            font-size: 0.88rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.96);
            margin-bottom: 0.12rem;
        }
        .home-stack-copy {
            font-size: 0.82rem;
            line-height: 1.42;
            color: rgba(49, 51, 63, 0.74);
        }
        .home-include-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.5rem;
            margin-top: 0.2rem;
        }
        .home-include-item {
            border: 1px solid rgba(49, 51, 63, 0.08);
            border-radius: 16px;
            padding: 0.68rem 0.72rem;
            background: rgba(248,250,252,0.92);
        }
        .home-include-title {
            font-size: 0.82rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.96);
            margin-bottom: 0.1rem;
        }
        .home-include-copy {
            font-size: 0.77rem;
            line-height: 1.4;
            color: rgba(49, 51, 63, 0.74);
        }
        .home-mini-card {
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: 18px;
            padding: 0.8rem 0.9rem;
            background: rgba(255,255,255,0.88);
            min-height: 150px;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
            margin-bottom: 0.55rem;
        }
        .home-mini-kicker {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: rgba(49, 51, 63, 0.56);
            margin-bottom: 0.25rem;
        }
        .home-mini-title {
            font-size: 1rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.98);
            margin-bottom: 0.22rem;
        }
        .home-mini-copy {
            font-size: 0.88rem;
            color: rgba(49, 51, 63, 0.75);
            line-height: 1.45;
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
            padding: 0.76rem 0.72rem 0.68rem;
            background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(248,250,252,0.92));
            box-shadow: 0 12px 26px rgba(15, 23, 42, 0.05);
            text-align: center;
            min-height: 164px;
            margin-bottom: 0.4rem;
            transition: transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease;
        }
        .home-icon-tile--recommended {
            border-color: rgba(37, 99, 235, 0.22);
            background: linear-gradient(180deg, rgba(239,246,255,0.98), rgba(255,255,255,0.94));
            box-shadow: 0 14px 30px rgba(37, 99, 235, 0.10);
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
            font-size: 1rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.98);
            margin-bottom: 0.32rem;
        }
        .home-icon-copy {
            font-size: 0.8rem;
            line-height: 1.38;
            color: rgba(49, 51, 63, 0.74);
            min-height: 44px;
        }
        .home-icon-caption {
            display: inline-block;
            margin-top: 0.42rem;
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
        .sidebar-kicker {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: rgba(71, 85, 105, 0.72);
            font-weight: 700;
            margin-bottom: 0.18rem;
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
        .sidebar-hint {
            border: 1px solid rgba(49, 51, 63, 0.08);
            border-radius: 14px;
            padding: 0.62rem 0.72rem;
            background: rgba(255,255,255,0.8);
            margin: 0.15rem 0 0.55rem;
        }
        .sidebar-hint--info {
            border-color: rgba(37, 99, 235, 0.12);
            background: rgba(239,246,255,0.7);
        }
        .sidebar-hint--neutral {
            border-color: rgba(49, 51, 63, 0.08);
            background: rgba(248,250,252,0.88);
        }
        .sidebar-hint-title {
            font-size: 0.78rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.92);
            margin-bottom: 0.12rem;
        }
        .sidebar-hint-copy {
            font-size: 0.78rem;
            line-height: 1.38;
            color: rgba(49, 51, 63, 0.74);
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
        .app-footer {
            margin-top: 1rem;
            padding: 0.95rem 1rem 0.8rem;
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: 22px;
            background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(248,250,252,0.92));
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
        }
        .app-footer-title {
            font-size: 1rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.98);
            margin-bottom: 0.18rem;
        }
        .app-footer-copy {
            font-size: 0.88rem;
            line-height: 1.45;
            color: rgba(49, 51, 63, 0.78);
            margin-bottom: 0.7rem;
        }
        .footer-funding-lead {
            font-size: 0.84rem;
            line-height: 1.45;
            color: rgba(49, 51, 63, 0.78);
            margin: 0.1rem 0 0.65rem;
        }
        .footer-sponsor-card {
            border: 1px solid rgba(49, 51, 63, 0.08);
            border-radius: 16px;
            padding: 0.65rem 0.7rem 0.55rem;
            background: rgba(255,255,255,0.82);
            min-height: 168px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            box-shadow: 0 6px 16px rgba(15, 23, 42, 0.04);
        }
        .footer-sponsor-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.7rem;
            align-items: stretch;
        }
        .footer-sponsor-title {
            font-size: 0.82rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.96);
            margin-bottom: 0.35rem;
        }
        .footer-sponsor-copy {
            font-size: 0.76rem;
            line-height: 1.35;
            color: rgba(49, 51, 63, 0.74);
            margin-bottom: 0.5rem;
        }
        .footer-sponsor-logo {
            height: 44px;
            width: auto;
            max-width: 100%;
            object-fit: contain;
            margin: 0.2rem 0 0.55rem;
        }
        .footer-sponsor-link {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            padding: 0.48rem 0.65rem;
            border-radius: 12px;
            background: rgba(37, 99, 235, 0.10);
            color: #1d4ed8;
            text-decoration: none;
            font-size: 0.79rem;
            font-weight: 700;
            border: 1px solid rgba(37, 99, 235, 0.14);
            box-sizing: border-box;
        }
        .footer-sponsor-link:hover {
            background: rgba(37, 99, 235, 0.14);
            color: #1e40af;
        }
        .footer-contact-line {
            margin-top: 0.55rem;
        }
        @media (max-width: 900px) {
            .footer-sponsor-grid {
                grid-template-columns: 1fr;
            }
            .home-presentation-grid,
            .home-include-grid {
                grid-template-columns: 1fr;
            }
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


def icon_badge_html(name: str, size: str = "md") -> str:
    label, bg, border, fg = ICON_BADGES.get(name, ICON_BADGES["navigator"])
    svg = ICON_SVG_PATHS.get(name)
    content = (
        f"<svg viewBox='0 0 24 24' aria-hidden='true' focusable='false'>{svg}</svg>"
        if svg
        else label
    )
    return (
        f"<span class='pro-icon-badge pro-icon-badge--{size}' "
        f"style='background:{bg};border-color:{border};color:{fg};'>{content}</span>"
    )


def render_disclaimer_banner():
    if not st.session_state.get("disclaimer_collapsed", False):
        banner_cols = st.columns([8, 1.2])
        with banner_cols[0]:
            st.markdown(
                """
                <div class="app-disclaimer">
                    <div class="app-disclaimer-icon">"""
                + icon_badge_html("notice", "sm")
                + """</div>
                    <div>
                        <div class="app-disclaimer-title">Educational demo only</div>
                        <div class="app-disclaimer-copy">This app is for demonstration, learning, and research. It is not intended for production, commercial, safety, or operational deployment.</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with banner_cols[1]:
            st.write("")
            if st.button("Hide", key="collapse_disclaimer_banner", use_container_width=True):
                st.session_state.disclaimer_collapsed = True
                st.rerun()
    else:
        compact_cols = st.columns([8, 1.2])
        with compact_cols[0]:
            st.caption("Educational demo only · Not intended for production, commercial, safety, or operational deployment.")
        with compact_cols[1]:
            if st.button("Show", key="expand_disclaimer_banner", use_container_width=True):
                st.session_state.disclaimer_collapsed = False
                st.rerun()

    with st.expander("See full disclaimer", expanded=False):
        st.markdown(
            "This demo is provided as a proof-of-concept experience only. All content, data, and examples are intended for learning and research. "
            "It should not be used for commercial, production, or operational deployment, and the authors assume no responsibility for misuse or unintended application."
        )


def render_onboarding_panel(title: str, body: str, bullets: list[str], kicker: str, variant: str = "info"):
    items_html = "".join([f"<li>{item}</li>" for item in bullets])
    st.markdown(
        f"""
        <div class="onboarding-panel onboarding-panel--{variant}">
            <div class="onboarding-panel-kicker">{kicker}</div>
            <div class="onboarding-panel-title">{title}</div>
            <div class="onboarding-panel-copy">{body}</div>
            <ul class="onboarding-panel-list">{items_html}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_onboarding_destination_card(
    icon: str,
    title: str,
    body: str,
    note: str,
    kicker: str,
    recommended: bool = False,
):
    recommended_class = " onboarding-destination-card--recommended" if recommended else ""
    st.markdown(
        f"""
        <div class="onboarding-destination-card{recommended_class}">
            <div class="onboarding-destination-kicker">{kicker}</div>
            <div class="onboarding-destination-header">
                <div>{icon_badge_html(icon, 'md')}</div>
                <div class="onboarding-destination-title">{title}</div>
            </div>
            <div class="onboarding-destination-copy">{body}</div>
            <div class="onboarding-destination-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_status_strip(title: str, body: str, icon: str = "ℹ️"):
    st.markdown(
        f"""
        <div class="app-status-strip">
            <div class="app-status-strip-icon">{icon_badge_html(icon, 'sm')}</div>
            <div>
                <div class="app-status-strip-title">{title}</div>
                <div class="app-status-strip-copy">{body}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_focus_callout(title: str, body: str, variant: str = "info"):
    st.markdown(
        f"""
        <div class="focus-callout focus-callout--{variant}">
            <div class="focus-callout-title">{title}</div>
            <div class="focus-callout-copy">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_summary_list(title: str, bullets: list[str], kicker: str = "Summary"):
    items_html = "".join([f"<li>{item}</li>" for item in bullets])
    st.markdown(
        f"""
        <div class="summary-list-panel">
            <div class="summary-list-kicker">{kicker}</div>
            <div class="summary-list-title">{title}</div>
            <ul class="summary-list-items">{items_html}</ul>
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
    role_line = f"<div class='tab-role-note'><strong>For {role}:</strong> {role_copy}</div>" if role_copy else ""
    st.markdown(
        f"""
        <div class="tab-intro">
            <div class="tab-intro-title">{tab_name}</div>
            <div class="tab-intro-copy">{copy['summary']}</div>
            <div class="tab-intro-grid">
                <div class="tab-intro-card">
                    <div class="tab-intro-card-kicker">Look for</div>
                    <div class="tab-intro-card-copy">{copy['focus']}</div>
                </div>
                <div class="tab-intro-card">
                    <div class="tab-intro-card-kicker">Next</div>
                    <div class="tab-intro-card-copy">{copy['next']}</div>
                </div>
            </div>
            {role_line}
        </div>
        """,
        unsafe_allow_html=True,
    )


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
            <div class="sidebar-kicker">Control center</div>
            <div class="sidebar-card-title">{icon_badge_html('navigator', 'sm')} <span style='margin-left:0.35rem;'>Demo Navigator</span></div>
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


def render_sidebar_intro_card(title: str, body: str):
    st.markdown(
        f"""
        <div class="sidebar-card">
            <div class="sidebar-kicker">Sidebar guide</div>
            <div class="sidebar-card-title">{title}</div>
            <div class="sidebar-card-copy">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_hint(title: str, body: str, variant: str = "neutral"):
    st.markdown(
        f"""
        <div class="sidebar-hint sidebar-hint--{variant}">
            <div class="sidebar-hint-title">{title}</div>
            <div class="sidebar-hint-copy">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _footer_image_src(image_source) -> str:
    if isinstance(image_source, bytes):
        encoded = base64.b64encode(image_source).decode("utf-8")
        return f"data:image/png;base64,{encoded}"
    return str(image_source)


def render_funding_acknowledgement(compact: bool = False):
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

    if not compact:
        st.markdown("### Funding acknowledgement")
        st.markdown(
            f"This demo hub is supported by **VINNOVA** (Sweden's Innovation Agency), "
            f"project reference **{PROJECT_REF}**, by **KK-stiftelsen** (The Knowledge Foundation), "
            f"and by **Interreg Aurora**."
        )
    else:
        st.markdown(
            f"<div class='footer-funding-lead'>Supported by <strong>VINNOVA</strong> (project reference <strong>{PROJECT_REF}</strong>), <strong>KK-stiftelsen</strong>, and <strong>Interreg Aurora</strong>.</div>",
            unsafe_allow_html=True,
        )

    funding_items = [
        (
            "VINNOVA",
            vinnova_logo_bytes or VINNOVA_LOGO_URL,
            PROJECT_URL,
            "View VINNOVA project",
            "Sweden's Innovation Agency supporting the project showcase and research context.",
        ),
        (
            "KK-stiftelsen",
            kks_logo_bytes or KKS_LOGO_URL,
            KKS_URL,
            "View KKS website",
            "Research funding support for knowledge-building and trustworthy AI demonstration work.",
        ),
        (
            "Interreg Aurora",
            aurora_logo_bytes or AURORA_LOGO_URL,
            AURORA_URL,
            "View Aurora project",
            "Cross-border innovation support connected to regional digital resilience and collaboration.",
        ),
    ]

    if compact:
        cards_html = "".join(
            [
                dedent(
                    f"""
                    <div class="footer-sponsor-card">
                        <div>
                            <div class="footer-sponsor-title">{label}</div>
                            <div class="footer-sponsor-copy">{copy}</div>
                            <img class="footer-sponsor-logo" src="{_footer_image_src(image_source)}" alt="{label} logo" />
                        </div>
                        <a class="footer-sponsor-link" href="{link_url}" target="_blank" rel="noopener noreferrer">{button_text}</a>
                    </div>
                    """
                ).strip()
                for label, image_source, link_url, button_text, copy in funding_items
            ]
        )
        st.markdown(f"<div class='footer-sponsor-grid'>{cards_html}</div>", unsafe_allow_html=True)
        return

    columns = st.columns(3)
    for column, (label, image_source, link_url, button_text, copy) in zip(columns, funding_items):
        with column:
            with st.container(border=True):
                st.image(image_source, width=170)
                st.caption(copy)
                st.link_button(button_text, link_url, use_container_width=True)
                st.caption(label)


def render_footerline():
    st.markdown(
        "<div class='footer-contact-line'><small>Trustworthy AI Demo Hub — Developed and maintained by Kyi Thar • Contact: kyi.thar@miun.se</small></div>",
        unsafe_allow_html=True,
    )


def render_app_footer():
    st.markdown(
        """
        <div class="app-footer">
            <div class="app-footer-title">Project funding and contact</div>
            <div class="app-footer-copy">
                A compact presentation footer for Streamlit Cloud so project acknowledgement, sponsor links, and contact details remain visible without taking over the page.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_funding_acknowledgement(compact=True)
    render_footerline()


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

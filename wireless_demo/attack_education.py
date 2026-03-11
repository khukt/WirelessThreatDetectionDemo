from __future__ import annotations

import streamlit as st

from .ux import icon_badge_html


ATTACK_KNOWLEDGE = {
    "Normal": {
        "icon": "normal",
        "title": "Normal baseline",
        "what": "This is the healthy reference case. Devices still show variation, but the pattern stays within expected RF, GNSS, access, and integrity behavior.",
        "analogy": "Think of this as a normal operating day: some noise and motion, but no coordinated threat pattern.",
        "why_it_matters": "Users need a stable baseline so they can tell the difference between routine variation and a real attack pattern.",
        "watch_for": [
            "Healthy SNR/SINR and moderate noise floor",
            "Low packet loss, low latency, and stable throughput",
            "Low auth churn and low integrity errors",
        ],
        "how_demo_models_it": "The generator produces ordinary mobility, RF variation, and routine network noise without applying attack-specific perturbations.",
        "limits": "Normal does not mean perfect; it is still synthetic and simpler than real industrial operations.",
    },
    "Jamming": {
        "icon": "jamming",
        "title": "Jamming",
        "what": "Jamming is deliberate interference that makes legitimate wireless communication harder or impossible.",
        "analogy": "It is like trying to talk in a room where someone is blasting loud noise over everyone else.",
        "why_it_matters": "Wireless control, telemetry, and logistics workflows depend on usable radio links. Jamming can disrupt safety, visibility, and coordination.",
        "watch_for": [
            "Lower SNR or SINR",
            "Higher noise floor, PHY/BLER errors, and packet loss",
            "Higher latency, jitter, and channel busy time",
        ],
        "how_demo_models_it": "The demo uses a localized interference radius and mode-specific RF degradation such as broadband noise, reactive interference, or burst interference.",
        "limits": "This is a simplified radio model. It does not simulate protocol-specific waveform behavior, adaptive coding responses, or hardware-specific antenna effects.",
    },
    "Access Breach": {
        "icon": "breach",
        "title": "Access breach",
        "what": "An access breach covers attacks on association, authentication, or infrastructure trust, such as rogue AP/gNB behavior, credential abuse, or deauth-style disruption.",
        "analogy": "It is like a fake entrance or checkpoint tricking users into connecting to the wrong place or repeatedly kicking them back out.",
        "why_it_matters": "Even when radio quality looks acceptable, devices may fail to connect, re-authenticate, or stay attached to trusted infrastructure.",
        "watch_for": [
            "Deauth bursts and association churn",
            "Retry spikes, DHCP or attach failures",
            "Rogue RSSI gap or infrastructure anomalies",
        ],
        "how_demo_models_it": "The demo uses a rogue-node lure radius and applies mode-specific access symptoms for Evil Twin, Rogue Open AP, Credential hammer, or Deauth flood behavior.",
        "limits": "The model combines Wi-Fi and cellular access symptoms into one educational scenario, so it is broader than a real protocol-specific test plan.",
    },
    "GPS Spoofing": {
        "icon": "spoofing",
        "title": "GPS spoofing",
        "what": "GPS spoofing means feeding a receiver false satellite-like signals so it computes the wrong position or time.",
        "analogy": "It is like giving someone a convincing but fake map and clock so they believe they are somewhere else.",
        "why_it_matters": "Location and timing errors can misroute vehicles, corrupt tracking, and mislead downstream decisions that trust GNSS data.",
        "watch_for": [
            "Higher position error",
            "Odd HDOP, fewer satellites, or unusual clock drift",
            "Strange Doppler and C/N₀ patterns",
        ],
        "how_demo_models_it": "The demo can target a single device, localized area, or site-wide footprint and applies GNSS inconsistencies only to the affected scope.",
        "limits": "The GNSS behavior is educational rather than physics-accurate; it does not emulate actual satellite constellations, receiver tracking loops, or navigation filters.",
    },
    "Data Tamper": {
        "icon": "tamper",
        "title": "Data tamper",
        "what": "Data tampering means altering payloads or message streams so the receiving system sees corrupted, replayed, biased, or malformed information.",
        "analogy": "It is like editing a report in transit so the numbers, timestamps, or units no longer match reality.",
        "why_it_matters": "Even if connectivity is healthy, bad data can mislead operations, analytics, and automation.",
        "watch_for": [
            "Timestamp skew, duplicates, and sequence gaps",
            "CRC or HMAC failures",
            "Schema violations, unusual entropy, or biased values",
        ],
        "how_demo_models_it": "The demo applies gateway-focused replay, constant injection, drift, bitflip/noise, or scale mismatch effects to integrity-related telemetry.",
        "limits": "This is not a full industrial protocol emulator; it focuses on recognizable integrity symptoms rather than exact field-level attack traces.",
    },
}


SUMMARY_ROLES = {"Executive", "Regulator", "End User"}
ORDERED_FAMILIES = ["Normal", "Jamming", "Access Breach", "GPS Spoofing", "Data Tamper"]


def scenario_family_name(scenario: str) -> str:
    text = str(scenario)
    for family in ORDERED_FAMILIES:
        if family != "Normal" and text.startswith(family):
            return family
    return "Normal"


def _audience_depth(role: str) -> str:
    return "summary" if role in SUMMARY_ROLES else "technical"


def _render_attack_card(family: str, role: str):
    attack = ATTACK_KNOWLEDGE[family]
    depth = _audience_depth(role)
    st.markdown(
        f"<div class='inline-icon-heading'>{icon_badge_html(attack['icon'], 'sm')}<div class='inline-icon-heading-title'>{attack['title']}</div></div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"**What it is:** {attack['what']}")
    st.caption(attack["analogy"])
    st.markdown(f"**Why it matters:** {attack['why_it_matters']}")
    st.markdown("**What to watch for in this demo:**")
    st.markdown("\n".join([f"- {item}" for item in attack["watch_for"]]))
    if depth == "technical":
        st.markdown(f"**How the demo models it:** {attack['how_demo_models_it']}")
        st.markdown(f"**Educational limit:** {attack['limits']}")
    else:
        with st.expander("Open technical note", expanded=False):
            st.markdown(f"**How the demo models it:** {attack['how_demo_models_it']}")
            st.markdown(f"**Educational limit:** {attack['limits']}")


def render_attack_academy(role: str, selected_scenario: str | None = None):
    st.markdown("### Attack Academy")
    st.caption("This educational section explains what each threat means in the real world, what you should see in the demo, and where the simplifications are.")
    chosen_family = scenario_family_name(selected_scenario) if selected_scenario else None
    for family in ORDERED_FAMILIES:
        expanded = family == chosen_family
        with st.expander(f"{ATTACK_KNOWLEDGE[family]['title']}", expanded=expanded):
            _render_attack_card(family, role)


def render_current_attack_brief(scenario: str, role: str, title: str = "Current attack explainer"):
    family = scenario_family_name(scenario)
    attack = ATTACK_KNOWLEDGE[family]
    st.markdown(f"### {title}")
    st.markdown(
        f"""
        <div class="section-card">
            <div class="summary-kicker">{attack['title']}</div>
            <div class="summary-value">{scenario}</div>
            <div class="summary-copy"><strong>What it is:</strong> {attack['what']}</div>
            <div class="summary-copy" style="margin-top:0.35rem;"><strong>Watch for:</strong> {', '.join(attack['watch_for'][:2])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("Open educational detail", expanded=False):
        _render_attack_card(family, role)


def attack_category_caption(category: str) -> str:
    family = scenario_family_name(category)
    attack = ATTACK_KNOWLEDGE.get(family, ATTACK_KNOWLEDGE["Normal"])
    return attack["what"]

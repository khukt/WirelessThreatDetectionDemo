import streamlit as st

from ..attack_education import attack_category_caption, render_current_attack_brief
from ..config import CFG
from ..hitl import get_review_status
from ..ui_components import incident_category, render_incident_card
from ..ux import render_section_card, render_tab_intro


ROLE_INCIDENTS_CALLOUT = {
    "End User": "Prioritize the queue, confirm what matters, and use review states to keep operations focused.",
    "Domain Expert": "This is the main analyst workspace for triage, evidence review, and deciding whether alerts match domain reality.",
    "Regulator": "Look for understandable incidents, visible human review, and clear paths for approval, rejection, or escalation.",
    "AI Builder": "Inspect how model output becomes operator-facing incidents and how human feedback changes suppression and prioritization.",
    "Executive": "Use this page to see what actions operators would take and how much human oversight is built into response.",
}
def _incident_review_status(incident):
    status = get_review_status(incident)
    return "Pending Review" if status == "Pending Review" else status


def _severity_rank(level):
    return {"High": 3, "Medium": 2, "Low": 1}.get(level, 0)


def _sort_incidents(incidents, sort_by):
    if sort_by == "Highest probability":
        return sorted(incidents, key=lambda incident: (incident.get("prob", 0.0), incident.get("tick", 0)), reverse=True)
    if sort_by == "Highest severity":
        return sorted(
            incidents,
            key=lambda incident: (_severity_rank(incident.get("severity", "Low")), incident.get("prob", 0.0), incident.get("tick", 0)),
            reverse=True,
        )
    if sort_by == "Device name":
        return sorted(incidents, key=lambda incident: (incident.get("device_id", ""), -incident.get("tick", 0)))
    return sorted(incidents, key=lambda incident: incident.get("tick", 0), reverse=True)


def _matches_search(incident, query):
    if not query:
        return True
    haystack = " ".join(
        [
            incident.get("device_id", ""),
            incident.get("scenario", ""),
            incident.get("type", ""),
            incident.get("type_label", ""),
            incident_category(incident),
        ]
    ).lower()
    return query in haystack


def _filter_incidents(incidents, query, severities, review_states):
    filtered = []
    for incident in incidents:
        review_status = _incident_review_status(incident)
        if incident.get("severity", "Low") not in severities:
            continue
        if review_status not in review_states:
            continue
        if not _matches_search(incident, query):
            continue
        filtered.append(incident)
    return filtered


def render_incidents_tab(role):
    render_tab_intro("Incidents", role)
    st.info(f"{role} focus: {ROLE_INCIDENTS_CALLOUT.get(role, ROLE_INCIDENTS_CALLOUT['End User'])}")
    render_current_attack_brief(st.session_state.get("scenario_selector", "Normal"), role, title="What this attack means")
    render_section_card(
        "Incidents",
        "This is the analyst queue for sorting, filtering, and reviewing incidents before they become operational follow-up actions.",
        kicker="Triage workspace",
    )
    all_incidents = st.session_state.incidents
    if not all_incidents:
        current_tick = int(st.session_state.get("tick", 0))
        warmup_remaining = max(CFG.rolling_len - current_tick, 0)
        if warmup_remaining > 0:
            st.info(f"Monitoring is warming up. The detector needs about {CFG.rolling_len} ticks of history before it can emit incidents. {warmup_remaining} more tick(s) to go.")
        else:
            st.success("No incidents yet.")
        st.caption("Use `Auto stream` for continuous playback or `Step once` to advance manually. Threat scenarios start producing incidents after the rolling history buffer fills.")
        return

    with st.container(border=True):
        top = st.columns(4)
        severities = [incident.get("severity", "Low") for incident in all_incidents]
        top[0].metric("Total incidents", len(all_incidents))
        top[1].metric("High severity", sum(level == "High" for level in severities))
        top[2].metric("Latest tick", max(incident.get("tick", 0) for incident in all_incidents))
        top[3].metric("Unique devices", len({incident["device_id"] for incident in all_incidents}))

    render_section_card(
        "Queue filters",
        "Use these controls to focus the triage queue before switching between category tabs or reviewing individual incident cards.",
        kicker="Filtering",
    )
    with st.container(border=True):
        st.markdown("<div class='quick-chip-row'><span class='quick-chip'>Tip: start with highest severity</span><span class='quick-chip'>Review status stays visible on each card</span><span class='quick-chip'>Search accepts device, scenario, or threat family</span></div>", unsafe_allow_html=True)
        control_cols = st.columns([1.2, 1, 1, 1, 0.8])
        max_items = control_cols[0].slider("Incidents per view", 5, 100, min(25, len(all_incidents)), 5, key="incidents_max_items")
        sort_by = control_cols[1].selectbox(
            "Sort by",
            ["Newest first", "Highest probability", "Highest severity", "Device name"],
            index=0,
            key="incidents_sort_by",
        )
        review_states = control_cols[2].multiselect(
            "Review status",
            ["Pending Review", "Approved", "False Positive", "Escalated"],
            default=["Pending Review", "Approved", "False Positive", "Escalated"],
            key="incidents_review_states",
        )
        search_query = control_cols[3].text_input("Search incidents", placeholder="Device, scenario, attack type", key="incidents_search_query").strip().lower()
        if control_cols[4].button("Reset", key="incidents_reset_filters", use_container_width=True):
            st.session_state.incidents_sort_by = "Newest first"
            st.session_state.incidents_review_states = ["Pending Review", "Approved", "False Positive", "Escalated"]
            st.session_state.incidents_search_query = ""
            st.session_state.incidents_severity_filter = ["High", "Medium", "Low"]
            st.session_state.incidents_max_items = min(25, len(all_incidents))
            st.rerun()

        severity_filter = st.multiselect(
            "Severity filter",
            ["High", "Medium", "Low"],
            default=["High", "Medium", "Low"],
            help="Use this to narrow the triage queue before switching between category tabs.",
            key="incidents_severity_filter",
        )

    filtered_all = _sort_incidents(_filter_incidents(all_incidents, search_query, severity_filter, review_states), sort_by)
    review_counts = {
        "Pending Review": sum(_incident_review_status(incident) == "Pending Review" for incident in all_incidents),
        "Approved": sum(_incident_review_status(incident) == "Approved" for incident in all_incidents),
        "False Positive": sum(_incident_review_status(incident) == "False Positive" for incident in all_incidents),
        "Escalated": sum(_incident_review_status(incident) == "Escalated" for incident in all_incidents),
    }

    with st.container(border=True):
        summary = st.columns(4)
        summary[0].metric("Filtered incidents", len(filtered_all))
        summary[1].metric("Pending review", review_counts["Pending Review"])
        summary[2].metric("Approved", review_counts["Approved"])
        summary[3].metric("False positives", review_counts["False Positive"])

    st.markdown(
        "<div class='quick-chip-row'>"
        f"<span class='quick-chip'>Filtered: {len(filtered_all)}</span>"
        f"<span class='quick-chip'>Escalated: {review_counts['Escalated']}</span>"
        f"<span class='quick-chip'>Sort: {sort_by}</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    if search_query or len(severity_filter) < 3 or len(review_states) < 3 or sort_by != "Newest first":
        st.caption(
            f"Showing {len(filtered_all)} of {len(all_incidents)} incidents · sorted by {sort_by.lower()}"
        )

    if not filtered_all:
        st.info("No incidents match the current filters. Broaden the search, review status, or severity settings.")
        return

    category_map = {}
    for incident in filtered_all:
        category_map.setdefault(incident_category(incident), []).append(incident)
    order = ["Jamming", "Access Breach", "GPS Spoofing", "Data Tamper", "Other"]
    categories = [cat for cat in order if cat in category_map] + [cat for cat in category_map if cat not in order]
    tabs = st.tabs([f"{cat} ({len(category_map[cat])})" for cat in categories] + [f"All ({len(filtered_all)})"])

    for idx, cat in enumerate(categories):
        with tabs[idx]:
            render_section_card(
                f"{cat} incidents",
                "These incidents share the same attack family after the current triage filters and are ordered using the queue policy above.",
                kicker="Category view",
            )
            st.caption(f"{len(category_map[cat])} incidents in {cat.lower()} after the current triage filters.")
            st.info(attack_category_caption(cat))
            shown = 0
            for incident in category_map[cat]:
                render_incident_card(incident, role, scope=f"cat_{cat}")
                shown += 1
                if shown >= max_items:
                    break
            if len(category_map[cat]) > max_items:
                st.caption(f"Showing the top {max_items} incidents in this category.")

    with tabs[-1]:
        render_section_card(
            "All filtered incidents",
            "This tab shows the combined triage queue after all current filters and sorting rules have been applied.",
            kicker="Combined view",
        )
        shown = 0
        for incident in filtered_all:
            render_incident_card(incident, role, scope="all")
            shown += 1
            if shown >= max_items:
                break
        if len(filtered_all) > max_items:
            st.caption(f"Showing the top {max_items} incidents after filtering.")

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from textwrap import dedent, fill

from ..config import FEATURE_GLOSSARY
from ..helpers import shap_pos
from ..ux import render_focus_callout, render_section_card, render_summary_list, render_tab_intro, style_plotly_figure


ROLE_INSIGHTS_CALLOUT = {
    "End User": "Use this page only when you need a simpler explanation for why an alert was raised.",
    "Domain Expert": "Check whether important features and attack labels align with RF, GNSS, access, or integrity expectations.",
    "Regulator": "Use this page to inspect transparency artifacts, confidence controls, and how the AI reaches its conclusions.",
    "AI Builder": "This is the main technical workspace for model logic, feature importance, calibration, and architecture review.",
    "Executive": "Use this page for a simplified explanation of how the AI works and why leaders should trust or question it.",
}

ROLE_INSIGHTS_SUMMARY = {
    "Executive": {
        "title": "Leadership summary",
        "bullets": [
            "The AI first decides whether behavior looks abnormal, then explains the most likely threat type.",
            "Confidence checks are built in so alerts are not based on raw model scores alone.",
            "Human reviewers stay in control of the final operational decision.",
        ],
    },
    "Regulator": {
        "title": "Assurance summary",
        "bullets": [
            "This page exposes how the system turns telemetry into alerts, explanations, and human-reviewable outcomes.",
            "Confidence controls and transparency artifacts are shown inline rather than hidden behind the model.",
            "Technical detail remains available below for deeper inspection when needed.",
        ],
    },
}


def _is_summary_role(role):
    return role in {"Executive", "Regulator"}


def _render_role_summary(role):
    summary = ROLE_INSIGHTS_SUMMARY.get(role)
    if not summary:
        return
    render_summary_list(summary["title"], summary["bullets"], kicker="Audience summary")


@st.cache_data(show_spinner=False)
def _stakeholder_architecture_figure():
    def wrap_text(text, width):
        return fill(text, width=width).replace("\n", "<br>")

    def add_line(x0, y0, x1, y1, color="rgba(15,23,42,0.40)", width=2.0):
        fig.add_shape(
            type="line",
            x0=x0,
            y0=y0,
            x1=x1,
            y1=y1,
            line=dict(color=color, width=width),
        )

    def add_arrow(x0, y0, x1, y1, color="rgba(15,23,42,0.45)"):
        fig.add_annotation(
            x=x1,
            y=y1,
            ax=x0,
            ay=y0,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=3,
            arrowsize=1,
            arrowwidth=1.7,
            arrowcolor=color,
        )

    fig = go.Figure()
    box_specs = [
        {
            "x0": 0.03,
            "y0": 0.58,
            "x1": 0.22,
            "y1": 0.90,
            "icon": "RF",
            "title": "Fleet signals",
            "subtitle": "RF, GNSS, access, and integrity telemetry",
            "fill": "rgba(14,116,144,0.08)",
            "accent": "rgba(14,116,144,0.92)",
            "wrap": 18,
        },
        {
            "x0": 0.27,
            "y0": 0.58,
            "x1": 0.46,
            "y1": 0.90,
            "icon": "ML",
            "title": "Anomaly model",
            "subtitle": "Binary LightGBM estimates suspicious behavior",
            "fill": "rgba(239,68,68,0.08)",
            "accent": "rgba(239,68,68,0.88)",
            "wrap": 18,
        },
        {
            "x0": 0.51,
            "y0": 0.58,
            "x1": 0.70,
            "y1": 0.90,
            "icon": "QA",
            "title": "Confidence layer",
            "subtitle": "Threshold and conformal p-value grade alert confidence",
            "fill": "rgba(245,158,11,0.08)",
            "accent": "rgba(245,158,11,0.90)",
            "wrap": 18,
        },
        {
            "x0": 0.75,
            "y0": 0.58,
            "x1": 0.94,
            "y1": 0.90,
            "icon": "CLS",
            "title": "Attack typing",
            "subtitle": "Multiclass model and domain rules identify the likely threat family",
            "fill": "rgba(168,85,247,0.08)",
            "accent": "rgba(168,85,247,0.90)",
            "wrap": 18,
        },
        {
            "x0": 0.24,
            "y0": 0.08,
            "x1": 0.73,
            "y1": 0.36,
            "icon": "HITL",
            "title": "Human oversight",
            "subtitle": "Analyst approves, escalates, or rejects alerts. Review outcomes shape future triage.",
            "fill": "rgba(16,185,129,0.08)",
            "accent": "rgba(16,185,129,0.88)",
            "wrap": 44,
        },
    ]

    for spec in box_specs:
        fig.add_shape(
            type="rect",
            x0=spec["x0"],
            y0=spec["y0"],
            x1=spec["x1"],
            y1=spec["y1"],
            line=dict(color="rgba(15,23,42,0.20)", width=1.3),
            fillcolor=spec["fill"],
            layer="below",
        )
        fig.add_shape(
            type="rect",
            x0=spec["x0"],
            y0=spec["y1"] - 0.028,
            x1=spec["x1"],
            y1=spec["y1"],
            line=dict(color=spec["accent"], width=0),
            fillcolor=spec["accent"],
            layer="below",
        )
        fig.add_annotation(
            x=(spec["x0"] + spec["x1"]) / 2,
            y=spec["y1"] - 0.075,
            text=f"<b>{spec['icon']}</b> · <b>{spec['title']}</b>",
            showarrow=False,
            font=dict(size=14, color="#0f172a"),
            align="center",
        )
        fig.add_annotation(
            x=(spec["x0"] + spec["x1"]) / 2,
            y=(spec["y0"] + spec["y1"]) / 2 - 0.015,
            text=wrap_text(spec["subtitle"], spec["wrap"]),
            showarrow=False,
            font=dict(size=11, color="#334155"),
            align="center",
        )

    step_specs = [
        (0.06, 0.87, "1", box_specs[0]["accent"]),
        (0.30, 0.87, "2", box_specs[1]["accent"]),
        (0.54, 0.87, "3", box_specs[2]["accent"]),
        (0.78, 0.87, "4", box_specs[3]["accent"]),
        (0.27, 0.33, "5", box_specs[4]["accent"]),
    ]
    for x, y, label, accent in step_specs:
        fig.add_shape(
            type="circle",
            x0=x - 0.018,
            y0=y - 0.028,
            x1=x + 0.018,
            y1=y + 0.028,
            line=dict(color=accent, width=1.2),
            fillcolor=accent,
        )
        fig.add_annotation(
            x=x,
            y=y,
            text=f"<b>{label}</b>",
            showarrow=False,
            font=dict(size=10, color="white"),
        )

    forward_arrows = [
        ((0.22, 0.74), (0.27, 0.74)),
        ((0.46, 0.74), (0.51, 0.74)),
        ((0.70, 0.74), (0.75, 0.74)),
    ]
    for (x0, y0), (x1, y1) in forward_arrows:
        add_arrow(x0, y0, x1, y1)

    feedback_color = box_specs[4]["accent"]
    add_line(0.485, 0.36, 0.485, 0.48, color=feedback_color, width=2.2)
    add_line(0.365, 0.48, 0.845, 0.48, color=feedback_color, width=2.2)
    add_arrow(0.365, 0.48, 0.365, 0.58, color=feedback_color)
    add_arrow(0.605, 0.48, 0.605, 0.58, color=feedback_color)
    add_arrow(0.845, 0.48, 0.845, 0.58, color=feedback_color)

    fig.add_annotation(
        x=0.71,
        y=0.50,
        text="<b>Human feedback loop</b>",
        showarrow=False,
        font=dict(size=11, color="#065f46"),
        align="center",
        bgcolor="rgba(240,253,250,0.95)",
    )

    fig.add_annotation(
        x=0.50,
        y=0.98,
        text="<b>How telemetry becomes a reviewable alert</b>",
        showarrow=False,
        font=dict(size=15, color="#0f172a"),
        align="center",
    )

    fig.update_xaxes(visible=False, range=[0, 1])
    fig.update_yaxes(visible=False, range=[0, 1])
    fig.update_layout(
        height=430,
        margin=dict(l=10, r=10, t=16, b=10),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return fig


@st.cache_data(show_spinner=False)
def _model_decision_pipeline_figure():
    def add_box(x0, y0, x1, y1, title, subtitle, fill_color, accent_color, step, icon, centered=False, wrap_width=34):
        fig.add_shape(
            type="rect",
            x0=x0,
            y0=y0,
            x1=x1,
            y1=y1,
            line=dict(color="rgba(15,23,42,0.16)", width=1.2),
            fillcolor=fill_color,
            layer="below",
        )
        fig.add_shape(
            type="rect",
            x0=x0,
            y0=y1 - 0.018,
            x1=x1,
            y1=y1,
            line=dict(color=accent_color, width=0),
            fillcolor=accent_color,
            layer="below",
        )
        fig.add_shape(
            type="circle",
            x0=x0 + 0.025,
            y0=y1 - 0.064,
            x1=x0 + 0.065,
            y1=y1 - 0.016,
            line=dict(color=accent_color, width=1.0),
            fillcolor=accent_color,
        )
        fig.add_annotation(
            x=x0 + 0.045,
            y=y1 - 0.040,
            text=f"<b>{step}</b>",
            showarrow=False,
            font=dict(size=10, color="white"),
        )
        fig.add_annotation(
            x=x0 + 0.096,
            y=y1 - 0.040,
            text=icon,
            showarrow=False,
            font=dict(size=16, color="#0f172a"),
        )
        if centered:
            fig.add_annotation(
                x=(x0 + x1) / 2,
                y=y1 - 0.040,
                text=f"<b>{title}</b>",
                showarrow=False,
                font=dict(size=13, color="#0f172a"),
                align="center",
            )
            fig.add_annotation(
                x=(x0 + x1) / 2,
                y=(y0 + y1) / 2 - 0.015,
                text=fill(subtitle, width=wrap_width).replace("\n", "<br>"),
                showarrow=False,
                font=dict(size=10, color="#475569"),
                align="center",
            )
        else:
            fig.add_annotation(
                x=x0 + 0.17,
                y=y1 - 0.040,
                text=f"<b>{title}</b>",
                showarrow=False,
                xanchor="left",
                font=dict(size=14, color="#0f172a"),
                align="left",
            )
            fig.add_annotation(
                x=x0 + 0.05,
                y=(y0 + y1) / 2 - 0.015,
                text=fill(subtitle, width=wrap_width).replace("\n", "<br>"),
                showarrow=False,
                xanchor="left",
                font=dict(size=11, color="#475569"),
                align="left",
            )

    def add_arrow(x0, y0, x1, y1, color="rgba(15,23,42,0.38)"):
        fig.add_annotation(
            x=x1,
            y=y1,
            ax=x0,
            ay=y0,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=3,
            arrowsize=1,
            arrowwidth=1.7,
            arrowcolor=color,
        )

    def add_line(x0, y0, x1, y1, color="rgba(15,23,42,0.30)", width=1.4):
        fig.add_shape(
            type="line",
            x0=x0,
            y0=y0,
            x1=x1,
            y1=y1,
            line=dict(color=color, width=width),
        )

    def add_pill(x, y, text, fg, bg, border):
        fig.add_annotation(
            x=x,
            y=y,
            text=text,
            showarrow=False,
            font=dict(size=10, color=fg),
            bgcolor=bg,
            bordercolor=border,
            borderwidth=1,
            borderpad=4,
            align="center",
        )

    fig = go.Figure()
    main_boxes = [
        {
            "coords": (0.07, 0.78, 0.69, 0.91),
            "title": "Telemetry input",
            "subtitle": "Collect RF, GNSS, access, and integrity signals.",
            "fill": "rgba(14,116,144,0.08)",
            "accent": "rgba(14,116,144,0.90)",
            "step": "1",
            "icon": "RF",
            "wrap_width": 36,
        },
        {
            "coords": (0.07, 0.60, 0.69, 0.73),
            "title": "Window features",
            "subtitle": "Summarize recent behavior with rolling features.",
            "fill": "rgba(59,130,246,0.08)",
            "accent": "rgba(59,130,246,0.88)",
            "step": "2",
            "icon": "FE",
            "wrap_width": 34,
        },
        {
            "coords": (0.07, 0.42, 0.69, 0.55),
            "title": "Anomaly model",
            "subtitle": "Binary LightGBM scores whether behavior looks suspicious.",
            "fill": "rgba(239,68,68,0.08)",
            "accent": "rgba(239,68,68,0.88)",
            "step": "3",
            "icon": "ML",
            "wrap_width": 34,
        },
        {
            "coords": (0.07, 0.24, 0.69, 0.37),
            "title": "Confidence check",
            "subtitle": "Thresholds and conformal p-values grade alert reliability.",
            "fill": "rgba(245,158,11,0.08)",
            "accent": "rgba(245,158,11,0.90)",
            "step": "4",
            "icon": "QA",
            "wrap_width": 34,
        },
        {
            "coords": (0.07, 0.05, 0.69, 0.18),
            "title": "Incident output",
            "subtitle": "Show severity, likely threat family, and evidence.",
            "fill": "rgba(15,23,42,0.08)",
            "accent": "rgba(15,23,42,0.88)",
            "step": "6",
            "icon": "OUT",
            "wrap_width": 34,
        },
    ]
    side_boxes = [
        {
            "coords": (0.73, 0.39, 0.97, 0.53),
            "title": "Attack label",
            "subtitle": "Predict the most likely threat family.",
            "fill": "rgba(168,85,247,0.08)",
            "accent": "rgba(168,85,247,0.90)",
            "step": "5",
            "icon": "CLS",
            "centered": True,
            "wrap_width": 18,
        },
        {
            "coords": (0.73, 0.21, 0.97, 0.35),
            "title": "Rule context",
            "subtitle": "Add simple operational context.",
            "fill": "rgba(16,185,129,0.08)",
            "accent": "rgba(16,185,129,0.88)",
            "step": "R",
            "icon": "CTX",
            "centered": True,
            "wrap_width": 18,
        },
    ]

    for item in main_boxes + side_boxes:
        add_box(
            *item["coords"],
            item["title"],
            item["subtitle"],
            item["fill"],
            item["accent"],
            item["step"],
            item["icon"],
            centered=item.get("centered", False),
            wrap_width=item.get("wrap_width", 34),
        )

    add_arrow(0.38, 0.78, 0.38, 0.73)
    add_arrow(0.38, 0.60, 0.38, 0.55)
    add_arrow(0.38, 0.42, 0.38, 0.37)
    add_arrow(0.38, 0.24, 0.38, 0.18)
    add_arrow(0.69, 0.47, 0.73, 0.47, color="rgba(168,85,247,0.50)")
    add_arrow(0.85, 0.39, 0.85, 0.35, color="rgba(16,185,129,0.55)")
    add_line(0.73, 0.28, 0.73, 0.12, color="rgba(15,23,42,0.26)")
    add_arrow(0.73, 0.12, 0.69, 0.12, color="rgba(15,23,42,0.40)")

    fig.add_annotation(
        x=0.50,
        y=0.98,
        text="<b>How the AI pipeline creates an explainable alert</b>",
        showarrow=False,
        font=dict(size=16, color="#0f172a"),
        align="center",
    )
    add_pill(
        0.85,
        0.58,
        "Suspicious only",
        "#7c3aed",
        "rgba(245,243,255,0.97)",
        "rgba(196,181,253,0.70)",
    )
    add_pill(
        0.85,
        0.16,
        "Rules add context",
        "#047857",
        "rgba(236,253,245,0.97)",
        "rgba(110,231,183,0.70)",
    )
    add_pill(
        0.40,
        0.01,
        "Human reviewers make the final decision",
        "#334155",
        "rgba(248,250,252,0.98)",
        "rgba(203,213,225,0.80)",
    )

    fig.update_xaxes(visible=False, range=[0, 1])
    fig.update_yaxes(visible=False, range=[0, 1])
    fig.update_layout(
        height=600,
        margin=dict(l=8, r=8, t=12, b=8),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return fig


def _fmt_metric_value(value, precision=2, empty="—"):
    if value is None:
        return empty
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if np.isnan(numeric):
        return empty
    return f"{numeric:.{precision}f}"


def _get_global_importance_df():
    importance = st.session_state.get("global_importance")
    if importance is not None and len(importance) > 0:
        return importance

    baseline = st.session_state.get("baseline")
    explainer = st.session_state.get("explainer")
    if baseline is None or len(baseline) == 0 or explainer is None:
        return None

    sample = baseline.sample(n=min(len(baseline), 600), random_state=42) if len(baseline) > 600 else baseline
    shap_mat = shap_pos(explainer, sample)
    mean_abs = np.abs(shap_mat).mean(axis=0)
    importance = (
        pd.DataFrame({"feature": sample.columns, "mean_abs_shap": mean_abs})
        .sort_values("mean_abs_shap", ascending=False)
        .reset_index(drop=True)
    )
    st.session_state.global_importance = importance
    return importance


def _render_transparency_side_panel(metrics, training_info, threshold, type_metrics):
    detector_label = "LightGBM binary"
    type_label = "LightGBM + rules"
    threshold_text = _fmt_metric_value(threshold, precision=2)
    feature_count = training_info.get("n_features", 0)
    auc_text = _fmt_metric_value(metrics.get("auc"), precision=2)
    brier_text = _fmt_metric_value(metrics.get("brier"), precision=3)
    tau_text = _fmt_metric_value(type_metrics.get("tau"), precision=2)
    with st.container(border=True):
        st.markdown("#### Pipeline summary")
        st.write("Detect risk, explain the threat, then present a reviewable incident.")

        chip_cols = st.columns(3)
        chip_cols[0].caption("Detector")
        chip_cols[0].write(detector_label)
        chip_cols[1].caption("Type head")
        chip_cols[1].write(type_label)
        chip_cols[2].caption("Threshold")
        chip_cols[2].write(threshold_text)

        metric_cols_top = st.columns(2)
        metric_cols_top[0].metric("AUC", auc_text)
        metric_cols_top[1].metric("Brier", brier_text)
        metric_cols_bottom = st.columns(2)
        metric_cols_bottom[0].metric("Features", feature_count)
        metric_cols_bottom[1].metric("Type confidence τ", tau_text)

        st.markdown(
            "- **Detect anomaly**: the binary model scores each telemetry window.  \n"
            "- **Explain threat**: suspicious cases go to the type model plus rules.  \n"
            "- **Calibrate confidence**: thresholding and p-values reduce overconfident alerts.  \n"
            "- **Keep humans in control**: reviewers still approve, reject, or escalate incidents."
        )


def _render_model_transparency_card(nonce, role):
    metrics = st.session_state.get("metrics") or {}
    training_info = st.session_state.get("training_info") or {}
    type_metrics = st.session_state.get("type_metrics") or {}
    threshold = st.session_state.get("suggested_threshold") or st.session_state.get("th_slider")
    summary_role = _is_summary_role(role)

    st.markdown(
        dedent(
            """
        <div class="transparency-card">
            <div class="transparency-title">Model transparency card</div>
            <div class="transparency-copy">
                This demo uses a two-stage decision stack: a binary anomaly detector first decides whether behavior is suspicious,
                then an attack-type model plus domain rules explain what kind of threat is most likely.
            </div>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )

    flow = _model_decision_pipeline_figure()

    top_left, top_right = st.columns([1.26, 0.94], vertical_alignment="top")
    with top_left:
        st.plotly_chart(
            flow,
            use_container_width=True,
            config={"displayModeBar": False},
            key=f"transparency_flow_{nonce}",
        )
        st.markdown(
            '<div class="transparency-figure-note">Read top to bottom. The right-side lane activates only after suspicious behavior is detected.</div>',
            unsafe_allow_html=True,
        )
    with top_right:
        _render_transparency_side_panel(metrics, training_info, threshold, type_metrics)

    def render_technical_details():
        tabs = st.tabs(["How decisions are made", "What influences the model", "Current model settings"])

        with tabs[0]:
            st.caption("Decision walkthrough")
            decision_df = pd.DataFrame(
                [
                    {"step": "Input", "description": "Synthetic RF, network, GNSS, access, and integrity telemetry is collected per device."},
                    {"step": "Feature engineering", "description": "The app builds rolling-window mean/std/min/max/last/slope/z/jump features."},
                    {"step": "Anomaly score", "description": "A LightGBM binary classifier outputs anomaly probability for each device window."},
                    {"step": "Calibration", "description": "Conformal p-values and thresholding help convert raw probability into alert severity."},
                    {"step": "Attack typing", "description": "A multiclass LightGBM plus rules estimates Jamming, Breach, Spoof, or Tamper."},
                    {"step": "Final output", "description": "The incident card shows severity, type label, evidence features, and confidence context."},
                ]
            )
            st.dataframe(decision_df, width="stretch", hide_index=True)

        with tabs[1]:
            st.caption("Top feature drivers")
            importance = _get_global_importance_df()
            if importance is not None and len(importance) > 0:
                top_importance = importance.head(10)
                fig = px.bar(
                    top_importance.sort_values("mean_abs_shap"),
                    x="mean_abs_shap",
                    y="feature",
                    orientation="h",
                    title="Top features driving anomaly decisions",
                )
                st.plotly_chart(
                    style_plotly_figure(fig, height=340, show_legend=True),
                    use_container_width=True,
                    config={"displayModeBar": False},
                    key=f"transparency_top_features_{nonce}",
                )
            else:
                render_focus_callout("Model setup needed", "Run model setup to show the most influential features.", variant="warning")

        with tabs[2]:
            st.caption("Configuration snapshot")
            settings_df = pd.DataFrame(
                [
                    {"Setting": "Binary detector", "Value": "LightGBM classifier"},
                    {"Setting": "Attack type classifier", "Value": "LightGBM multiclass" if st.session_state.get("type_clf") is not None else "Rules fallback only"},
                    {"Setting": "Conformal calibration", "Value": "Enabled" if st.session_state.get("conformal_scores") is not None else "Not available"},
                    {"Setting": "Suggested threshold", "Value": f"{threshold:.2f}" if threshold is not None else "—"},
                    {"Setting": "Type fusion alpha", "Value": f"{type_metrics.get('alpha', '—')}"},
                    {"Setting": "Type confidence tau", "Value": f"{type_metrics.get('tau', '—')}"},
                    {"Setting": "Type margin delta", "Value": f"{type_metrics.get('delta', '—')}"},
                    {"Setting": "Training windows", "Value": training_info.get("n_windows", 0)},
                ]
            )
            settings_df["Value"] = settings_df["Value"].astype(str)
            st.table(settings_df)

    with st.expander("Open technical transparency detail", expanded=False):
        render_technical_details()

    render_section_card(
        "Stakeholder architecture view",
        "A simplified picture for regulators, executives, and non-technical reviewers showing where AI is used, where confidence is checked, and where humans remain in control.",
        kicker="Architecture lens",
    )

    left, right = st.columns([1.5, 1])
    with left:
        st.plotly_chart(
            _stakeholder_architecture_figure(),
            use_container_width=True,
            config={"displayModeBar": False},
            key=f"stakeholder_arch_{nonce}",
        )
    with right:
        with st.container(border=True):
            st.markdown("#### What this architecture shows")
            st.markdown(
                "- **Signals in:** the system collects synthetic operational telemetry.  \n"
                "- **AI decides risk:** the anomaly model estimates whether behavior is suspicious.  \n"
                "- **Confidence is checked:** thresholding and p-values reduce overconfident alerts.  \n"
                "- **Threat type is explained:** ML output is fused with domain rules.  \n"
                "- **Humans remain accountable:** reviewers approve, reject, or escalate incidents."
            )
            st.caption(
                "This is a decision-support architecture, not an autonomous enforcement system. Human review remains part of the control path."
            )


def render_insights_tab(role):
    nonce = st.session_state.ui_nonce
    summary_role = _is_summary_role(role)
    render_tab_intro("Insights", role)
    _render_role_summary(role)
    _render_model_transparency_card(nonce, role)
    render_section_card(
        "Technical evidence",
        "Open the diagnostics below when you want feature importance, calibration, and the feature glossary.",
        kicker="Deep dive",
    )

    def render_detailed_analysis():
        col1, col2 = st.columns(2)

        with col1:
            with st.container(border=True):
                st.markdown("#### Global importance")
                st.caption("Mean absolute SHAP values show which features influence anomaly decisions most across the dataset.")
                importance = _get_global_importance_df()
                if importance is not None and len(importance) > 0:
                    top_importance = importance.head(18)
                    fig = px.bar(top_importance, x="mean_abs_shap", y="feature", orientation="h", title="Global feature impact")
                    st.plotly_chart(
                        style_plotly_figure(fig, height=420),
                        use_container_width=True,
                        config={"displayModeBar": False},
                        key=f"global_importance_{nonce}",
                    )
                else:
                    render_focus_callout("Model setup needed", "Run model setup to view global importance.", variant="warning")

        with col2:
            with st.container(border=True):
                st.markdown("#### Calibration")
                st.caption("This curve compares model confidence with observed frequency so you can see whether probabilities are trustworthy.")
                evaluation = st.session_state.get("eval") or {}
                if "te_p" in evaluation and "y_test" in evaluation:
                    te_p = np.array(evaluation["te_p"])
                    y_test = np.array(evaluation["y_test"])
                    bins = np.linspace(0.0, 1.0, 11)
                    inds = np.digitize(te_p, bins) - 1
                    bin_p, bin_y = [], []
                    for bucket in range(10):
                        mask = inds == bucket
                        if np.any(mask):
                            bin_p.append(te_p[mask].mean())
                            bin_y.append(y_test[mask].mean())
                    if bin_p:
                        reliability = pd.DataFrame({"confidence": bin_p, "empirical": bin_y})
                        fig = px.line(
                            reliability,
                            x="confidence",
                            y="empirical",
                            title=f"Reliability (Brier {evaluation.get('brier', np.nan):.3f})",
                        )
                        fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", name="perfect")
                        st.plotly_chart(
                            style_plotly_figure(fig, height=420, show_legend=True),
                            use_container_width=True,
                            config={"displayModeBar": False},
                            key=f"calibration_curve_{nonce}",
                        )
                else:
                    render_focus_callout("Model setup needed", "Run model setup or refresh to view calibration.", variant="warning")

        with st.container(border=True):
            st.markdown("#### Feature glossary")
            st.caption("A quick reference for the base telemetry features that appear in the model explanations and engineered windows.")
            st.table(
                pd.DataFrame(
                    {
                        "Feature (base)": list(FEATURE_GLOSSARY.keys()),
                        "Meaning": [FEATURE_GLOSSARY[key] for key in FEATURE_GLOSSARY],
                    }
                )
            )

    with st.expander("Open model diagnostics and glossary", expanded=False):
        render_detailed_analysis()

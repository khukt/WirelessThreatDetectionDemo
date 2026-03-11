import time
from collections import deque

import numpy as np
import pandas as pd
import streamlit as st

from .config import CFG, DEVICE_TYPES, MOBILE_TYPES
from .helpers import rand_point_near
from .hitl import load_review_log, sync_legacy_labels


@st.cache_resource(show_spinner=False)
def model_store():
    return {}


def _seed_live_entities():
    lat0, lon0 = CFG.site_center
    ap_lat, ap_lon = rand_point_near(lat0, lon0, 50)
    jam_lat, jam_lon = rand_point_near(lat0, lon0, 100)
    rog_lat, rog_lon = rand_point_near(lat0, lon0, 80)
    spf_lat, spf_lon = rand_point_near(lat0, lon0, 120)

    devices = []
    for idx in range(CFG.n_devices):
        device_type = np.random.choice(DEVICE_TYPES, p=[0.45, 0.25, 0.20, 0.10])
        lat, lon = rand_point_near(lat0, lon0, CFG.site_radius_m)
        speed_mps = np.random.uniform(0.5, 2.5) if device_type in MOBILE_TYPES else 0.0
        devices.append(
            {
                "device_id": f"D{idx:03d}",
                "type": device_type,
                "lat": lat,
                "lon": lon,
                "speed_mps": speed_mps,
                "heading": np.random.uniform(0, 2 * np.pi),
                "active": True,
            }
        )

    return pd.DataFrame(devices), {"lat": ap_lat, "lon": ap_lon}, {"lat": jam_lat, "lon": jam_lon}, {"lat": rog_lat, "lon": rog_lon}, {"lat": spf_lat, "lon": spf_lon}


def reset_live_simulation():
    devices, ap, jammer, rogue, spoofer = _seed_live_entities()

    st.session_state.devices = devices
    st.session_state.ap = ap
    st.session_state.jammer = jammer
    st.session_state.rogue = rogue
    st.session_state.spoofer = spoofer
    st.session_state.tick = 0
    st.session_state.dev_buf = {
        row.device_id: deque(maxlen=CFG.rolling_len) for _, row in st.session_state.devices.iterrows()
    }
    st.session_state.last_features = {}
    st.session_state.latest_probs = {}
    st.session_state.fleet_records = deque(maxlen=CFG.max_plot_points)
    st.session_state.incidents = []
    st.session_state.group_incidents = []
    st.session_state.hitl_live_stats = {"suppressed_alerts": 0, "prioritized_alerts": 0, "last_effect": None}
    st.session_state.seq_counter = {
        row.device_id: 0 for _, row in st.session_state.devices.iterrows()
    }
    st.session_state.spoof_target_id = None
    st.session_state.ui_nonce = str(int(time.time()))


def init_state():
    devices, ap, jammer, rogue, spoofer = _seed_live_entities()

    st.session_state.devices = devices
    st.session_state.ap = ap
    st.session_state.jammer = jammer
    st.session_state.rogue = rogue
    st.session_state.spoofer = spoofer
    st.session_state.tick = 0
    st.session_state.dev_buf = {
        row.device_id: deque(maxlen=CFG.rolling_len) for _, row in st.session_state.devices.iterrows()
    }
    st.session_state.last_features = {}
    st.session_state.latest_probs = {}
    st.session_state.fleet_records = deque(maxlen=CFG.max_plot_points)
    st.session_state.incidents = []
    st.session_state.group_incidents = []
    st.session_state.incident_labels = {}
    st.session_state.review_log = load_review_log()
    sync_legacy_labels(st.session_state.review_log)
    st.session_state.hitl_live_stats = {"suppressed_alerts": 0, "prioritized_alerts": 0, "last_effect": None}
    st.session_state.suggested_threshold = None
    st.session_state.seq_counter = {
        row.device_id: 0 for _, row in st.session_state.devices.iterrows()
    }
    st.session_state.spoof_target_id = None
    st.session_state.ui_nonce = st.session_state.get("ui_nonce") or str(int(time.time()))

    defaults = {
        "model": None,
        "scaler": None,
        "explainer": None,
        "conformal_scores": None,
        "metrics": {},
        "baseline": None,
        "global_importance": None,
        "eval": {},
        "training_info": {},
        "type_clf": None,
        "type_cols": [],
        "type_labels": [],
        "type_explainer": None,
        "type_metrics": {},
        "suggested_threshold": None,
        "last_train_secs": None,
        "artifact_trained_at": None,
        "model_artifact_source": None,
        "latest_probs": {},
        "hitl_live_stats": {"suppressed_alerts": 0, "prioritized_alerts": 0, "last_effect": None},
        "hitl_suppression_enabled": CFG.hitl_suppression_enabled,
        "hitl_suppression_ticks": CFG.hitl_suppression_ticks,
        "hitl_escalation_boost": CFG.hitl_escalation_boost,
        "presentation_mode": False,
        "welcome_prompt_dismissed": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

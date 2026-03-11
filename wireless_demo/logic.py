import math
import time

import numpy as np
import pandas as pd
import streamlit as st

from .config import (
    CFG,
    MOBILE_TYPES,
    RAW_FEATURES,
    TYPE_ALPHA,
    TYPE_DELTA,
    TYPE_TAU,
)
from .helpers import (
    conformal_pvalue,
    haversine_m,
    meters_to_latlon_offset,
    rand_point_near,
    severity,
    shap_pos,
    time_of_day_load,
    to_df,
)


def update_positions(df):
    latc, lonc = CFG.site_center
    for idx in df.index:
        if df.at[idx, "type"] in MOBILE_TYPES:
            heading = df.at[idx, "heading"] + np.random.normal(0, 0.2)
            df.at[idx, "heading"] = heading
            step = df.at[idx, "speed_mps"] * np.random.uniform(0.6, 1.4)
            dn, de = step * math.cos(heading), step * math.sin(heading)
            dlat, dlon = meters_to_latlon_offset(dn, de, df.at[idx, "lat"])
            lat_new = df.at[idx, "lat"] + dlat
            lon_new = df.at[idx, "lon"] + dlon
            dist = haversine_m(lat_new, lon_new, latc, lonc)
            if dist > CFG.site_radius_m:
                df.at[idx, "heading"] = (heading + math.pi / 2) % (2 * math.pi)
            else:
                df.at[idx, "lat"] = lat_new
                df.at[idx, "lon"] = lon_new
    return df


def rf_and_network_model(
    row,
    tick,
    scen,
    tamper_mode=None,
    crypto_enabled=True,
    training=False,
    jam_mode=None,
    breach_mode=None,
    spoof_mode=None,
    spoof_mobile_only=True,
    spoof_target_id=None,
):
    if jam_mode is None:
        jam_mode = st.session_state.get("jam_mode")
    if breach_mode is None:
        breach_mode = st.session_state.get("breach_mode")
    if spoof_mode is None:
        spoof_mode = st.session_state.get("spoof_mode", "Localized area")
    if spoof_mobile_only is None:
        spoof_mobile_only = st.session_state.get("spoof_mobile_only", True)
    if spoof_target_id is None:
        spoof_target_id = st.session_state.get("spoof_target_id")
    cellular_mode = st.session_state.get("cellular_mode", False)

    ap = st.session_state.ap
    jam = st.session_state.jammer
    rogue = st.session_state.rogue
    spoofer = st.session_state.spoofer

    d_ap = max(1.0, haversine_m(row.lat, row.lon, ap["lat"], ap["lon"]))
    d_jam = haversine_m(row.lat, row.lon, jam["lat"], jam["lon"])
    d_rog = haversine_m(row.lat, row.lon, rogue["lat"], rogue["lon"])
    d_spf = haversine_m(row.lat, row.lon, spoofer["lat"], spoofer["lon"])
    load = time_of_day_load(tick)
    attack_active = False
    attack_type = "Normal"

    rssi = -40 - 18 * math.log10(d_ap) + np.random.normal(0, 2)
    rssi = float(np.clip(rssi, -90, -40))
    base_snr = 35 - 0.008 * d_ap + np.random.normal(0, 1.5)
    jam_penalty = 0.0

    noise_floor_dbm = -95 + 5 * load + np.random.normal(0, 1.5)
    cca_busy_frac = float(np.clip(0.20 * load + np.random.normal(0, 0.03), 0.0, 0.95))
    phy_error_rate = float(np.clip(np.random.beta(1, 60), 0.0, 0.3))
    beacon_miss_rate = float(np.clip(np.random.beta(1, 100), 0.0, 0.2))
    deauth_rate = float(np.clip(np.random.beta(1, 200), 0.0, 0.2))
    assoc_churn = float(np.clip(np.random.beta(1, 100), 0.0, 0.3))
    eapol_retry_rate = float(np.clip(np.random.beta(1, 120), 0.0, 0.5))
    dhcp_fail_rate = float(np.clip(np.random.beta(1, 200), 0.0, 1.0))
    rogue_rssi_gap = -30.0

    if cellular_mode:
        rsrp_dbm = float(np.clip(-65 - 20 * math.log10(d_ap / 50.0) + np.random.normal(0, 2.5), -120, -60))
        rsrq_db = float(np.clip(-3.0 - 0.003 * d_ap + np.random.normal(0, 1.0), -19, -3))
        sinr_db = float(np.clip(22 - 0.006 * d_ap + np.random.normal(0, 1.2), -5, 30))
        bler = float(np.clip(np.random.beta(1, 120), 0.0, 0.20))
        harq_nack_ratio = float(np.clip(np.random.beta(1, 100), 0.0, 0.30))
        rrc_reestablish = float(np.clip(np.random.beta(1, 200), 0.0, 0.10))
        rlf_count = float(np.clip(np.random.beta(1, 250), 0.0, 0.05))
        ho_fail_rate = float(np.clip(np.random.beta(1, 180), 0.0, 0.15))
        attach_reject_rate = float(np.clip(np.random.beta(1, 250), 0.0, 0.10))
        ta_anomaly = float(np.random.rand() < 0.01)
        pci_anomaly = float(np.random.rand() < 0.01)
    else:
        rsrp_dbm = -115.0
        rsrq_db = -18.0
        sinr_db = 0.0
        bler = harq_nack_ratio = rrc_reestablish = rlf_count = ho_fail_rate = attach_reject_rate = 0.0
        ta_anomaly = pci_anomaly = 0.0

    if str(scen).startswith("Jamming") and d_jam <= CFG.jam_radius_m:
        attack_active = True
        attack_type = "Jamming"
        reach = max(0.15, 1.0 - d_jam / CFG.jam_radius_m)
        if jam_mode == "Mgmt (deauth)":
            jam_mode = "Burst interference"
        if jam_mode == "Broadband noise" or jam_mode is None:
            bump = np.random.uniform(10, 22) * reach
            jam_penalty += bump
            noise_floor_dbm += bump * np.random.uniform(0.8, 1.1)
            if cellular_mode:
                sinr_db -= 0.9 * bump
                rsrq_db -= 2.5 * reach + np.random.uniform(0.5, 1.4)
                rsrp_dbm -= 4.0 * reach + np.random.uniform(0.0, 2.0)
                bler = float(np.clip(bler + 0.35 * reach + 0.18 * np.random.rand(), 0, 0.98))
                harq_nack_ratio = float(np.clip(harq_nack_ratio + 0.32 * reach + 0.12 * np.random.rand(), 0, 1.0))
                ho_fail_rate = float(np.clip(ho_fail_rate + 0.24 * reach, 0, 1.0))
                rlf_count = float(np.clip(rlf_count + 0.14 * reach + 0.05 * np.random.rand(), 0, 1.0))
                rrc_reestablish = float(np.clip(rrc_reestablish + 0.16 * reach + 0.05 * np.random.rand(), 0, 1.0))
            else:
                cca_busy_frac = float(np.clip(cca_busy_frac + 0.25 * reach + 0.15 * np.random.rand(), 0, 0.98))
                phy_error_rate = float(np.clip(phy_error_rate + 0.20 * reach + 0.10 * np.random.rand(), 0, 0.95))
                beacon_miss_rate = float(np.clip(beacon_miss_rate + 0.10 * reach + 0.10 * np.random.rand(), 0, 1.0))
        elif jam_mode == "Reactive":
            util = 0.4 + 0.5 * load
            bump = np.random.uniform(7, 16) * reach * util
            jam_penalty += bump
            noise_floor_dbm += bump * np.random.uniform(0.7, 1.0)
            if cellular_mode:
                sinr_db -= 0.75 * bump
                rsrq_db -= 2.0 * reach * util + np.random.uniform(0.4, 1.2)
                bler = float(np.clip(bler + 0.36 * reach * util + 0.12 * np.random.rand(), 0, 0.98))
                harq_nack_ratio = float(np.clip(harq_nack_ratio + 0.30 * reach * util + 0.12 * np.random.rand(), 0, 1.0))
                ho_fail_rate = float(np.clip(ho_fail_rate + 0.28 * reach * util, 0, 1.0))
                rlf_count = float(np.clip(rlf_count + 0.10 * reach * util, 0, 1.0))
            else:
                cca_busy_frac = float(np.clip(cca_busy_frac + 0.18 * reach * util + 0.07 * np.random.rand(), 0, 0.98))
                phy_error_rate = float(np.clip(phy_error_rate + 0.28 * reach * util, 0, 0.98))
        else:
            burst = np.random.uniform(5, 12) * reach
            jam_penalty += burst * np.random.uniform(0.6, 0.9)
            noise_floor_dbm += burst * np.random.uniform(0.5, 0.8)
            if cellular_mode:
                sinr_db -= 0.55 * burst
                rsrq_db -= 1.6 * reach + np.random.uniform(0.2, 0.8)
                bler = float(np.clip(bler + 0.22 * reach + 0.10 * np.random.rand(), 0, 0.92))
                ho_fail_rate = float(np.clip(ho_fail_rate + 0.18 * reach, 0, 1.0))
                harq_nack_ratio = float(np.clip(harq_nack_ratio + 0.16 * reach + 0.05 * np.random.rand(), 0, 1.0))
            else:
                cca_busy_frac = float(np.clip(cca_busy_frac + 0.12 * reach + 0.05 * np.random.rand(), 0, 0.95))
                phy_error_rate = float(np.clip(phy_error_rate + 0.14 * reach + 0.06 * np.random.rand(), 0, 0.90))
                beacon_miss_rate = float(np.clip(beacon_miss_rate + 0.10 * reach, 0, 1.0))

    snr = max(0.0, base_snr - jam_penalty)
    loss = 1 / (1 + np.exp(0.35 * (snr - 18))) + 0.18 * load + np.random.normal(0, 0.02)
    loss = float(np.clip(loss * 100, 0, 95))
    latency = float(max(5, 18 + 2.2 * loss + 28 * load + np.random.normal(0, 7)))
    jitter = float(max(0.3, 1.2 + 0.06 * loss + 9 * load + np.random.normal(0, 1.3)))
    throughput = float(max(0.5, 95 - 0.9 * loss - 45 * load + np.random.normal(0, 6)))
    channel_util = float(np.clip(100 * (0.4 + 0.5 * load) + 100 * (cca_busy_frac - 0.15) + np.random.normal(0, 5), 0, 100))

    if str(scen).startswith("Access Breach"):
        affect_wifi = row.type in {"AMR", "Sensor", "Gateway"}
        affect_cellular = row.type in {"Truck", "Gateway"}
        should_affect = (cellular_mode and affect_cellular) or ((not cellular_mode) and affect_wifi)
        if should_affect and d_rog <= CFG.breach_radius_m:
            if row.type in MOBILE_TYPES or np.random.rand() < 0.3:
                attack_active = True
                attack_type = "Breach"
                rogue_rssi = -40 - 18 * math.log10(max(1.0, d_rog)) + np.random.normal(0, 2)
                rogue_rssi_gap = float(rogue_rssi - rssi)
                mode = breach_mode or st.session_state.get("breach_mode", "Evil Twin")
                if mode == "Evil Twin":
                    if cellular_mode:
                        attach_reject_rate = float(np.clip(attach_reject_rate + np.random.uniform(0.25, 0.60), 0, 1.0))
                        ho_fail_rate = float(np.clip(ho_fail_rate + np.random.uniform(0.20, 0.40), 0, 1.0))
                        pci_anomaly = 1.0
                    else:
                        deauth_rate = float(np.clip(deauth_rate + np.random.uniform(0.25, 0.60), 0, 1.0))
                        assoc_churn = float(np.clip(assoc_churn + np.random.uniform(0.25, 0.50), 0, 1.0))
                        eapol_retry_rate = float(np.clip(eapol_retry_rate + np.random.uniform(0.10, 0.30), 0, 1.0))
                elif mode == "Rogue Open AP":
                    if cellular_mode:
                        rrc_reestablish = float(np.clip(rrc_reestablish + np.random.uniform(0.20, 0.40), 0, 1.0))
                    else:
                        assoc_churn = float(np.clip(assoc_churn + np.random.uniform(0.15, 0.35), 0, 1.0))
                        dhcp_fail_rate = float(np.clip(dhcp_fail_rate + np.random.uniform(0.25, 0.60), 0, 1.0))
                elif mode == "Deauth flood":
                    if cellular_mode:
                        rrc_reestablish = float(np.clip(rrc_reestablish + np.random.uniform(0.25, 0.50), 0, 1.0))
                        attach_reject_rate = float(np.clip(attach_reject_rate + np.random.uniform(0.10, 0.30), 0, 1.0))
                    else:
                        deauth_rate = float(np.clip(deauth_rate + np.random.uniform(0.45, 0.85), 0, 1.0))
                        assoc_churn = float(np.clip(assoc_churn + np.random.uniform(0.30, 0.60), 0, 1.0))
                        beacon_miss_rate = float(np.clip(beacon_miss_rate + np.random.uniform(0.08, 0.20), 0, 1.0))
                else:
                    if cellular_mode:
                        attach_reject_rate = float(np.clip(attach_reject_rate + np.random.uniform(0.35, 0.70), 0, 1.0))
                    else:
                        eapol_retry_rate = float(np.clip(eapol_retry_rate + np.random.uniform(0.35, 0.70), 0, 1.0))

    pos_error = np.random.normal(2.0, 0.7)
    gnss_sats = int(np.clip(np.random.normal(11, 2.0), 5, 18))
    gnss_hdop = float(np.clip(np.random.normal(1.0, 0.25), 0.6, 2.5))
    gnss_doppler_var = float(np.clip(np.random.normal(3.0, 0.8), 0.5, 8.0))
    gnss_clk_drift_ppm = float(np.clip(np.random.normal(0.10, 0.05), 0.0, 0.5))
    cno_mean_dbhz = float(np.clip(np.random.normal(38, 3.0), 25, 48))
    cno_std_dbhz = float(np.clip(np.random.normal(2.0, 0.8), 0.3, 6.0))

    if "seq_counter" not in st.session_state:
        st.session_state.seq_counter = {}
    if row.device_id not in st.session_state.seq_counter:
        st.session_state.seq_counter[row.device_id] = 0
    st.session_state.seq_counter[row.device_id] += 1

    device_ts = tick + np.random.normal(0, 0.05)
    payload_entropy = float(np.random.normal(5.8, 0.4))
    ts_skew_s = float(device_ts - tick)
    seq_gap = 0.0
    dup_ratio = 0.0
    schema_violation_rate = 0.0
    hmac_fail_rate = 0.0 if crypto_enabled else 0.0
    crc_err = int(np.random.poisson(0.2))

    if str(scen).startswith("Data Tamper") and row.type == "Gateway":
        attack_active = True
        attack_type = "Tamper"
        mode = tamper_mode
        if mode is None:
            mode = (
                np.random.choice(["Replay", "Constant injection", "Bias/Drift", "Bitflip/Noise", "Scale/Unit mismatch"])
                if training
                else "Replay"
            )
        if mode == "Replay":
            ts_skew_s += float(np.random.uniform(30, 120))
            dup_ratio += float(np.random.uniform(0.15, 0.50))
            seq_gap += float(np.random.uniform(0.10, 0.40))
            if crypto_enabled:
                hmac_fail_rate += float(np.random.uniform(0.6, 1.0))
        elif mode == "Constant injection":
            payload_entropy = float(np.random.uniform(1.0, 2.5))
            dup_ratio += float(np.random.uniform(0.20, 0.60))
            schema_violation_rate += float(np.random.uniform(0.05, 0.20))
            if crypto_enabled:
                hmac_fail_rate += float(np.random.uniform(0.3, 0.8))
        elif mode == "Bias/Drift":
            drift_amt = float(np.random.uniform(5, 15))
            throughput = max(1.0, throughput - drift_amt)
            latency += float(np.random.uniform(10, 30))
            payload_entropy = float(np.random.uniform(4.0, 5.0))
            schema_violation_rate += float(np.random.uniform(0.02, 0.08))
        elif mode == "Bitflip/Noise":
            payload_entropy = float(np.random.uniform(7.0, 8.0))
            crc_err += int(np.random.poisson(2))
            if crypto_enabled:
                hmac_fail_rate += float(np.random.uniform(0.5, 1.0))
        elif mode == "Scale/Unit mismatch":
            latency *= float(np.random.uniform(1.8, 3.0))
            schema_violation_rate += float(np.random.uniform(0.30, 0.70))
            payload_entropy = float(np.random.uniform(4.5, 6.0))

    spoof_hit = (
        spoof_mode == "Site-wide"
        or (spoof_mode == "Single device" and row.device_id == spoof_target_id)
        or (spoof_mode == "Localized area" and d_spf <= CFG.spoof_radius_m)
    )
    if str(scen).startswith("GPS Spoofing") and spoof_hit and (not spoof_mobile_only or row.type in MOBILE_TYPES):
        attack_active = True
        attack_type = "Spoof"
        minutes = tick / 60.0
        bias = 30.0
        drift = 8.0 * minutes
        scale = 1.0 if spoof_mode != "Localized area" else max(0.20, 1.0 - d_spf / CFG.spoof_radius_m)
        pos_error += scale * (np.random.uniform(0.6 * bias, 1.2 * bias) + 0.6 * drift)
        gnss_hdop = float(np.random.uniform(0.25, 0.5)) if np.random.rand() < 0.5 else float(np.random.uniform(2.5, 4.0))
        gnss_sats = int(np.random.randint(4, 8))
        gnss_doppler_var = float(np.random.uniform(4.5, 9.5))
        gnss_clk_drift_ppm = float(np.random.uniform(0.5, 1.5))
        if np.random.rand() < 0.5:
            cno_mean_dbhz = float(np.random.uniform(42, 47))
            cno_std_dbhz = float(np.random.uniform(0.2, 0.8))
        else:
            cno_mean_dbhz = float(np.random.uniform(28, 34))
            cno_std_dbhz = float(np.random.uniform(3.0, 6.0))

    return {
        "rssi": float(rssi),
        "snr": float(snr),
        "packet_loss": float(loss),
        "latency_ms": float(latency),
        "jitter_ms": float(jitter),
        "throughput_mbps": float(throughput),
        "channel_util": float(channel_util),
        "noise_floor_dbm": float(noise_floor_dbm),
        "phy_error_rate": float(phy_error_rate),
        "cca_busy_frac": float(cca_busy_frac),
        "beacon_miss_rate": float(beacon_miss_rate),
        "deauth_rate": float(deauth_rate),
        "assoc_churn": float(assoc_churn),
        "eapol_retry_rate": float(eapol_retry_rate),
        "dhcp_fail_rate": float(dhcp_fail_rate),
        "rogue_rssi_gap": float(rogue_rssi_gap),
        "pos_error_m": float(max(0.3, pos_error)),
        "gnss_sats": int(gnss_sats),
        "gnss_hdop": float(gnss_hdop),
        "gnss_doppler_var": float(gnss_doppler_var),
        "gnss_clk_drift_ppm": float(gnss_clk_drift_ppm),
        "cno_mean_dbhz": float(cno_mean_dbhz),
        "cno_std_dbhz": float(cno_std_dbhz),
        "rsrp_dbm": float(rsrp_dbm),
        "rsrq_db": float(rsrq_db),
        "sinr_db": float(sinr_db),
        "bler": float(bler),
        "harq_nack_ratio": float(harq_nack_ratio),
        "rrc_reestablish": float(rrc_reestablish),
        "rlf_count": float(rlf_count),
        "ho_fail_rate": float(ho_fail_rate),
        "attach_reject_rate": float(attach_reject_rate),
        "ta_anomaly": float(ta_anomaly),
        "pci_anomaly": float(pci_anomaly),
        "payload_entropy": float(np.clip(payload_entropy, 0.0, 8.0)),
        "ts_skew_s": float(ts_skew_s),
        "seq_gap": float(np.clip(seq_gap, 0.0, 1.0)),
        "dup_ratio": float(np.clip(dup_ratio, 0.0, 1.0)),
        "schema_violation_rate": float(np.clip(schema_violation_rate, 0.0, 1.0)),
        "hmac_fail_rate": float(np.clip(hmac_fail_rate, 0.0, 1.0)),
        "crc_err": int(max(0, crc_err)),
        "_attack_active": attack_active,
        "_attack_type": attack_type,
    }


def build_window_features(buffer_rows):
    df = pd.DataFrame(buffer_rows)
    if df.empty:
        return {}

    features = {}
    for feat in RAW_FEATURES:
        series = df[feat]
        features[f"{feat}_mean"] = series.mean()
        features[f"{feat}_std"] = series.std(ddof=0) if len(series) > 1 else 0.0
        features[f"{feat}_min"] = series.min()
        features[f"{feat}_max"] = series.max()
        features[f"{feat}_last"] = series.iloc[-1]
        if len(series) >= 3:
            x_axis = np.arange(len(series))
            features[f"{feat}_slope"] = float(np.polyfit(x_axis, series.values, 1)[0])
        else:
            features[f"{feat}_slope"] = 0.0
        mean_val = series.mean()
        std_val = series.std(ddof=0) if len(series) > 1 else 1.0
        features[f"{feat}_z"] = 0.0 if std_val == 0 else (series.iloc[-1] - mean_val) / std_val
        features[f"{feat}_jump"] = float(series.iloc[-1] - series.iloc[-2]) if len(series) >= 2 else 0.0
    return features


def feature_cols():
    cols = []
    aggs = ["mean", "std", "min", "max", "last", "slope", "z", "jump"]
    for raw_feature in RAW_FEATURES:
        for agg in aggs:
            cols.append(f"{raw_feature}_{agg}")
    return cols


def _select_type_bases():
    wifi_jam = ["snr", "noise_floor_dbm", "phy_error_rate", "cca_busy_frac", "packet_loss", "latency_ms", "jitter_ms"]
    cell_jam = ["sinr_db", "rsrp_dbm", "rsrq_db", "bler", "harq_nack_ratio", "assoc_churn", "packet_loss", "latency_ms"]
    breach = ["deauth_rate", "assoc_churn", "eapol_retry_rate", "dhcp_fail_rate", "rogue_rssi_gap", "beacon_miss_rate", "attach_reject_rate", "pci_anomaly"]
    spoof = ["pos_error_m", "gnss_hdop", "gnss_sats", "gnss_doppler_var", "gnss_clk_drift_ppm", "cno_mean_dbhz", "cno_std_dbhz"]
    tamper = ["hmac_fail_rate", "dup_ratio", "seq_gap", "ts_skew_s", "schema_violation_rate", "payload_entropy", "crc_err"]
    return sorted(set(wifi_jam + cell_jam + breach + spoof + tamper))


def cols_from_bases(all_cols, bases):
    return [col for col in all_cols if any(col.startswith(f"{base}_") for base in bases)]


def _z(feats, base):
    return float(feats.get(f"{base}_z", feats.get(f"{base}_last", 0.0)))


def _pos(feats, base):
    return float(feats.get(f"{base}_last", 0.0))


def _sigmoid(x, c=0.0, s=1.0):
    return float(1.0 / (1.0 + math.exp(-(x - c) / max(1e-6, s))))


def compute_rule_scores_from_feats(feats: dict, cellular_mode: bool) -> dict:
    if cellular_mode:
        jam_terms = [
            _sigmoid(-_z(feats, "sinr_db"), c=0.5, s=0.8),
            _sigmoid(_z(feats, "noise_floor_dbm"), c=0.8, s=0.8),
            _sigmoid(_z(feats, "bler"), c=0.4, s=0.5),
            _sigmoid(_z(feats, "harq_nack_ratio"), c=0.4, s=0.5),
            _sigmoid(_z(feats, "packet_loss"), c=0.6, s=0.7),
        ]
    else:
        jam_terms = [
            _sigmoid(-_z(feats, "snr"), c=0.5, s=0.8),
            _sigmoid(_z(feats, "noise_floor_dbm"), c=0.8, s=0.8),
            _sigmoid(_z(feats, "phy_error_rate"), c=0.5, s=0.7),
            _sigmoid(_z(feats, "cca_busy_frac"), c=0.5, s=0.7),
            _sigmoid(_z(feats, "packet_loss"), c=0.6, s=0.7),
        ]
    jam = float(np.clip(np.mean(jam_terms), 0, 1))

    breach_terms = [
        _sigmoid(_z(feats, "deauth_rate"), c=0.4, s=0.5),
        _sigmoid(_z(feats, "assoc_churn"), c=0.4, s=0.5),
        _sigmoid(_z(feats, "eapol_retry_rate"), c=0.35, s=0.5),
        _sigmoid(_z(feats, "dhcp_fail_rate"), c=0.35, s=0.5),
        _sigmoid(_pos(feats, "rogue_rssi_gap"), c=5.0, s=6.0),
        _sigmoid(_z(feats, "attach_reject_rate"), c=0.35, s=0.5),
        _sigmoid(_pos(feats, "pci_anomaly"), c=0.5, s=0.2),
    ]
    breach = float(np.clip(np.mean(breach_terms), 0, 1))

    hdop = _pos(feats, "gnss_hdop")
    hdop_weird = max(_sigmoid(2.2 - hdop, c=0.0, s=0.6), _sigmoid(hdop - 2.0, c=0.0, s=0.6))
    spoof_terms = [
        _sigmoid(_z(feats, "pos_error_m"), c=0.7, s=0.7),
        hdop_weird,
        _sigmoid(-_pos(feats, "gnss_sats"), c=-8.0, s=2.0),
        _sigmoid(_z(feats, "gnss_doppler_var"), c=0.6, s=0.7),
        _sigmoid(_z(feats, "gnss_clk_drift_ppm"), c=0.6, s=0.7),
        max(
            _sigmoid(_z(feats, "cno_std_dbhz"), c=0.6, s=0.7),
            _sigmoid(-_z(feats, "cno_std_dbhz"), c=-0.6, s=0.7),
        ),
    ]
    spoof = float(np.clip(np.mean(spoof_terms), 0, 1))

    tamper_terms = [
        _sigmoid(_z(feats, "hmac_fail_rate"), c=0.4, s=0.5),
        _sigmoid(_z(feats, "dup_ratio"), c=0.4, s=0.5),
        _sigmoid(_z(feats, "seq_gap"), c=0.35, s=0.5),
        _sigmoid(_z(feats, "ts_skew_s"), c=0.35, s=0.5),
        _sigmoid(_z(feats, "schema_violation_rate"), c=0.35, s=0.5),
        _sigmoid(_z(feats, "payload_entropy"), c=0.0, s=1.2),
    ]
    tamper = float(np.clip(np.mean(tamper_terms), 0, 1))

    vec = np.array([jam, breach, spoof, tamper], dtype=float)
    if np.all(vec == 0):
        vec = np.ones_like(vec) * 1e-6
    vec = vec / vec.sum()
    return {"Jamming": vec[0], "Breach": vec[1], "Spoof": vec[2], "Tamper": vec[3]}


def power_temp(probs: np.ndarray, gamma: float) -> np.ndarray:
    if probs.ndim == 1:
        probs = probs[None, :]
    powed = np.power(np.clip(probs, 1e-8, 1.0), 1.0 / max(1e-6, gamma))
    return powed / powed.sum(axis=1, keepdims=True)


def fit_power_temp(probs: np.ndarray, y_true_idx: np.ndarray) -> float:
    grid = [0.6, 0.8, 1.0, 1.2, 1.4]
    best_g, best_acc = 1.0, -1.0
    for gamma in grid:
        adjusted = power_temp(probs, gamma)
        acc = (adjusted.argmax(axis=1) == y_true_idx).mean()
        if acc > best_acc:
            best_acc, best_g = acc, gamma
    return float(best_g)


def feature_cols_cached():
    baseline = st.session_state.get("baseline")
    if baseline is not None:
        return list(baseline.columns)
    return feature_cols()


def tick_once(scenario, use_conformal):
    if st.session_state.get("model") is None:
        return

    st.session_state.devices = update_positions(st.session_state.devices.copy())
    tick = st.session_state.tick

    if st.session_state.spoof_target_id is None:
        st.session_state.spoof_target_id = np.random.choice(st.session_state.devices["device_id"])

    fleet_rows = []
    for _, row in st.session_state.devices.iterrows():
        metrics = rf_and_network_model(
            row,
            tick,
            scenario,
            tamper_mode=st.session_state.get("tamper_mode"),
            crypto_enabled=st.session_state.get("crypto_enabled", True),
            training=False,
            jam_mode=st.session_state.get("jam_mode"),
            breach_mode=st.session_state.get("breach_mode"),
            spoof_mode=st.session_state.get("spoof_mode", "Localized area"),
            spoof_mobile_only=st.session_state.get("spoof_mobile_only", True),
            spoof_target_id=st.session_state.get("spoof_target_id"),
        )
        metrics.pop("_attack_active", None)
        metrics.pop("_attack_type", None)

        st.session_state.dev_buf[row.device_id].append(metrics)
        fleet_rows.append({"tick": tick, "device_id": row.device_id, "type": row.type, "lat": row.lat, "lon": row.lon, **metrics})

    device_ids, feats_list = [], []
    for _, row in st.session_state.devices.iterrows():
        feats = build_window_features(st.session_state.dev_buf[row.device_id])
        if feats:
            st.session_state.last_features[row.device_id] = feats
            device_ids.append(row.device_id)
            feats_list.append(feats)

    incidents_this_tick = []
    st.session_state.latest_probs.clear()

    if feats_list:
        x_frame = pd.DataFrame(feats_list).fillna(0.0)
        cols = feature_cols_cached()
        x_frame = x_frame.reindex(columns=cols, fill_value=0.0)
        x_scaled = st.session_state.scaler.transform(x_frame)
        x_scaled_df = to_df(x_scaled, cols)
        probs = st.session_state.model.predict_proba(x_scaled_df)[:, 1]

        for device_id, prob in zip(device_ids, probs):
            st.session_state.latest_probs[device_id] = float(prob)

        idx_alert = np.where(probs >= CFG.threshold)[0]
        if len(idx_alert) > 0:
            expl_inputs = x_scaled_df.iloc[idx_alert]
            shap_vals = shap_pos(st.session_state.explainer, expl_inputs)
            shap_arr = np.array(shap_vals)
            if shap_arr.ndim == 1:
                shap_arr = shap_arr[:, None]

            for alert_idx, idx in enumerate(idx_alert):
                device_id = device_ids[idx]
                row = st.session_state.devices[st.session_state.devices["device_id"] == device_id].iloc[0]
                prob = float(probs[idx])
                p_value = conformal_pvalue(prob) if st.session_state.get("conformal_scores") is not None and use_conformal else None
                severity_label, _ = severity(prob, p_value)
                shap_vec = shap_arr[alert_idx]
                pairs = sorted(zip(cols, shap_vec), key=lambda kv: abs(kv[1]), reverse=True)[:6]

                type_label = "Unknown"
                type_conf = None
                type_pairs = []
                cellular_mode = st.session_state.get("cellular_mode", False)
                feats_win = st.session_state.last_features.get(device_id, {})
                rule_scores = compute_rule_scores_from_feats(feats_win, cellular_mode)
                rule_vec = np.array([rule_scores["Jamming"], rule_scores["Breach"], rule_scores["Spoof"], rule_scores["Tamper"]], dtype=float)
                full_classes = ["Breach", "Jamming", "Spoof", "Tamper"]
                order_map = {"Breach": 1, "Jamming": 0, "Spoof": 2, "Tamper": 3}

                if st.session_state.get("type_clf") is not None:
                    all_type_cols = st.session_state.type_cols
                    type_cols = [col for col in all_type_cols if col in cols]
                    xrow_full = x_scaled_df.iloc[[idx]]
                    xrow = xrow_full[type_cols] if type_cols else xrow_full
                    raw_probs_ml = st.session_state.type_clf.predict_proba(xrow)[0]
                    gamma = st.session_state.get("type_metrics", {}).get("temp_gamma", 1.0)
                    calibrated_probs_ml = power_temp(raw_probs_ml, gamma)[0]
                    trained_class_indices = [int(class_idx) for class_idx in getattr(st.session_state.type_clf, "classes_", np.arange(len(calibrated_probs_ml)))]

                    probs_ml = np.zeros(len(full_classes), dtype=float)
                    for prob_idx, class_idx in enumerate(trained_class_indices):
                        if 0 <= class_idx < len(full_classes):
                            probs_ml[class_idx] = calibrated_probs_ml[prob_idx]
                    if probs_ml.sum() <= 0:
                        probs_ml = np.ones(len(full_classes), dtype=float) / len(full_classes)
                    else:
                        probs_ml = probs_ml / probs_ml.sum()

                    classes = full_classes
                    rule_vec_ordered = np.array([rule_vec[order_map[cls]] for cls in classes], dtype=float)
                    fused = (1.0 - TYPE_ALPHA) * probs_ml + TYPE_ALPHA * rule_vec_ordered
                    fused = fused / fused.sum()

                    best_idx = int(np.argmax(fused))
                    top1 = float(fused[best_idx])
                    sorted_fused = np.sort(fused)[::-1]
                    margin = float(sorted_fused[0] - (sorted_fused[1] if len(sorted_fused) > 1 else 0.0))
                    raw_label = classes[best_idx]
                    if top1 >= TYPE_TAU and margin >= TYPE_DELTA:
                        type_label, type_conf = raw_label, top1
                    elif top1 >= 0.40:
                        type_label, type_conf = f"{raw_label} (low conf)", top1
                    else:
                        type_label, type_conf = "Unknown", top1

                    try:
                        type_explainer = st.session_state.get("type_explainer")
                        if type_explainer is not None and best_idx in trained_class_indices:
                            type_vals = type_explainer.shap_values(xrow)
                            shap_class_idx = trained_class_indices.index(best_idx)
                            if isinstance(type_vals, list) and len(type_vals) > shap_class_idx:
                                type_vec = type_vals[shap_class_idx][0]
                            else:
                                type_vec = type_vals[0]
                            type_pairs = sorted(zip(xrow.columns, type_vec), key=lambda kv: abs(kv[1]), reverse=True)[:6]
                    except Exception:
                        type_pairs = []
                else:
                    classes = full_classes
                    probs_ml = [0.25, 0.25, 0.25, 0.25]
                    rule_vec_ordered = np.array([rule_vec[1], rule_vec[0], rule_vec[2], rule_vec[3]], dtype=float)
                    fused = rule_vec_ordered / rule_vec_ordered.sum()
                    best_idx = int(np.argmax(fused))
                    type_label, type_conf = f"{classes[best_idx]} (rules)", float(fused[best_idx])
                    margin = None

                incident = {
                    "ts": int(time.time()),
                    "tick": int(tick),
                    "device_id": device_id,
                    "type": row.type,
                    "lat": float(row.lat),
                    "lon": float(row.lon),
                    "scenario": scenario,
                    "prob": float(prob),
                    "p_value": None if p_value is None else float(p_value),
                    "severity": severity_label,
                    "features": st.session_state.last_features.get(device_id, {}),
                    "reasons": [{"feature": key, "impact": float(val)} for key, val in pairs],
                    "type_label": type_label,
                    "type_conf": type_conf,
                    "type_reasons": [{"feature": key, "impact": float(val)} for key, val in type_pairs],
                    "type_probs_ml": probs_ml if isinstance(probs_ml, list) else probs_ml.tolist(),
                    "type_scores_rules": rule_vec_ordered if isinstance(rule_vec_ordered, list) else rule_vec_ordered.tolist(),
                    "type_probs_fused": fused if isinstance(fused, list) else fused.tolist(),
                    "type_classes": list(classes),
                    "type_margin": float(margin) if margin is not None else None,
                }

                from .hitl import get_device_review_effect

                review_effect = get_device_review_effect(device_id, scenario, tick)
                incident["review_status"] = review_effect["status"]
                incident["hitl_reason"] = review_effect.get("reason")
                incident["review_priority"] = "Escalated watch" if review_effect.get("prioritize") else "Standard"
                escalation_boost = float(st.session_state.get("hitl_escalation_boost", CFG.hitl_escalation_boost))
                incident["queue_score"] = float(prob + (escalation_boost if review_effect.get("prioritize") else 0.0))

                if review_effect.get("suppress"):
                    st.session_state.hitl_live_stats["suppressed_alerts"] += 1
                    st.session_state.hitl_live_stats["last_effect"] = {
                        "device_id": device_id,
                        "effect": "suppressed",
                        "reason": review_effect.get("reason"),
                        "tick": int(tick),
                    }
                    continue

                if review_effect.get("prioritize"):
                    st.session_state.hitl_live_stats["prioritized_alerts"] += 1
                    st.session_state.hitl_live_stats["last_effect"] = {
                        "device_id": device_id,
                        "effect": "prioritized",
                        "reason": review_effect.get("reason"),
                        "tick": int(tick),
                    }

                st.session_state.incidents.append(incident)
                incidents_this_tick.append(incident)

    if incidents_this_tick:
        affected = {incident["device_id"] for incident in incidents_this_tick}
        ratio = len(affected) / len(st.session_state.devices)
        if ratio >= 0.25:
            st.session_state.group_incidents.append(
                {
                    "ts": int(time.time()),
                    "tick": tick,
                    "scenario": scenario,
                    "affected": len(affected),
                    "fleet": len(st.session_state.devices),
                    "ratio": ratio,
                }
            )

    st.session_state.fleet_records.extend(fleet_rows)
    st.session_state.tick += 1

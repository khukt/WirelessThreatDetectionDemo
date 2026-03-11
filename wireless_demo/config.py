from dataclasses import dataclass

import numpy as np

SEED = 42
np.random.seed(SEED)


@dataclass
class Config:
    n_devices: int = 30
    rolling_len: int = 8
    max_plot_points: int = 1200
    threshold: float = 0.75
    coverage: float = 0.90
    n_estimators: int = 60
    max_depth: int = 3
    learning_rate: float = 0.08
    site_center: tuple = (62.4030, 17.3400)
    site_radius_m: float = 500
    jam_radius_m: float = 200
    breach_radius_m: float = 120
    spoof_radius_m: float = 250
    retrain_on_start: bool = False
    hitl_suppression_enabled: bool = True
    hitl_suppression_ticks: int = 25
    hitl_escalation_boost: float = 0.50


CFG = Config()
MODEL_KEY = "v3.1-sundsvall-mixed-profiles"

TYPE_TAU = 0.50
TYPE_DELTA = 0.10
TYPE_ALPHA = 0.40

DEVICE_TYPES = ["AMR", "Truck", "Sensor", "Gateway"]
MOBILE_TYPES = {"AMR", "Truck"}

RAW_FEATURES = [
    "rssi", "snr", "packet_loss", "latency_ms", "jitter_ms", "throughput_mbps", "channel_util",
    "noise_floor_dbm", "phy_error_rate", "cca_busy_frac", "beacon_miss_rate",
    "deauth_rate", "assoc_churn", "eapol_retry_rate", "dhcp_fail_rate", "rogue_rssi_gap",
    "pos_error_m", "gnss_sats", "gnss_hdop", "gnss_doppler_var", "gnss_clk_drift_ppm",
    "cno_mean_dbhz", "cno_std_dbhz",
    "rsrp_dbm", "rsrq_db", "sinr_db", "bler", "harq_nack_ratio",
    "rrc_reestablish", "rlf_count", "ho_fail_rate", "attach_reject_rate", "ta_anomaly", "pci_anomaly",
    "payload_entropy", "ts_skew_s", "seq_gap", "dup_ratio", "schema_violation_rate", "hmac_fail_rate", "crc_err",
]

FEATURE_AGG_SUFFIXES = ("_mean", "_std", "_min", "_max", "_last", "_slope", "_z", "_jump")

FEATURE_GLOSSARY = {
    "snr": "Signal-to-Noise Ratio (dB): higher is cleaner link; <10 dB is often unreliable.",
    "packet_loss": "Packet loss (%): higher means more delivery failures.",
    "latency_ms": "Network latency (ms): time for a packet round-trip; lower is better.",
    "jitter_ms": "Latency variation (ms): unstable delay; lower is smoother.",
    "pos_error_m": "GNSS position error (m): higher suggests spoofing or weak satellites.",
    "noise_floor_dbm": "RF noise floor (dBm): higher noise reduces usable SNR.",
    "cca_busy_frac": "Channel busy fraction: how often the medium is sensed busy.",
    "phy_error_rate": "PHY-layer error rate.",
    "beacon_miss_rate": "Missed AP beacons (Wi-Fi/private-5G).",
    "deauth_rate": "Deauthentication bursts.",
    "assoc_churn": "Association/roaming churn.",
    "eapol_retry_rate": "802.1X retries.",
    "dhcp_fail_rate": "DHCP failure rate.",
    "rogue_rssi_gap": "Rogue node signal − Legit signal: >0 = rogue more attractive.",
    "payload_entropy": "Payload entropy: randomness; extreme values can be suspicious.",
    "ts_skew_s": "Timestamp skew (s) vs wall clock: replay/stale hints.",
    "seq_gap": "Sequence gap ratio: missing counters/frames.",
    "dup_ratio": "Duplicate payloads: replay/reinjection symptoms.",
    "schema_violation_rate": "Payload schema violations: field types/units off.",
    "hmac_fail_rate": "Signature (HMAC) failures: integrity/auth mismatch.",
    "throughput_mbps": "Throughput (Mb/s): effective data rate.",
    "channel_util": "Channel utilization (%): how busy the medium is.",
    "rssi": "Received signal strength (dBm): higher is closer/clearer.",
    "crc_err": "CRC errors (count): integrity errors at frame level.",
    "gnss_sats": "Satellites used in fix (count): typical 8–14; sudden drops are suspicious.",
    "gnss_hdop": "Horizontal Dilution of Precision: geometry; <1 good, >2 poor.",
    "gnss_doppler_var": "Variance of Doppler residuals: inconsistency across satellites suggests spoofing.",
    "gnss_clk_drift_ppm": "Receiver clock drift (ppm): abnormal jumps suggest time spoof/replay.",
    "cno_mean_dbhz": "GNSS C/N₀ mean (dB-Hz): 30–45 typical; patterns shift under spoof/jam.",
    "cno_std_dbhz": "GNSS C/N₀ variability (dB-Hz): anomalous spread indicates manipulation.",
    "rsrp_dbm": "Cellular RSRP (dBm): stronger (closer to 0) is better.",
    "rsrq_db": "Reference Signal Received Quality (dB): higher is better.",
    "sinr_db": "Signal-to-Interference-plus-Noise Ratio (dB): higher is better.",
    "bler": "Block Error Rate: fraction of failed code blocks.",
    "harq_nack_ratio": "HARQ NACK ratio: retransmission demand.",
    "rrc_reestablish": "RRC re-establishments (rate).",
    "rlf_count": "Radio Link Failures (rate).",
    "ho_fail_rate": "Handover failure rate.",
    "attach_reject_rate": "Attach/registration reject rate.",
    "ta_anomaly": "Timing advance anomaly.",
    "pci_anomaly": "Unexpected Physical Cell ID changes.",
}

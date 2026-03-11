import math
import time
from collections import deque

import lightgbm as lgb
import numpy as np
import pandas as pd
import plotly.express as px
import shap
import streamlit as st
from lightgbm import LGBMClassifier
from sklearn.metrics import brier_score_loss, precision_recall_fscore_support, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from .config import CFG, DEVICE_TYPES, MOBILE_TYPES, MODEL_KEY, SEED, TYPE_ALPHA, TYPE_DELTA, TYPE_TAU
from .helpers import fmt_eta, meters_to_latlon_offset, rand_point_near, shap_pos, to_df
from .logic import (
    _select_type_bases,
    build_window_features,
    cols_from_bases,
    fit_power_temp,
    power_temp,
    rf_and_network_model,
)
from .persistence import save_model_artifacts
from .state import model_store


def log_train(message: str):
    timestamp = time.strftime("%H:%M:%S")
    st.session_state.training_logs = st.session_state.get("training_logs", [])
    st.session_state.training_logs.append({"t": timestamp, "msg": message})


def render_training_explainer(nonce: str):
    training_info = st.session_state.get("training_info", {})
    if not training_info:
        st.info("Train the model to see dataset and calibration details.")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Windows (total)", training_info.get("n_windows", 0))
    col2.metric("Devices (train gen)", training_info.get("n_devices", 0))
    col3.metric("Features used", training_info.get("n_features", 0))
    spw = training_info.get("scale_pos_weight")
    col4.metric("scale_pos_weight", f"{spw:.2f}" if spw is not None else "—")

    binary_dist = training_info.get("binary_distribution", {})
    if binary_dist:
        df_bin = pd.DataFrame({"class": list(binary_dist.keys()), "count": list(binary_dist.values())})
        st.plotly_chart(
            px.bar(df_bin, x="class", y="count", title="Binary class balance (Normal vs Anomaly)"),
            use_container_width=True,
            key=f"train_bin_{nonce}",
        )

    type_dist = training_info.get("type_distribution", {})
    if type_dist:
        df_type = pd.DataFrame({"type": list(type_dist.keys()), "count": list(type_dist.values())})
        st.plotly_chart(
            px.bar(
                df_type.sort_values("count", ascending=False),
                x="count",
                y="type",
                orientation="h",
                title="Attack-type balance (training positives)",
            ),
            use_container_width=True,
            key=f"train_type_{nonce}",
        )

    observed_classes = training_info.get("type_classes_observed", [])
    missing_classes = training_info.get("type_classes_missing", [])
    if observed_classes or missing_classes:
        observed_text = ", ".join(observed_classes) if observed_classes else "None"
        missing_text = ", ".join(missing_classes) if missing_classes else "None"
        st.markdown(
            f"- **Observed attack classes:** `{observed_text}`  \n"
            f"- **Missing attack classes:** `{missing_text}`"
        )

    metrics = st.session_state.get("metrics", {})
    if metrics:
        st.markdown(
            f"- **Calibration** (Brier): `{metrics.get('brier', float('nan')):.3f}`  \n"
            f"- **AUC**: `{metrics.get('auc', 0):.2f}` • **Precision**: `{metrics.get('precision', 0):.2f}` • "
            f"**Recall**: `{metrics.get('recall', 0):.2f}` • **F1**: `{metrics.get('f1', 0):.2f}`  \n"
            f"- **Suggested threshold**: `{st.session_state.get('suggested_threshold', CFG.threshold):.2f}`"
        )

    logs = st.session_state.get("training_logs", [])
    if logs:
        st.markdown("#### Training console")
        st.dataframe(pd.DataFrame(logs).tail(50), width="stretch")


def make_training_data(n_ticks=400, progress_cb=None, pct_start=0, pct_end=70):
    lat0, lon0 = CFG.site_center
    ap_lat, ap_lon = rand_point_near(lat0, lon0, 50)
    jam_lat, jam_lon = rand_point_near(lat0, lon0, 100)
    rog_lat, rog_lon = rand_point_near(lat0, lon0, 80)
    spf_lat, spf_lon = rand_point_near(lat0, lon0, 120)

    devices = []
    for idx in range(18):
        device_type = np.random.choice(DEVICE_TYPES, p=[0.5, 0.2, 0.2, 0.1])
        lat, lon = rand_point_near(lat0, lon0, CFG.site_radius_m)
        devices.append(
            {
                "device_id": f"T{idx:02d}",
                "type": device_type,
                "lat": lat,
                "lon": lon,
                "speed_mps": np.random.uniform(0.5, 2.5) if device_type in MOBILE_TYPES else 0.0,
                "heading": np.random.uniform(0, 2 * np.pi),
            }
        )
    fleet = pd.DataFrame(devices)

    if "seq_counter" not in st.session_state:
        st.session_state.seq_counter = {}
    for dev_id in fleet["device_id"]:
        st.session_state.seq_counter.setdefault(dev_id, 0)

    buffers = {device_id: deque(maxlen=CFG.rolling_len) for device_id in fleet.device_id}
    x_rows, y_values, labels = [], [], []
    type_counter = {"Jamming": 0, "Breach": 0, "Spoof": 0, "Tamper": 0}
    profile_counter = {"Yard": 0, "Road": 0}
    started = time.time()

    for tick in range(n_ticks):
        cellular_mode = bool(np.random.rand() < 0.5)
        st.session_state["cellular_mode"] = cellular_mode
        profile_counter["Road" if cellular_mode else "Yard"] += 1
        scen_code = np.random.choice(["Normal", "J", "Breach", "GPS", "Tamper"], p=[0.55, 0.15, 0.12, 0.10, 0.08])
        if scen_code == "J":
            scenario = "Jamming (localized)"
            jam_mode = np.random.choice(["Broadband noise", "Reactive", "Burst interference"])
            breach_mode = None
            spoof_mode = None
            spoof_mobile_only = True
            spoof_target_id = None
        elif scen_code == "Breach":
            scenario = "Access Breach (AP/gNB)"
            breach_mode = np.random.choice(["Evil Twin", "Rogue Open AP", "Credential hammer", "Deauth flood"])
            jam_mode = None
            spoof_mode = None
            spoof_mobile_only = True
            spoof_target_id = None
        elif scen_code == "GPS":
            scenario = "GPS Spoofing (subset)"
            jam_mode = breach_mode = None
            spoof_mode = np.random.choice(["Single device", "Localized area", "Site-wide"], p=[0.25, 0.55, 0.20])
            spoof_mobile_only = bool(np.random.rand() < 0.8)
            if spoof_mode == "Single device":
                candidate_ids = fleet["device_id"]
                if spoof_mobile_only:
                    mobile_ids = fleet.loc[fleet["type"].isin(MOBILE_TYPES), "device_id"]
                    if len(mobile_ids) > 0:
                        candidate_ids = mobile_ids
                spoof_target_id = np.random.choice(candidate_ids.to_numpy())
            else:
                spoof_target_id = None
        elif scen_code == "Tamper":
            scenario = "Data Tamper (gateway)"
            jam_mode = breach_mode = None
            spoof_mode = None
            spoof_mobile_only = True
            spoof_target_id = None
        else:
            scenario = "Normal"
            jam_mode = breach_mode = None
            spoof_mode = None
            spoof_mobile_only = True
            spoof_target_id = None

        for idx in fleet.index:
            if fleet.at[idx, "type"] in MOBILE_TYPES:
                fleet.at[idx, "heading"] += np.random.normal(0, 0.3)
                step = fleet.at[idx, "speed_mps"] * np.random.uniform(0.6, 1.4)
                dn, de = step * math.cos(fleet.at[idx, "heading"]), step * math.sin(fleet.at[idx, "heading"])
                dlat, dlon = meters_to_latlon_offset(dn, de, fleet.at[idx, "lat"])
                fleet.at[idx, "lat"] += dlat
                fleet.at[idx, "lon"] += dlon

        st.session_state.ap = {"lat": ap_lat, "lon": ap_lon}
        st.session_state.jammer = {"lat": jam_lat, "lon": jam_lon}
        st.session_state.rogue = {"lat": rog_lat, "lon": rog_lon}
        st.session_state.spoofer = {"lat": spf_lat, "lon": spf_lon}

        for _, row in fleet.iterrows():
            fake_row = type("R", (object,), row.to_dict())()
            metrics = rf_and_network_model(
                fake_row,
                tick,
                scenario,
                tamper_mode=None,
                crypto_enabled=bool(np.random.rand() < 0.7),
                training=True,
                jam_mode=jam_mode if "Jamming" in scenario else None,
                breach_mode=breach_mode if "Access Breach" in scenario else None,
                spoof_mode=spoof_mode,
                spoof_mobile_only=spoof_mobile_only,
                spoof_target_id=spoof_target_id,
            )
            attack_active = bool(metrics.pop("_attack_active", False))
            attack_type = metrics.pop("_attack_type", "Normal")
            buffers[row.device_id].append(metrics)
            feats = build_window_features(buffers[row.device_id])
            if feats:
                x_rows.append(feats)
                y_values.append(1 if attack_active else 0)
                labels.append(attack_type if attack_active else "Normal")
                if attack_active and attack_type in type_counter:
                    type_counter[attack_type] += 1

        if progress_cb:
            frac = (tick + 1) / n_ticks
            elapsed = time.time() - started
            eta = (elapsed / frac) * (1 - frac) if frac > 0 else None
            pct = pct_start + (pct_end - pct_start) * frac
            progress_cb(int(pct), f"Synthesizing windows {int(frac * 100)}%", eta)

    X = pd.DataFrame(x_rows).fillna(0.0)
    y = np.array(y_values)
    labels = np.array(labels)
    X_train, X_tmp, y_train, y_tmp, lab_train, lab_tmp = train_test_split(
        X, y, labels, test_size=0.40, random_state=SEED, shuffle=True, stratify=y
    )
    X_cal, X_test, y_cal, y_test, lab_cal, lab_test = train_test_split(
        X_tmp, y_tmp, lab_tmp, test_size=0.50, random_state=SEED, shuffle=True, stratify=y_tmp
    )

    binary_dist = {"Normal": int((np.array(y) == 0).sum()), "Anomaly": int((np.array(y) == 1).sum())}
    type_dist = {key: int(val) for key, val in type_counter.items() if val > 0}
    st.session_state.training_info = st.session_state.get("training_info", {})
    st.session_state.training_info.update(
        {
            "n_windows": int(len(X)),
            "n_devices": int(len(fleet)),
            "binary_distribution": binary_dist,
            "type_distribution": type_dist,
            "profile_distribution": profile_counter,
            "n_features": int(len(X.columns)),
        }
    )
    log_train(f"Data synthesized: windows={len(X)}, devices={len(fleet)}, anomaly={binary_dist['Anomaly']}")
    return (X_train, y_train, lab_train), (X_cal, y_cal, lab_cal), (X_test, y_test, lab_test), X, labels


def train_model_with_progress(n_ticks=350):
    bar = st.progress(0, text="Preparing training…")
    note = st.empty()
    console = st.empty()
    t_start = time.time()
    st.session_state.training_logs = []

    def update(pct, msg, eta=None):
        label = f"{msg} • ETA {fmt_eta(eta)}" if eta is not None else msg
        bar.progress(min(100, int(pct)), text=label)
        log_train(msg)
        logs_tail = st.session_state.training_logs[-6:]
        console.write("\n".join([f"[{entry['t']}] {entry['msg']}" for entry in logs_tail]))

    (X_train, y_train, _), (X_cal, y_cal, _), (X_test, y_test, _), X_all, labels_all = make_training_data(
        n_ticks=n_ticks, progress_cb=update, pct_start=0, pct_end=70
    )

    cols = list(X_train.columns)
    scaler = StandardScaler()
    Xtr = scaler.fit_transform(X_train)
    Xca = scaler.transform(X_cal)
    Xte = scaler.transform(X_test)
    Xall = scaler.transform(X_all)
    Xtr_df = to_df(Xtr, cols)
    Xca_df = to_df(Xca, cols)
    Xte_df = to_df(Xte, cols)
    Xall_df = to_df(Xall, cols)

    pos = max(1, int((y_train == 1).sum()))
    neg = max(1, int((y_train == 0).sum()))
    scale_pos_weight = float(neg / pos)
    st.session_state.training_info = st.session_state.get("training_info", {})
    st.session_state.training_info["scale_pos_weight"] = scale_pos_weight

    model = LGBMClassifier(
        n_estimators=CFG.n_estimators,
        max_depth=CFG.max_depth,
        learning_rate=CFG.learning_rate,
        subsample=0.9,
        colsample_bytree=0.9,
        min_child_samples=12,
        force_col_wise=True,
        verbosity=-1,
        random_state=SEED,
        scale_pos_weight=scale_pos_weight,
    )

    iter_started = time.time()
    total_iters = CFG.n_estimators

    def lgbm_progress_callback(env):
        iteration = max(0, min(total_iters, getattr(env, "iteration", 0)))
        frac = iteration / total_iters if total_iters > 0 else 1.0
        elapsed = time.time() - iter_started
        eta = (elapsed / frac) * (1 - frac) if frac > 0 else None
        pct = 70 + 20 * frac
        update(pct, f"Training trees {iteration}/{total_iters}", eta)

    update(70, "Starting model training…")
    model.fit(Xtr_df, y_train, callbacks=[lgb.log_evaluation(period=0), lgbm_progress_callback])

    update(90, "Calibrating confidence…")
    cal_probs = model.predict_proba(Xca_df)[:, 1]
    cal_nonconformity = 1 - np.where(y_cal == 1, cal_probs, 1 - cal_probs)

    update(93, "Evaluating detector…")
    test_probs = model.predict_proba(Xte_df)[:, 1]
    preds = (test_probs >= CFG.threshold).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(y_test, preds, average="binary", zero_division=0)
    auc = roc_auc_score(y_test, test_probs)
    brier = brier_score_loss(y_test, test_probs)

    thresholds = np.linspace(0.30, 0.90, 61)
    best_f1, best_threshold = 0.0, CFG.threshold
    for threshold in thresholds:
        pred = (test_probs >= threshold).astype(int)
        _, _, f1_candidate, _ = precision_recall_fscore_support(y_test, pred, average="binary", zero_division=0)
        if f1_candidate > best_f1:
            best_f1, best_threshold = f1_candidate, threshold
    st.session_state.suggested_threshold = float(best_threshold)

    update(95, "Training attack type classifier…")
    pos_mask = labels_all != "Normal"
    if np.any(pos_mask):
        bases = _select_type_bases()
        type_cols = cols_from_bases(cols, bases)
        X_pos = to_df(Xall[:, [cols.index(col) for col in type_cols]], type_cols)[pos_mask]
        y_pos_lbl = labels_all[pos_mask]
        classes = np.array(["Breach", "Jamming", "Spoof", "Tamper"])
        observed_labels = sorted(set(y_pos_lbl.tolist()))
        missing_labels = [label for label in classes.tolist() if label not in observed_labels]
        st.session_state.training_info["type_classes_observed"] = observed_labels
        st.session_state.training_info["type_classes_missing"] = missing_labels
        if missing_labels:
            log_train(
                "Attack type training note: missing classes in current synthetic sample -> "
                + ", ".join(missing_labels)
                + ". The multiclass model will train on observed classes only; rule fusion still covers all four output types."
            )
        y_idx = np.array([np.where(classes == label)[0][0] for label in y_pos_lbl])
        cls, cnt = np.unique(y_idx, return_counts=True)
        weight_map = {cls_idx: (1.0 / count) for cls_idx, count in zip(cls, cnt)}
        sample_weights = np.array([weight_map[i] for i in y_idx], dtype=float)

        X_tr_t, X_te_t, y_tr_t, y_te_t, sw_tr, _ = train_test_split(
            X_pos, y_idx, sample_weights, test_size=0.25, random_state=SEED, stratify=y_idx
        )
        type_clf = LGBMClassifier(
            objective="multiclass",
            num_class=len(classes),
            n_estimators=80,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            verbosity=-1,
            random_state=SEED,
        )
        type_clf.fit(X_tr_t, y_tr_t, sample_weight=sw_tr)
        probs_te = type_clf.predict_proba(X_te_t)
        gamma = fit_power_temp(probs_te, y_te_t)
        acc_raw = float((probs_te.argmax(axis=1) == y_te_t).mean())
        acc_adj = float((power_temp(probs_te, gamma).argmax(axis=1) == y_te_t).mean())
        type_explainer = shap.TreeExplainer(type_clf)

        st.session_state.type_clf = type_clf
        st.session_state.type_cols = type_cols
        st.session_state.type_labels = list(classes)
        st.session_state.type_explainer = type_explainer
        st.session_state.type_metrics = {
            "accuracy_raw": acc_raw,
            "accuracy_calibrated": acc_adj,
            "classes": list(classes),
            "classes_observed": observed_labels,
            "classes_missing": missing_labels,
            "tau": TYPE_TAU,
            "delta": TYPE_DELTA,
            "alpha": TYPE_ALPHA,
            "temp_gamma": gamma,
        }
    else:
        st.session_state.type_clf = None
        st.session_state.type_cols = []
        st.session_state.type_labels = []
        st.session_state.type_explainer = None
        st.session_state.type_metrics = {}
        st.session_state.training_info["type_classes_observed"] = []
        st.session_state.training_info["type_classes_missing"] = list(classes) if 'classes' in locals() else ["Breach", "Jamming", "Spoof", "Tamper"]

    st.session_state.model = model
    st.session_state.scaler = scaler
    st.session_state.explainer = shap.TreeExplainer(model)
    st.session_state.conformal_scores = cal_nonconformity
    st.session_state.metrics = {"precision": precision, "recall": recall, "f1": f1, "auc": auc, "brier": brier}
    st.session_state.baseline = Xall_df
    baseline_sample = Xall_df.sample(n=min(len(Xall_df), 600), random_state=SEED) if len(Xall_df) > 600 else Xall_df
    shap_mat = shap_pos(st.session_state.explainer, baseline_sample)
    mean_abs = np.abs(shap_mat).mean(axis=0)
    st.session_state.global_importance = (
        pd.DataFrame({"feature": baseline_sample.columns, "mean_abs_shap": mean_abs})
        .sort_values("mean_abs_shap", ascending=False)
        .reset_index(drop=True)
    )
    st.session_state.eval = {"y_test": y_test, "te_p": test_probs, "brier": brier}
    total_secs = time.time() - t_start
    st.session_state.last_train_secs = total_secs
    st.session_state.artifact_trained_at = int(time.time())
    st.session_state.model_artifact_source = "Fresh training"

    artifacts = {
        "trained_at": st.session_state.artifact_trained_at,
        "model": model,
        "scaler": scaler,
        "explainer": st.session_state.explainer,
        "conformal_scores": cal_nonconformity,
        "metrics": st.session_state.metrics,
        "baseline": Xall_df,
        "global_importance": st.session_state.global_importance,
        "eval": st.session_state.eval,
        "suggested_threshold": st.session_state.suggested_threshold,
        "type_clf": st.session_state.type_clf,
        "type_cols": st.session_state.type_cols,
        "type_labels": st.session_state.type_labels,
        "type_explainer": st.session_state.type_explainer,
        "type_metrics": st.session_state.type_metrics,
        "training_info": st.session_state.training_info,
    }
    store = model_store()
    store[MODEL_KEY] = artifacts
    save_model_artifacts(MODEL_KEY, artifacts)

    bar.progress(100, text=f"Training complete • {int(total_secs)}s")
    note.success(
        f"Model trained: AUC={auc:.2f}, Precision={precision:.2f}, Recall={recall:.2f} • "
        f"Brier={brier:.3f} • Duration {int(total_secs)}s • Suggested threshold={best_threshold:.2f}"
    )
    log_train(f"Training complete in {int(total_secs)}s (AUC={auc:.2f}, F1={f1:.2f}).")

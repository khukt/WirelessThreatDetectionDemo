from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Dict, Optional

import shap


DEMO_STATE_DIR = Path(__file__).resolve().parent.parent / ".demo_state"
BUNDLED_MODEL_CACHE_DIR = Path(__file__).resolve().parent / "assets" / "model_cache"


def _artifact_path(model_key: str) -> Path:
    safe_key = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in model_key)
    return DEMO_STATE_DIR / f"{safe_key}_artifacts.pkl"


def _bundled_artifact_path(model_key: str) -> Path:
    safe_key = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in model_key)
    return BUNDLED_MODEL_CACHE_DIR / f"{safe_key}_artifacts.pkl"


def save_model_artifacts(model_key: str, artifacts: Dict[str, Any]) -> Path:
    payload = dict(artifacts)
    payload.pop("explainer", None)
    payload.pop("type_explainer", None)
    path = _artifact_path(model_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return path


def load_model_artifacts(model_key: str) -> Optional[Dict[str, Any]]:
    candidates = (
        (_artifact_path(model_key), "Writable disk cache"),
        (_bundled_artifact_path(model_key), "Bundled startup cache"),
    )

    for path, source in candidates:
        if not path.exists():
            continue
        try:
            with path.open("rb") as handle:
                payload = pickle.load(handle)
        except Exception:
            continue
        hydrated = hydrate_model_artifacts(payload)
        hydrated["artifact_source"] = hydrated.get("artifact_source") or source
        return hydrated

    return None


def hydrate_model_artifacts(artifacts: Dict[str, Any]) -> Dict[str, Any]:
    hydrated = dict(artifacts)
    model = hydrated.get("model")
    type_clf = hydrated.get("type_clf")
    hydrated["explainer"] = shap.TreeExplainer(model) if model is not None else None
    hydrated["type_explainer"] = shap.TreeExplainer(type_clf) if type_clf is not None else None
    return hydrated

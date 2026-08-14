"""
services/prediction.py
------------------------
Loads the trained RandomForestClassifier (model.pkl) and predicts
Selected / Not Selected for a candidate application (Section 13).

Features (in this exact order, must match train_model.py):
    1. experience
    2. skills_count
    3. quiz_score
"""

import os
import pickle

FEATURE_ORDER = ["experience", "skills_count", "quiz_score"]

_model_cache = None
_model_path_cache = None


def _load_model(model_path):
    global _model_cache, _model_path_cache
    if _model_cache is not None and _model_path_cache == model_path:
        return _model_cache
    if not os.path.exists(model_path):
        return None
    with open(model_path, "rb") as f:
        _model_cache = pickle.load(f)
    _model_path_cache = model_path
    return _model_cache


def predict_outcome(model_path, experience, skills_count, quiz_score):
    """
    Returns dict:
        {
          "available": bool,
          "prediction": "Selected" | "Not Selected" | None,
          "probability": float | None,   # probability of "Selected"
          "error": str | None
        }
    """
    model = _load_model(model_path)
    if model is None:
        return {
            "available": False, "prediction": None, "probability": None,
            "error": "Prediction model (model.pkl) has not been trained yet. Run train_model.py.",
        }

    try:
        features = [[experience or 0, skills_count or 0, quiz_score or 0]]
        pred = model.predict(features)[0]
        proba = model.predict_proba(features)[0]
        # class 1 == "Selected"
        classes = list(model.classes_)
        selected_index = classes.index(1) if 1 in classes else 1
        probability = round(float(proba[selected_index]) * 100, 2)

        return {
            "available": True,
            "prediction": "Selected" if pred == 1 else "Not Selected",
            "probability": probability,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False, "prediction": None, "probability": None,
            "error": f"Prediction failed: {exc}",
        }

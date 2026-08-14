"""
train_model.py
----------------
Generates a synthetic training dataset (Section 14) and trains the
RandomForestClassifier used for hiring-outcome prediction (Section 13).

Run:
    python train_model.py

Outputs:
    model.pkl               - trained sklearn model
    model_metrics.json      - accuracy / precision / recall / CV accuracy
    static/images/feature_importance.png - feature importance bar chart

IMPORTANT: This dataset is entirely SYNTHETIC, generated for demonstration
purposes. It has NOT been validated against real hiring outcomes. See the
README "Limitations" section.
"""

import json
import os
import pickle
import random

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, precision_score, recall_score

from config import Config

RANDOM_SEED = 42
TOTAL_ROWS = 1000
SELECTED_ROWS = 350
NOT_SELECTED_ROWS = TOTAL_ROWS - SELECTED_ROWS  # 650


def generate_synthetic_dataset():
    """
    Build a synthetic dataset of (experience, skills_count, quiz_score, selected).

    Generation logic:
      - "Selected" candidates are sampled from distributions representing
        stronger profiles (more experience, more skills, higher quiz scores),
        plus label noise so the classes are not perfectly separable
        (making the model realistic rather than trivially perfect).
      - "Not Selected" candidates are sampled from weaker-profile
        distributions, also with noise.

    This keeps the dataset clearly synthetic and documented, matching the
    350 selected / 650 not-selected split required by the spec.
    """
    rng = np.random.default_rng(RANDOM_SEED)
    rows = []

    # Selected candidates: stronger profiles
    for _ in range(SELECTED_ROWS):
        experience = max(0, rng.normal(loc=4.5, scale=2.2))
        skills_count = max(0, int(round(rng.normal(loc=7.5, scale=2.0))))
        quiz_score = max(0, min(100, rng.normal(loc=75, scale=14)))
        label = 1
        # 10% label noise to keep the problem realistically imperfect
        if rng.random() < 0.10:
            label = 0
        rows.append([round(experience, 2), skills_count, round(quiz_score, 2), label])

    # Not selected candidates: weaker profiles
    for _ in range(NOT_SELECTED_ROWS):
        experience = max(0, rng.normal(loc=1.8, scale=1.6))
        skills_count = max(0, int(round(rng.normal(loc=3.5, scale=2.0))))
        quiz_score = max(0, min(100, rng.normal(loc=48, scale=18)))
        label = 0
        if rng.random() < 0.10:
            label = 1
        rows.append([round(experience, 2), skills_count, round(quiz_score, 2), label])

    random.Random(RANDOM_SEED).shuffle(rows)

    X = [[r[0], r[1], r[2]] for r in rows]
    y = [r[3] for r in rows]
    return X, y


def train_and_evaluate():
    X, y = generate_synthetic_dataset()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=RANDOM_SEED,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)

    cv_scores = cross_val_score(model, X, y, cv=5, scoring="accuracy")
    cv_accuracy = float(np.mean(cv_scores))

    feature_names = ["experience", "skills_count", "quiz_score"]
    importances = dict(zip(feature_names, model.feature_importances_.tolist()))

    metrics = {
        "dataset": {
            "total_rows": TOTAL_ROWS,
            "selected_rows": SELECTED_ROWS,
            "not_selected_rows": NOT_SELECTED_ROWS,
            "synthetic": True,
            "note": "This dataset is synthetically generated for demonstration only "
                    "and has not been validated against real hiring outcomes.",
        },
        "model_config": {
            "algorithm": "RandomForestClassifier",
            "n_estimators": 100,
            "max_depth": 10,
            "features": feature_names,
        },
        "metrics": {
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "cv_accuracy_5fold": round(cv_accuracy, 4),
        },
        "feature_importance": importances,
    }

    # Save model
    with open(Config.MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    # Save metrics
    with open(Config.MODEL_METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

    # Save feature importance chart
    os.makedirs(os.path.dirname(Config.FEATURE_IMPORTANCE_CHART), exist_ok=True)
    plt.figure(figsize=(6, 4))
    names = list(importances.keys())
    values = list(importances.values())
    plt.barh(names, values, color="#4f46e5")
    plt.xlabel("Importance")
    plt.title("Random Forest Feature Importance")
    plt.tight_layout()
    plt.savefig(Config.FEATURE_IMPORTANCE_CHART)
    plt.close()

    print("=" * 60)
    print("TalentLens AI - Random Forest Training Complete")
    print("=" * 60)
    print(f"Dataset: {TOTAL_ROWS} synthetic rows "
          f"({SELECTED_ROWS} selected / {NOT_SELECTED_ROWS} not selected)")
    print(f"Accuracy:            {metrics['metrics']['accuracy']*100:.2f}%")
    print(f"Precision:           {metrics['metrics']['precision']:.2f}")
    print(f"Recall:              {metrics['metrics']['recall']:.2f}")
    print(f"5-fold CV Accuracy:  {metrics['metrics']['cv_accuracy_5fold']*100:.2f}%")
    print(f"Feature importance:  {importances}")
    print(f"Model saved to:      {Config.MODEL_PATH}")
    print(f"Metrics saved to:    {Config.MODEL_METRICS_PATH}")
    print(f"Chart saved to:      {Config.FEATURE_IMPORTANCE_CHART}")
    print("=" * 60)
    print("NOTE: This model is trained on SYNTHETIC data for demonstration")
    print("purposes only. It has not been validated on real hiring behavior.")

    return metrics


if __name__ == "__main__":
    train_and_evaluate()

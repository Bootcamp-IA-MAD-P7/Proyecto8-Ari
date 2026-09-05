"""Tabular stroke-risk prediction.

Loads the tuned logistic pipeline and the one-hot encoder once, and exposes a
single `predict_tabular` function that takes a patient's raw fields and returns
a structured result. The model was trained on a specific column order; this
module reproduces the exact preprocessing recipe from notebook 02.
"""

from pathlib import Path

import joblib
import pandas as pd

# --- Constants from notebook 02 (the trained recipe) ---------------------------

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

THRESHOLD = 0.43  # chosen on OOF precision-recall curve, target recall ~0.90

# Columns dropped in the EDA (flat or age-proxy)
DROP_COLS = ["gender", "Residence_type", "ever_married", "work_type"]

# Final column order the pipeline was fitted on — MUST match exactly
FINAL_COLUMNS = [
    "age",
    "hypertension",
    "heart_disease",
    "avg_glucose_level",
    "bmi",
    "smoking_status_never smoked",
    "smoking_status_smokes",
    "smoking_status_formerly smoked",
]

# --- Load artifacts once at import time ----------------------------------------

_model = joblib.load(MODELS_DIR / "logistic_stroke.joblib")
_encoder = joblib.load(MODELS_DIR / "smoking_encoder.joblib")


# --- Public API ----------------------------------------------------------------

def predict_tabular(patient: dict) -> dict:
    """Predict stroke risk from a patient's tabular data.

    Parameters
    ----------
    patient : dict
        Raw patient fields, e.g.
        {"age": 67, "hypertension": 0, "heart_disease": 1,
         "avg_glucose_level": 228.7, "bmi": 36.6, "smoking_status": "smokes"}

    Returns
    -------
    dict
        {"probability": float, "prediction": int, "threshold": float}
    """
    # 1. one row DataFrame from the raw dict
    df = pd.DataFrame([patient])

    # 2. drop the columns discarded in the EDA
    df = df.drop(columns=DROP_COLS, errors="ignore")

    # 3. one-hot encode smoking_status with the saved encoder
    smk = _encoder.transform(df[["smoking_status"]])
    smk_cols = _encoder.get_feature_names_out(["smoking_status"])
    smk_df = pd.DataFrame(smk, columns=smk_cols, index=df.index)

    # 4. assemble features and enforce the exact trained column order
    df = df.drop(columns="smoking_status").join(smk_df)
    df = df[FINAL_COLUMNS]

    # 5. predict probability, then apply the clinical threshold
    proba = float(_model.predict_proba(df)[:, 1][0])
    prediction = int(proba >= THRESHOLD)

    return {"probability": proba, "prediction": prediction, "threshold": THRESHOLD}

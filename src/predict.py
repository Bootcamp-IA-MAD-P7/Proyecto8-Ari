"""Prediction orchestrator.

Single entry point for the app. Every patient goes through the tabular model;
only patients with a CT scan also go through the image model. Results are
reported side by side, never fused into a single verdict.
"""

from src.tabular import predict_tabular
from src.image import predict_image


def predict_patient(patient: dict, image_path=None) -> dict:
    """Run the available models for one patient and return both results.

    Parameters
    ----------
    patient : dict
        Raw patient fields for the tabular model (always required).
    image_path : str or Path, optional
        Path to a brain CT image. If None, the image model is skipped.

    Returns
    -------
    dict
        {
          "tabular": {"probability", "prediction", "threshold"},
          "image":   {"probability", "prediction", "threshold"} or None,
        }
    """
    result = {
        "tabular": predict_tabular(patient),
        "image": None,
    }

    if image_path is not None:
        result["image"] = predict_image(image_path)

    return result

"""Image stroke-risk prediction (brain CT).

Rebuilds the ResNet-50 architecture, loads the trained weights (state_dict from
notebook 03), and exposes `predict_image` which takes an image path and returns
a structured result. Preprocessing mirrors the exact v2 transform pipeline used
in training.
"""

from pathlib import Path

import torch
import torch.nn as nn
from PIL import Image
from torchvision import models
from torchvision.transforms import v2

# --- Constants from notebook 03 ------------------------------------------------

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

DEVICE = torch.device("cpu")

# ImageFolder assigned labels alphabetically: Normal -> 0, Stroke -> 1
CLASSES = ["Normal", "Stroke"]
STROKE_IDX = 1

# argmax over 2 classes == 0.5 threshold on the stroke probability.
# Kept at 0.5 to match the recall reported in notebook 03 (not a tuned value).
THRESHOLD = 0.5

# --- Preprocessing: same v2 pipeline as training -------------------------------

_transform = v2.Compose([
    v2.Resize((224, 224)),
    v2.Grayscale(num_output_channels=3),
    v2.ToImage(),
    v2.ToDtype(torch.float32, scale=True),
    v2.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

# --- Rebuild architecture and load trained weights (once) ----------------------

def _load_model():
    # weights=None: skip the ImageNet download; our state_dict overwrites everything
    model = models.resnet50(weights=None)
    model.fc = nn.Linear(model.fc.in_features, len(CLASSES))
    state = torch.load(MODELS_DIR / "cnn_resnet50_stroke.pth", map_location=DEVICE)
    model.load_state_dict(state)
    model.to(DEVICE)
    model.eval()
    return model


_model = _load_model()


# --- Public API ----------------------------------------------------------------

def predict_image(image_path) -> dict:
    """Predict stroke risk from a brain CT image.

    Parameters
    ----------
    image_path : str or Path
        Path to the image file (any mode; grayscale is handled).

    Returns
    -------
    dict
        {"probability": float, "prediction": int, "threshold": float}
        probability is P(Stroke); prediction is 1 (Stroke) or 0 (Normal).
    """
    img = Image.open(image_path)

    # transform -> [3, 224, 224], then add batch dim -> [1, 3, 224, 224]
    tensor = _transform(img).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        logits = _model(tensor)
        proba = torch.softmax(logits, dim=1)[0, STROKE_IDX].item()

    prediction = int(proba >= THRESHOLD)
    return {"probability": proba, "prediction": prediction, "threshold": THRESHOLD}

# ml_models/detect.py
# ============================================================
#  AutoHealz — YOLO Damage Detection
#  Returns list of dicts: { 'class': str, 'bbox': [x1,y1,x2,y2] }
#  so views.py can crop for BLIP and pass bbox area to severity logic.
# ============================================================

import os

os.environ["YOLO_CONFIG_DIR"] = "/tmp/Ultralytics"
from ultralytics import YOLO
# Load model only when required (Render memory fix)

_model = None


def get_model():

    global _model

    if _model is None:
        _model_path = os.path.join(
            os.path.dirname(__file__),
            "damage_model.pt"
        )

        _model = YOLO(_model_path)

        # CPU optimization
        _model.to("cpu")

    return _model


def detect_damage(image_path: str) -> list:
    """
    Run YOLO inference on image_path.

    Returns
    -------
    list of dicts:
        {
            'class' : str            — e.g. "front-bumper-dent"
            'bbox'  : [x1, y1, x2, y2]  — absolute pixel coords (int)
                      or None if unavailable
            'conf'  : float          — confidence score
        }

    Empty list if nothing detected.
    """
    model = get_model()

    print("YOLO starting inference")

    results = model.predict(
    source=image_path,
    conf=0.4,
    imgsz=320,
    fuse=False,
    device="cpu",
    verbose=False
   )

    print("YOLO completed")
    detections = []

    for r in results:
        for box in r.boxes:
            class_id   = int(box.cls[0])
            class_name = model.names[class_id]
            conf       = float(box.conf[0])

            # xyxy gives absolute pixel coords as tensor
            xyxy = box.xyxy[0].tolist()
            bbox = [int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])]

            detections.append({
                "class": class_name,
                "bbox" : bbox,
                "conf" : round(conf, 3),
            })

    return detections
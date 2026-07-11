# ml_models/knn_model.py
# ============================================================
#  AutoHealz — KNN Repair Cost Estimator
#  Dataset : autohealz1_dataset.csv  (18 Maruti Suzuki models)
#  Input   : car_model + YOLO class + BLIP caption + severity
#  Output  : estimated repair cost (₹) + breakdown dict
# ============================================================

import os
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from sklearn.neighbors import KNeighborsRegressor

# ── Global state (loaded once at server start) ──────────────
_knn        = None
le_model    = LabelEncoder()
le_part     = LabelEncoder()
le_damage   = LabelEncoder()
le_area     = LabelEncoder()

# ── Exact values present in the new dataset ─────────────────
VALID_MODELS = [
    'Alto 800', 'Alto K10', 'Baleno', 'Brezza', 'Celerio',
    'Dzire', 'Eeco', 'Ertiga', 'Fronx', 'Grand Vitara',
    'Ignis', 'Invicto', 'Jimny', 'S-Presso', 'Super Carry',
    'Swift', 'WagonR', 'XL6',
]

VALID_PARTS   = ["Bumper", "Door", "Fender", "Headlight", "Hood", "Windshield"]
VALID_DAMAGES = ["Broken", "Crack", "Dent", "Scratch", "Standard"]
VALID_AREAS   = ["Front", "General", "Rear", "Side"]


# ════════════════════════════════════════════════════════════
#  1.  MODEL LOADING  (lazy, once)
# ════════════════════════════════════════════════════════════
def get_model():
    """Load & train KNN lazily. Returns the fitted model or None on error."""
    global _knn

    if _knn is not None:
        return _knn

    try:
        base_dir     = os.path.dirname(
                           os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                       )
        dataset_path = os.path.join(base_dir, "autohealz1_dataset.csv")

        if not os.path.exists(dataset_path):
            raise FileNotFoundError(
                f"Dataset not found at: {dataset_path}\n"
                "Place autohealz1_dataset.csv in the same folder as manage.py."
            )

        df = pd.read_csv(dataset_path)

        df["car_model"]    = le_model.fit_transform(df["car_model"])
        df["damaged_part"] = le_part.fit_transform(df["damaged_part"])
        df["damage_type"]  = le_damage.fit_transform(df["damage_type"])
        df["area"]         = le_area.fit_transform(df["area"])

        X = df[["car_model", "damaged_part", "damage_type", "damage_level", "area"]]
        y = df["repair_cost"]

        model = KNeighborsRegressor(n_neighbors=5, weights="distance", metric="euclidean")
        model.fit(X, y)

        _knn = model
        print(f"[KNN] ✅ Model trained on {len(df)} samples across {df['car_model'].nunique()} models.")

    except Exception as exc:
        print(f"[KNN] ❌ LOAD ERROR: {exc}")
        _knn = None

    return _knn


# ════════════════════════════════════════════════════════════
#  2.  YOLO CLASS → DATASET FEATURE MAPPING
# ════════════════════════════════════════════════════════════
YOLO_TO_PART = {
    "front-bumper-dent" : ("Bumper",    "Front"),
    "rear-bumper-dent"  : ("Bumper",    "Rear"),
    "doorouter-dent"    : ("Door",      "Side"),
    "bonnet-dent"       : ("Hood",      "Front"),
    "headlight-damage"  : ("Headlight", "Front"),
    "taillight-damage"  : ("Headlight", "Rear"),
}

YOLO_TO_DAMAGE = {
    "front-bumper-dent" : "Dent",
    "rear-bumper-dent"  : "Dent",
    "doorouter-dent"    : "Dent",
    "bonnet-dent"       : "Dent",
    "headlight-damage"  : "Broken",
    "taillight-damage"  : "Broken",
}


# ════════════════════════════════════════════════════════════
#  3.  FEATURE EXTRACTION  (YOLO class + BLIP caption)
# ════════════════════════════════════════════════════════════
def extract_features(yolo_class: str, caption: str, severity: str = None):
    caption_lower = (caption or "").lower()
    yolo_lower    = (yolo_class or "").lower()

    # Part & Area — YOLO first
    if yolo_lower in YOLO_TO_PART:
        part, area = YOLO_TO_PART[yolo_lower]
    else:
        part = _part_from_text(yolo_lower) or _part_from_text(caption_lower) or "Bumper"
        area = _area_from_text(yolo_lower) or _area_from_text(caption_lower) or "Front"

    # Damage type — YOLO first, caption can upgrade
    if yolo_lower in YOLO_TO_DAMAGE:
        damage = YOLO_TO_DAMAGE[yolo_lower]
    else:
        damage = _damage_from_text(caption_lower) or "Dent"

    caption_damage = _damage_from_text(caption_lower)
    if caption_damage and caption_damage != damage:
        rank = {"Scratch": 1, "Dent": 2, "Crack": 3, "Broken": 4}
        if rank.get(caption_damage, 0) > rank.get(damage, 0):
            damage = caption_damage

    # Refine area from caption if YOLO didn't specify
    caption_area = _area_from_text(caption_lower)
    if caption_area and "front" not in yolo_lower and "rear" not in yolo_lower:
        area = caption_area

    # Damage level from severity
    level = _severity_to_level(severity)
    if "minor"    in caption_lower: level = 1
    if "moderate" in caption_lower: level = 2
    if "severe"   in caption_lower or "heavy" in caption_lower: level = 3

    return part, damage, level, area


def _part_from_text(text):
    if "bumper"     in text: return "Bumper"
    if "door"       in text: return "Door"
    if "fender"     in text: return "Fender"
    if "headlight"  in text: return "Headlight"
    if "taillight"  in text: return "Headlight"
    if "bonnet"     in text: return "Hood"
    if "hood"       in text: return "Hood"
    if "windshield" in text: return "Windshield"
    if "windscreen" in text: return "Windshield"
    if "glass"      in text: return "Windshield"
    return None

def _damage_from_text(text):
    if "scratch"  in text: return "Scratch"
    if "crack"    in text: return "Crack"
    if "broken"   in text: return "Broken"
    if "shatter"  in text: return "Broken"
    if "smash"    in text: return "Broken"
    if "dent"     in text: return "Dent"
    if "dented"   in text: return "Dent"
    return None

def _area_from_text(text):
    if "front"   in text: return "Front"
    if "rear"    in text: return "Rear"
    if "side"    in text: return "Side"
    if "general" in text: return "General"
    return None

def _severity_to_level(severity):
    if not severity: return 2
    s = severity.strip().lower()
    if s == "minor":    return 1
    if s == "moderate": return 2
    if s == "severe":   return 3
    return 2


# ════════════════════════════════════════════════════════════
#  4.  SAFE LABEL ENCODING
# ════════════════════════════════════════════════════════════
def _safe_encode(encoder: LabelEncoder, value: str) -> int:
    try:
        return int(encoder.transform([value])[0])
    except ValueError:
        lower_map = {c.lower(): c for c in encoder.classes_}
        if value.lower() in lower_map:
            return int(encoder.transform([lower_map[value.lower()]])[0])
        print(f"[KNN] ⚠️  Unseen label '{value}' — using index 0")
        return 0


# ════════════════════════════════════════════════════════════
#  5.  SINGLE PREDICTION
# ════════════════════════════════════════════════════════════
def predict_cost(car_model: str, yolo_class: str,
                 caption: str, severity: str = None) -> dict:
    """
    Predict repair cost for one detected damage.

    Parameters
    ----------
    car_model  : one of VALID_MODELS  e.g. "Swift", "Grand Vitara"
    yolo_class : YOLO label           e.g. "front-bumper-dent"
    caption    : BLIP caption string
    severity   : "Minor" | "Moderate" | "Severe"

    Returns dict with: part, damage_type, area, level, level_label,
                       estimated_cost   — or  error on failure.
    """
    try:
        model = get_model()
        if model is None:
            return {"error": "KNN model could not be loaded. Check dataset path."}

        # Normalise car model — title-case for safety
        car_model_clean = car_model.strip()
        if car_model_clean not in VALID_MODELS:
            print(f"[KNN] ⚠️  Unknown car model '{car_model}' — defaulting to 'Swift'")
            car_model_clean = "Swift"

        part, damage, level, area = extract_features(yolo_class, caption, severity)

        input_df = pd.DataFrame([{
            "car_model"   : _safe_encode(le_model,  car_model_clean),
            "damaged_part": _safe_encode(le_part,   part),
            "damage_type" : _safe_encode(le_damage, damage),
            "damage_level": level,
            "area"        : _safe_encode(le_area,   area),
        }])

        raw_cost       = model.predict(input_df)[0]
        estimated_cost = max(500, int(round(raw_cost, -2)))  # min ₹500, round to ₹100

        return {
            "part"          : part,
            "damage_type"   : damage,
            "area"          : area,
            "level"         : level,
            "level_label"   : {1: "Minor", 2: "Moderate", 3: "Severe"}.get(level, "Moderate"),
            "estimated_cost": estimated_cost,
        }

    except Exception as exc:
        print(f"[KNN] ❌ PREDICT ERROR: {exc}")
        return {"error": str(exc)}


# ════════════════════════════════════════════════════════════
#  6.  MULTI-DETECTION TOTAL  (called from views.py)
# ════════════════════════════════════════════════════════════
def predict_total_cost(car_model: str, detections: list) -> dict:
    """
    Run predict_cost() for every detection and sum them.

    Each detection dict needs:  'class', 'caption', 'severity'

    Returns:
        results     : list of per-detection prediction dicts
        total_cost  : int — sum of estimated_cost values
        error_count : int
    """
    results     = []
    total_cost  = 0
    error_count = 0

    for det in detections:
        result = predict_cost(
            car_model  = car_model,
            yolo_class = det.get("class", ""),
            caption    = det.get("caption", ""),
            severity   = det.get("severity", "Moderate"),
        )
        results.append(result)
        if "error" in result:
            error_count += 1
        else:
            total_cost += result["estimated_cost"]

    return {
        "results"    : results,
        "total_cost" : total_cost,
        "error_count": error_count,
    }
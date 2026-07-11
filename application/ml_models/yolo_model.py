# ml_models/yolo_model.py
import os
from ultralytics import YOLO
from PIL import Image

# =========================
# Load your trained YOLO model ONCE
# =========================
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'YOLOv8n.pt')  # make sure this is the correct trained file
model = YOLO(MODEL_PATH)  # only inference, load once at server start

# =========================
# Function to run YOLO on an image
# =========================
def run_yolo_on_image(image_path):
    """
    Run YOLO inference on a given image.
    Returns:
        result_image: path to saved image with bounding boxes
        partName: detected part name
        partDesc: damage description
        partCost: estimated cost
    """

    # Run prediction
    results = model.predict(image_path, conf=0.5, save=False)

    # Save annotated image
    annotated_image = results[0].plot()
    save_path = os.path.join('media', os.path.basename(image_path))
    Image.fromarray(annotated_image).save(save_path)

    # Extract detected parts
    labels = results[0].names
    detected_parts = [labels[int(cls)] for cls in results[0].boxes.cls]

    # Dummy cost mapping (replace with your ML/KNN later)
    cost_mapping = {
        'Bonnet': 40000,
        'Bumper': 25000,
        'Door': 20000,
        'Fender': 22000,
        'Headlight': 5000
    }

    if detected_parts:
        partName = detected_parts[0]
        partDesc = "major door damage"  # placeholder
        partCost = cost_mapping.get(partName, 8000)
    else:
        partName = partDesc = partCost = None

    return {
        'result_image': save_path,
        'partName': partName,
        'partDesc': partDesc,
        'partCost': partCost
    }

import os
import cv2
import json
from ultralytics import YOLO

# --- CONFIGURATION ---
BASE_PATH = os.getcwd()
IMG_DIR = os.path.join(BASE_PATH, "data/capas/images")
OUTPUT_DIR = os.path.join(BASE_PATH, "data/processed/image_analysis")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load a pre-trained Nano model (lightweight and fast)
model = YOLO('yolov8n.pt') 

def analyze_with_yolo(img_path):
    """
    Detects people in the image and returns their bounding boxes and counts.
    """
    try:
        # Load image via OpenCV to avoid path encoding issues
        img = cv2.imread(img_path)
        if img is None: return None

        # Run inference (classes=0 filters only for 'person')
        results = model.predict(source=img, classes=[0], conf=0.3, verbose=False)
        
        detections = []
        for r in results:
            for box in r.boxes:
                # Get coordinates and confidence
                coords = box.xyxy[0].tolist() # [x1, y1, x2, y2]
                conf = float(box.conf[0])
                
                detections.append({
                    "class": "person",
                    "confidence": round(conf, 2),
                    "bbox": [round(x, 1) for x in coords]
                })
        
        return {
            "total_people": len(detections),
            "detections": detections
        }
    except Exception as e:
        print(f"    [Error] YOLO failure on {os.path.basename(img_path)}: {e}")
        return None

# --- EXECUTION ---
image_files = [f for f in os.listdir(IMG_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

if not image_files:
    print("!!! No images found.")
else:
    print(f">>> Starting YOLOv8 Person Detection on {len(image_files)} images...")
    yolo_report = {}

    for i, img_name in enumerate(image_files):
        img_path = os.path.join(IMG_DIR, img_name)
        print(f"  [{i+1}/{len(image_files)}] Analyzing: {img_name}...")
        
        result = analyze_with_yolo(img_path)
        if result:
            yolo_report[img_name] = result

    # Save YOLO results
    output_file = os.path.join(OUTPUT_DIR, "yolo_person_detection.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(yolo_report, f, indent=4, ensure_ascii=False)

    print(f"\n>>> YOLO Analysis Complete! Saved to: {output_file}")
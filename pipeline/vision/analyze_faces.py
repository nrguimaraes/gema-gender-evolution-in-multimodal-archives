import os
import cv2
from deepface import DeepFace
import json

# --- CONFIGURATION ---
BASE_PATH = os.getcwd()
IMG_DIR = os.path.join(BASE_PATH, "data/capas/images")
OUTPUT_DIR = os.path.join(BASE_PATH, "data/processed/image_analysis")

# Ensure the output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

def analyze_image_robust(img_path):
    """
    Analyzes an image to detect faces, predict gender, and calculate 
    the spatial prominence (bounding box area percentage) of each face 
    relative to the entire magazine cover.
    """
    results = {"full_image": []}
    
    if not os.path.exists(img_path):
        print(f"    [Error] File not found: {img_path}")
        return None

    try:
        # Load image via OpenCV to handle path encoding issues seamlessly
        img_bgr = cv2.imread(img_path)
        if img_bgr is None:
            print(f"    [Error] OpenCV failed to load: {img_path}")
            return None
        
        # Calculate overall image dimensions to determine cover coverage area
        img_h, img_w, _ = img_bgr.shape
        total_pixels = img_w * img_h
        
        # Convert BGR (OpenCV standard) to RGB (DeepFace standard)
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        # Run DeepFace analysis using the robust RetinaFace backend
        analysis = DeepFace.analyze(
            img_path=img_rgb, 
            actions=['gender'], 
            enforce_detection=False, 
            detector_backend='retinaface'
        )
        
        if not isinstance(analysis, list):
            analysis = [analysis]

        summary = []
        for face in analysis:
            face_conf = face.get('face_confidence', 0)
            
            # Filter out weak/uncertain face detections
            if face_conf > 0.4:
                dominant_gender = face.get('dominant_gender')
                gender_data = face.get('gender', {})
                gender_conf = gender_data.get(dominant_gender, 0)

                # Extract spatial bounding box metadata provided by RetinaFace
                region = face.get('region', {})
                bx = region.get('x', 0)
                by = region.get('y', 0)
                bw = region.get('w', 0)
                bh = region.get('h', 0)
                
                # Calculate the area of the face bounding box and its percentage of the cover
                face_area = bw * bh
                coverage_pct = round((face_area / total_pixels) * 100, 2)

                summary.append({
                    "gender": dominant_gender,
                    "gender_confidence": round(float(gender_conf), 2),
                    "face_confidence": round(float(face_conf), 2),
                    "bbox": [bx, by, bx + bw, by + bh], # Standard format: [x1, y1, x2, y2]
                    "cover_coverage_percentage": coverage_pct # Metric for spatial prominence/protagonism
                })
        
        results["full_image"] = summary
        return results

    except Exception as e:
        print(f"    [Error] Critical failure on {os.path.basename(img_path)}: {e}")
        return None

# --- EXECUTION LOOP ---
valid_extensions = ('.jpg', '.jpeg', '.png')
image_files = [f for f in os.listdir(IMG_DIR) if f.lower().endswith(valid_extensions)]

if not image_files:
    print(f"!!! No images found in {IMG_DIR}.")
else:
    print(f">>> Starting Robust Vision Analysis with Prominence Metrics on {len(image_files)} images...")
    final_report = {}

    for i, img_name in enumerate(image_files):
        img_path = os.path.join(IMG_DIR, img_name)
        print(f"  [{i+1}/{len(image_files)}] Analyzing prominence on: {img_name}...")
        
        analysis_result = analyze_image_robust(img_path)
        
        if analysis_result:
            final_report[img_name] = analysis_result

    # Save outputs to the designated json file
    output_file = os.path.join(OUTPUT_DIR, "gender_vision_results_retinaface.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=4, ensure_ascii=False)

    print(f"\n>>> Analysis Complete! Enhanced results saved to: {output_file}")
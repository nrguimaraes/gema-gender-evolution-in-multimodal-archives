import os
import cv2
from deepface import DeepFace
import json

# --- CONFIGURATION ---
BASE_PATH = os.getcwd()
IMG_DIR = os.path.join(BASE_PATH, "data/capas/images")
OUTPUT_DIR = os.path.join(BASE_PATH, "data/processed/image_analysis")

os.makedirs(OUTPUT_DIR, exist_ok=True)

def analyze_image_robust(img_path):
    """
    Analyzes an image by loading it first with OpenCV to avoid 
    path encoding issues (non-english characters).
    """
    results = {"full_image": []}
    
    if not os.path.exists(img_path):
        print(f"    [Error] File not found: {img_path}")
        return None

    try:
        # Load image with OpenCV first to bypass path encoding errors
        img_bgr = cv2.imread(img_path)
        if img_bgr is None:
            print(f"    [Error] OpenCV failed to load: {img_path}")
            return None
        
        # Convert BGR (OpenCV) to RGB (DeepFace)
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        # Pass the image array (img_rgb) instead of the path string
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
            
            if face_conf > 0.4:
                dominant_gender = face.get('dominant_gender')
                gender_data = face.get('gender', {})
                gender_conf = gender_data.get(dominant_gender, 0)

                summary.append({
                    "gender": dominant_gender,
                    "gender_confidence": round(float(gender_conf), 2),
                    "face_confidence": round(float(face_conf), 2)
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
    print(f">>> Starting Robust Vision Analysis on {len(image_files)} images...")
    final_report = {}

    for i, img_name in enumerate(image_files):
        img_path = os.path.join(IMG_DIR, img_name)
        print(f"  [{i+1}/{len(image_files)}] Analyzing: {img_name}...")
        
        analysis_result = analyze_image_robust(img_path)
        
        if analysis_result:
            final_report[img_name] = analysis_result

    output_file = os.path.join(OUTPUT_DIR, "gender_vision_results_retinaface.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=4, ensure_ascii=False)

    print(f"\n>>> Analysis Complete! Results saved to: {output_file}")
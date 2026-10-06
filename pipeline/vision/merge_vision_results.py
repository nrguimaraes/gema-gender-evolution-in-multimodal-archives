import json
import os

# --- CONFIGURATION ---
BASE_PATH = os.getcwd()
INPUT_DIR = os.path.join(BASE_PATH, "data/processed/image_analysis")
OUTPUT_FILE = os.path.join(INPUT_DIR, "final_multimodal_vision_report.json")

def merge_results():
    # Load the two vision datasets
    yolo_path = os.path.join(INPUT_DIR, "yolo_person_detection.json")
    retina_path = os.path.join(INPUT_DIR, "gender_vision_results_retinaface.json")

    if not os.path.exists(yolo_path) or not os.path.exists(retina_path):
        print("Error: One or both vision JSON files are missing.")
        return

    with open(yolo_path, 'r', encoding='utf-8') as f:
        yolo_data = json.load(f)
    with open(retina_path, 'r', encoding='utf-8') as f:
        retina_data = json.load(f)

    final_report = {}

    # Iterate through all images found in YOLO (usually the most complete set)
    for img_name, yolo_info in yolo_data.items():
        total_detected = yolo_info.get("total_people", 0)
        
        # Get RetinaFace info for the same image
        retina_info = retina_data.get(img_name, {}).get("full_image", [])
        
        # Count identified genders
        men_count = sum(1 for face in retina_info if face.get("gender") == "Man")
        women_count = sum(1 for face in retina_info if face.get("gender") == "Woman")
        identified_total = men_count + women_count
        
        # Calculate "Indeterminate" (Detected as person by YOLO but no face found by RetinaFace)
        indeterminate_count = max(0, total_detected - identified_total)

        # Logic for predominant gender in the image
        if identified_total == 0:
            verdict = "Indeterminado (Sem faces claras)"
        elif women_count > men_count:
            verdict = "Feminino"
        elif men_count > women_count:
            verdict = "Masculino"
        else:
            verdict = "Misto/Equilibrado"

        final_report[img_name] = {
            "metrics": {
                "total_people_detected": total_detected,
                "men_identified": men_count,
                "women_identified": women_count,
                "indeterminate_presence": indeterminate_count
            },
            "verdict": verdict,
            "details": {
                "yolo_detections": yolo_info.get("detections", []),
                "face_detections": retina_info
            }
        }

    # Save the consolidated report
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_report, f, indent=4, ensure_ascii=False)
    
    print(f"Success! Consolidated report saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    merge_results()
"""
GEMA -- Pipeline Evaluation Script
Computes face detection recall using manual annotations from covers_manual_bbox.

Methodology:
  - Manual annotations = faces the pipeline missed (false negatives)
  - Pipeline detections are assumed correct (true positives)
  - Total real faces per cover = pipeline_detected + manually_annotated_missed
  - Recall = pipeline_detected / total_real_faces
  - Precision cannot be computed without explicit FP annotation

Run: python dashboard/eval_pipeline.py
"""

import os
from pymongo import MongoClient
import pandas as pd

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME   = "estagio_desporto"
SRC_COL   = "covers_analysis"
DEST_COL  = "covers_manual_bbox"

LABELS = {"a-bola": "A Bola", "o-jogo": "O Jogo", "record": "Record"}


def iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1); iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2); iy2 = min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0:
        return 0.0
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    return inter / (area_a + area_b - inter)


def main():
    db      = MongoClient(MONGO_URI)[DB_NAME]
    src_col = db[SRC_COL]
    ann_col = db[DEST_COL]

    annotations = list(ann_col.find({}))
    print(f"Annotated covers: {len(annotations)}\n")

    rows = []
    for ann in annotations:
        cover_id = ann.get("cover_id")
        source   = ann.get("source", "?")
        date     = str(ann.get("date", ""))[:10]

        # fetch pipeline doc -- _id is a string like "a-bola_2016-04-12.jpg"
        src_doc = src_col.find_one({"_id": cover_id})

        if src_doc is None:
            print(f"  WARNING: source doc not found for cover_id={cover_id}")
            continue

        pipeline_faces = src_doc.get("faces_detected", [])
        manual_faces   = ann.get("manual_faces", [])

        n_pipe   = len(pipeline_faces)
        n_missed = len(manual_faces)
        n_total  = n_pipe + n_missed
        recall   = n_pipe / n_total if n_total > 0 else None

        # gender breakdown -- pipeline
        pipe_w = sum(1 for f in pipeline_faces if f.get("gender") == "Woman")
        pipe_m = sum(1 for f in pipeline_faces if f.get("gender") == "Man")

        # gender breakdown -- missed
        miss_w = sum(1 for f in manual_faces if f.get("gender") == "Woman")
        miss_m = sum(1 for f in manual_faces if f.get("gender") == "Man")

        rows.append({
            "source":    source,
            "date":      date,
            "pipe_det":  n_pipe,
            "missed":    n_missed,
            "total":     n_total,
            "recall":    recall,
            "pipe_W":    pipe_w,
            "pipe_M":    pipe_m,
            "miss_W":    miss_w,
            "miss_M":    miss_m,
        })

    df = pd.DataFrame(rows).sort_values(["source", "date"])

    # ---------------------------------------------------------------------------
    # Per-cover table
    # ---------------------------------------------------------------------------
    print("=" * 70)
    print("PER-COVER RESULTS")
    print("=" * 70)
    fmt = "{:<10} {:<12} {:>8} {:>8} {:>8} {:>8}"
    print(fmt.format("Source", "Date", "Pipeline", "Missed", "Total", "Recall"))
    print("-" * 70)
    for _, r in df.iterrows():
        rec = f"{r['recall']:.1%}" if r['recall'] is not None else "N/A"
        print(fmt.format(
            LABELS.get(r["source"], r["source"]),
            r["date"],
            int(r["pipe_det"]),
            int(r["missed"]),
            int(r["total"]),
            rec,
        ))

    # ---------------------------------------------------------------------------
    # Per-newspaper aggregates
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("PER-NEWSPAPER AGGREGATES")
    print("=" * 70)
    fmt2 = "{:<10} {:>8} {:>8} {:>8} {:>8}"
    print(fmt2.format("Source", "Pipeline", "Missed", "Total", "Recall"))
    print("-" * 70)
    for src, grp in df.groupby("source"):
        tp = grp["pipe_det"].sum()
        fn = grp["missed"].sum()
        tot = tp + fn
        rec = tp / tot if tot > 0 else None
        rec_s = f"{rec:.1%}" if rec is not None else "N/A"
        print(fmt2.format(LABELS.get(src, src), int(tp), int(fn), int(tot), rec_s))

    # ---------------------------------------------------------------------------
    # Overall
    # ---------------------------------------------------------------------------
    tp_all  = df["pipe_det"].sum()
    fn_all  = df["missed"].sum()
    tot_all = tp_all + fn_all
    rec_all = tp_all / tot_all if tot_all > 0 else 0

    print("\n" + "=" * 70)
    print("OVERALL")
    print("=" * 70)
    print(f"  Pipeline detected : {int(tp_all)} faces")
    print(f"  Pipeline missed   : {int(fn_all)} faces (manually annotated)")
    print(f"  Total real faces  : {int(tot_all)}")
    print(f"  Face detection recall : {rec_all:.1%}")

    # ---------------------------------------------------------------------------
    # Gender breakdown (missed faces)
    # ---------------------------------------------------------------------------
    miss_w_tot = df["miss_W"].sum()
    miss_m_tot = df["miss_M"].sum()
    pipe_w_tot = df["pipe_W"].sum()
    pipe_m_tot = df["pipe_M"].sum()

    print("\n" + "=" * 70)
    print("GENDER BREAKDOWN")
    print("=" * 70)
    print(f"  Pipeline  -- Women: {int(pipe_w_tot)}  Men: {int(pipe_m_tot)}")
    print(f"  Missed    -- Women: {int(miss_w_tot)}  Men: {int(miss_m_tot)}")

    tot_w = pipe_w_tot + miss_w_tot
    tot_m = pipe_m_tot + miss_m_tot
    rec_w = pipe_w_tot / tot_w if tot_w > 0 else None
    rec_m = pipe_m_tot / tot_m if tot_m > 0 else None
    print(f"  Recall Women : {rec_w:.1%}" if rec_w is not None else "  Recall Women : N/A")
    print(f"  Recall Men   : {rec_m:.1%}" if rec_m is not None else "  Recall Men   : N/A")

    print("\nNote: precision cannot be computed without explicit false-positive")
    print("annotation. Assumes all pipeline detections are true positives.")


if __name__ == "__main__":
    main()

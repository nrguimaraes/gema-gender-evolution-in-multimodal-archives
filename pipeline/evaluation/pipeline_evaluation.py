"""
GEMA — Women's Representation in Portuguese Sports Media
Pipeline end-to-end evaluation script.

Connects to MongoDB and prints a quality report covering:
- Text classification volume and rate
- Visual face detection confidence distribution
- NER entity counts
- Data integrity checks

Usage:
    python evaluation/pipeline_evaluation.py
    python evaluation/pipeline_evaluation.py --output evaluation/report.txt
    python evaluation/pipeline_evaluation.py --csv evaluation/metrics.csv
"""
import argparse
import csv
import os
import sys
import time
from datetime import datetime

from pymongo import MongoClient

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://172.17.16.1:27017/")
DB_NAME = "estagio_desporto"

SEPARATOR = "=" * 70


def connect(uri: str = MONGO_URI):
    """Connect to MongoDB and verify the connection with a ping."""
    client = MongoClient(uri, serverSelectionTimeoutMS=8000)
    client.admin.command("ping")
    return client[DB_NAME]


# ---------------------------------------------------------------------------
# Metric collectors
# ---------------------------------------------------------------------------

def metric_text_pipeline(db) -> dict:
    """Volume and classification rate for the articles_final collection."""
    t0 = time.perf_counter()

    total_raw = db["articles_final"].count_documents({})

    classified = db["articles_final"].count_documents({
        "$or": [
            {"gender_analysis.verdict": {"$exists": True, "$ne": None}},
            {"gender_analysis.dominant_gender": {"$exists": True, "$ne": None}},
        ]
    })

    gender_pipeline = [
        {"$group": {
            "_id": {
                "$ifNull": [
                    "$gender_analysis.verdict",
                    "$gender_analysis.dominant_gender",
                    "Unknown"
                ]
            },
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}},
    ]
    gender_breakdown = {
        r["_id"]: r["count"]
        for r in db["articles_final"].aggregate(gender_pipeline)
    }

    year_pipeline = [
        {"$group": {"_id": "$year", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    year_breakdown = {
        r["_id"]: r["count"]
        for r in db["articles_final"].aggregate(year_pipeline)
    }

    elapsed = time.perf_counter() - t0
    return {
        "section": "TEXT — articles_final",
        "total_raw_articles": total_raw,
        "classified_articles": classified,
        "unclassified_articles": total_raw - classified,
        "classification_rate_pct": round(classified / total_raw * 100, 2) if total_raw else 0,
        "gender_breakdown": gender_breakdown,
        "year_breakdown": year_breakdown,
        "query_time_s": round(elapsed, 3),
    }


def metric_visual_pipeline(db) -> dict:
    """Face detection volume and gender confidence distribution from covers_analysis."""
    t0 = time.perf_counter()

    total_covers = db["covers_analysis"].count_documents({})

    agg = list(db["covers_analysis"].aggregate([
        {"$unwind": "$faces_detected"},
        {"$group": {
            "_id": None,
            "total_faces": {"$sum": 1},
            "high_conf": {
                "$sum": {"$cond": [{"$gte": ["$faces_detected.gender_confidence", 0.90]}, 1, 0]}
            },
            "mid_conf": {
                "$sum": {"$cond": [
                    {"$and": [
                        {"$gte": ["$faces_detected.gender_confidence", 0.70]},
                        {"$lt":  ["$faces_detected.gender_confidence", 0.90]},
                    ]}, 1, 0
                ]}
            },
            "low_conf": {
                "$sum": {"$cond": [{"$lt": ["$faces_detected.gender_confidence", 0.70]}, 1, 0]}
            },
            "avg_conf": {"$avg": "$faces_detected.gender_confidence"},
            "man_count":   {"$sum": {"$cond": [{"$eq": ["$faces_detected.gender", "Man"]},   1, 0]}},
            "woman_count": {"$sum": {"$cond": [{"$eq": ["$faces_detected.gender", "Woman"]}, 1, 0]}},
        }}
    ], allowDiskUse=True))

    conf = agg[0] if agg else {
        "total_faces": 0, "high_conf": 0, "mid_conf": 0, "low_conf": 0,
        "avg_conf": 0, "man_count": 0, "woman_count": 0,
    }

    newspaper_pipeline = [
        {"$unwind": "$faces_detected"},
        {"$group": {
            "_id": "$source",
            "faces": {"$sum": 1},
            "women": {"$sum": {"$cond": [{"$eq": ["$faces_detected.gender", "Woman"]}, 1, 0]}},
        }},
        {"$sort": {"faces": -1}},
    ]
    newspaper_breakdown = {
        r["_id"]: {"faces": r["faces"], "women": r["women"]}
        for r in db["covers_analysis"].aggregate(newspaper_pipeline, allowDiskUse=True)
    }

    elapsed = time.perf_counter() - t0
    total = conf["total_faces"] or 1
    return {
        "section": "VISUAL — covers_analysis",
        "total_covers_processed": total_covers,
        "total_faces_detected": conf["total_faces"],
        "man_faces": conf["man_count"],
        "woman_faces": conf["woman_count"],
        "female_visual_pct": round(conf["woman_count"] / total * 100, 2),
        "avg_gender_confidence": round(conf["avg_conf"], 4),
        "high_confidence_faces": conf["high_conf"],
        "mid_confidence_faces": conf["mid_conf"],
        "low_confidence_faces": conf["low_conf"],
        "high_conf_rate_pct": round(conf["high_conf"] / total * 100, 2),
        "low_conf_rate_pct": round(conf["low_conf"] / total * 100, 2),
        "newspaper_breakdown": newspaper_breakdown,
        "query_time_s": round(elapsed, 3),
    }


def metric_ner(db) -> dict:
    """Unique entity counts and top-10 lists from NER protagonists."""
    t0 = time.perf_counter()

    def _unique_count(gender_key: str) -> int:
        pipeline = [
            {"$unwind": {
                "path": f"$gender_analysis.details.protagonists.{gender_key}",
                "preserveNullAndEmptyArrays": False,
            }},
            {"$group": {"_id": f"$gender_analysis.details.protagonists.{gender_key}"}},
            {"$count": "n"},
        ]
        result = list(db["articles_final"].aggregate(pipeline, allowDiskUse=True))
        return result[0]["n"] if result else 0

    def _top_entities(gender_key: str, n: int = 10) -> list:
        pipeline = [
            {"$unwind": {
                "path": f"$gender_analysis.details.protagonists.{gender_key}",
                "preserveNullAndEmptyArrays": False,
            }},
            {"$group": {
                "_id": f"$gender_analysis.details.protagonists.{gender_key}",
                "count": {"$sum": 1},
            }},
            {"$sort": {"count": -1}},
            {"$limit": n},
        ]
        return [(r["_id"], r["count"]) for r in db["articles_final"].aggregate(pipeline, allowDiskUse=True)]

    unique_f = _unique_count("feminine")
    unique_m = _unique_count("masculine")
    top_f = _top_entities("feminine")
    top_m = _top_entities("masculine")

    elapsed = time.perf_counter() - t0
    return {
        "section": "NER — articles_final",
        "unique_feminine_entities": unique_f,
        "unique_masculine_entities": unique_m,
        "total_unique_entities": unique_f + unique_m,
        "top10_feminine": top_f,
        "top10_masculine": top_m,
        "query_time_s": round(elapsed, 3),
    }


def metric_data_integrity(db) -> dict:
    """Count documents with missing critical fields in both collections."""
    t0 = time.perf_counter()

    missing_year = db["articles_final"].count_documents({"year": {"$exists": False}})
    missing_body = db["articles_final"].count_documents({"body_text": {"$exists": False}})
    missing_ga   = db["articles_final"].count_documents({"gender_analysis": {"$exists": False}})
    total        = db["articles_final"].count_documents({})

    covers_missing_faces = db["covers_analysis"].count_documents({
        "$or": [
            {"faces_detected": {"$exists": False}},
            {"faces_detected": {"$size": 0}},
        ]
    })
    total_covers = db["covers_analysis"].count_documents({})

    elapsed = time.perf_counter() - t0
    return {
        "section": "DATA INTEGRITY",
        "articles_missing_year": missing_year,
        "articles_missing_body": missing_body,
        "articles_missing_gender_analysis": missing_ga,
        "articles_integrity_pct": round((1 - missing_ga / total) * 100, 2) if total else 0,
        "covers_with_no_faces": covers_missing_faces,
        "covers_total": total_covers,
        "covers_integrity_pct": round((1 - covers_missing_faces / total_covers) * 100, 2) if total_covers else 0,
        "query_time_s": round(elapsed, 3),
    }


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def _fmt_section(title: str) -> str:
    return f"\n{SEPARATOR}\n  {title}\n{SEPARATOR}"


def build_report(metrics: list[dict], generated_at: str) -> str:
    """Build the full plain-text report string."""
    lines = [
        "GEMA — Women's Representation in Portuguese Sports Media",
        "Pipeline End-to-End Evaluation Report",
        f"Generated: {generated_at}",
        f"Database:  {MONGO_URI}{DB_NAME}",
    ]

    for m in metrics:
        lines.append(_fmt_section(m["section"]))
        for k, v in m.items():
            if k == "section":
                continue
            if isinstance(v, dict):
                lines.append(f"  {k}:")
                for kk, vv in v.items():
                    lines.append(f"      {kk}: {vv}")
            elif isinstance(v, list):
                lines.append(f"  {k}:")
                for item in v:
                    lines.append(f"      {item}")
            else:
                lines.append(f"  {k}: {v}")

    total_time = sum(m.get("query_time_s", 0) for m in metrics)
    lines.append(f"\n{SEPARATOR}")
    lines.append(f"  Total query time: {total_time:.3f}s")
    lines.append(SEPARATOR)
    return "\n".join(lines)


def build_csv_rows(metrics: list[dict]) -> list[dict]:
    """Flatten scalar metrics into {section, metric, value} rows for CSV export."""
    rows = []
    nested_keys = {"section", "gender_breakdown", "year_breakdown",
                   "newspaper_breakdown", "top10_feminine", "top10_masculine"}
    for m in metrics:
        section = m.get("section", "")
        for k, v in m.items():
            if k in nested_keys:
                continue
            rows.append({"section": section, "metric": k, "value": v})
    return rows


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="GEMA Pipeline Evaluation")
    parser.add_argument("--output", default=None, help="Path to save the text report (.txt)")
    parser.add_argument("--csv",    default=None, help="Path to save the metrics CSV (.csv)")
    parser.add_argument("--mongo-uri", default=MONGO_URI, help="MongoDB connection URI")
    args = parser.parse_args()

    print("GEMA — Connecting to MongoDB...")
    try:
        db = connect(args.mongo_uri)
        print("Connection successful.\n")
    except Exception as e:
        print(f"ERROR: Could not connect to MongoDB: {e}")
        sys.exit(1)

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    metrics = []

    steps = [
        ("Text pipeline metrics",   metric_text_pipeline),
        ("Visual pipeline metrics", metric_visual_pipeline),
        ("NER metrics",             metric_ner),
        ("Data integrity check",    metric_data_integrity),
    ]

    for label, fn in steps:
        print(f"  -> {label}...", end=" ", flush=True)
        t = time.perf_counter()
        try:
            result = fn(db)
            metrics.append(result)
            print(f"done ({time.perf_counter() - t:.2f}s)")
        except Exception as e:
            print(f"FAILED: {e}")
            metrics.append({"section": label, "error": str(e)})

    report = build_report(metrics, generated_at)
    print("\n" + report)

    if args.output:
        os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\nReport saved -> {args.output}")

    if args.csv:
        os.makedirs(os.path.dirname(args.csv) if os.path.dirname(args.csv) else ".", exist_ok=True)
        rows = build_csv_rows(metrics)
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["section", "metric", "value"])
            writer.writeheader()
            writer.writerows(rows)
        print(f"CSV saved -> {args.csv}")


if __name__ == "__main__":
    main()

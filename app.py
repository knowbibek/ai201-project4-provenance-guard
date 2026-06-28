"""Provenance Guard — Flask API.

Milestone 3: POST /submit (Signal 1 only) + structured audit log + GET /log.
Confidence and label are PLACEHOLDERS until Milestone 4 (fusion) and Milestone 5 (label logic).
"""
import json
import uuid

from flask import Flask, jsonify, request

from audit import get_log, init_db, log_decision, _utc_now
from config import ATTR_AI, ATTR_HUMAN, ATTR_UNCERTAIN
from signals import signal_llm

app = Flask(__name__)
init_db()


def _placeholder_verdict(llm: dict) -> dict:
    """M3 stand-in: derive attribution from Signal 1 alone.

    Real fusion + calibrated confidence arrive in M4; real label text in M5.
    """
    score = llm["score"]
    if not llm["available"]:
        attribution = ATTR_UNCERTAIN
    elif score >= 0.5:
        attribution = ATTR_AI
    else:
        attribution = ATTR_HUMAN
    return {
        "attribution": attribution,
        "confidence": round(abs(score - 0.5) * 2, 2),  # placeholder (single-signal)
        "label": {
            "variant": attribution,
            "text": "(placeholder — final label logic added in Milestone 5)",
        },
    }


@app.post("/submit")
def submit():
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    creator_id = body.get("creator_id")

    if not text:
        return jsonify({"error": "field 'text' is required and must be non-empty"}), 400
    if not creator_id:
        return jsonify({"error": "field 'creator_id' is required"}), 400

    content_id = str(uuid.uuid4())
    llm = signal_llm(text)
    verdict = _placeholder_verdict(llm)

    record = {
        "content_id": content_id,
        "creator_id": creator_id,
        "title": body.get("title"),
        "timestamp": _utc_now(),
        "content_excerpt": text[:300],
        "attribution": verdict["attribution"],
        "confidence": verdict["confidence"],
        "llm_score": llm["score"],
        "stylometry_score": None,  # added in M4
        "label_variant": verdict["label"]["variant"],
        "label_text": verdict["label"]["text"],
        "signals_json": json.dumps([llm]),
        "status": "classified",
    }
    log_decision(record)

    return jsonify(
        {
            "content_id": content_id,
            "creator_id": creator_id,
            "attribution": verdict["attribution"],
            "confidence": verdict["confidence"],
            "label": verdict["label"],
            "signals": [llm],
            "created_at": record["timestamp"],
        }
    )


@app.get("/log")
def log():
    limit = request.args.get("limit", default=50, type=int)
    return jsonify({"entries": get_log(limit)})


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

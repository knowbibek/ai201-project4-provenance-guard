"""Provenance Guard — Flask API.

Milestone 3: POST /submit (Signal 1 only) + structured audit log + GET /log.
Confidence and label are PLACEHOLDERS until Milestone 4 (fusion) and Milestone 5 (label logic).
"""
import json
import uuid


from flask import Flask, jsonify, request  # type: ignore[import]

from audit import get_log, init_db, log_decision, _utc_now
from scoring import score_confidence
from signals import signal_llm, signal_stylometry

app = Flask(__name__)
init_db()


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
    stylometry = signal_stylometry(text)
    verdict = score_confidence(llm, stylometry)

    # Final label text is M5; for now the variant tracks the real verdict.
    label = {
        "variant": verdict["attribution"],
        "text": "(placeholder — final label logic added in Milestone 5)",
    }
    signals = [llm, stylometry]

    record = {
        "content_id": content_id,
        "creator_id": creator_id,
        "title": body.get("title"),
        "timestamp": _utc_now(),
        "content_excerpt": text[:300],
        "attribution": verdict["attribution"],
        "confidence": verdict["confidence"],
        "llm_score": llm["score"],
        "stylometry_score": stylometry["score"],
        "label_variant": label["variant"],
        "label_text": label["text"],
        "signals_json": json.dumps(signals),
        "status": "classified",
    }
    log_decision(record)

    return jsonify(
        {
            "content_id": content_id,
            "creator_id": creator_id,
            "attribution": verdict["attribution"],
            "ai_likelihood": verdict["ai_likelihood"],
            "confidence": verdict["confidence"],
            "label": label,
            "signals": signals,
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

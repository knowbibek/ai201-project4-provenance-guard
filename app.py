"""Provenance Guard — Flask API.

Endpoints:
  POST /submit   text -> two-signal classification + confidence + transparency label (rate limited)
  POST /appeal   contest a classification -> status 'under_review' + logged (rate limited)
  GET  /log      structured audit log (decisions + any appeals), newest first
  GET  /health   liveness
"""
import json
import uuid

from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from audit import _utc_now, get_log, init_db, log_appeal, log_decision
from labels import build_label
from scoring import score_confidence
from signals import signal_lexical, signal_llm, signal_stylometry

app = Flask(__name__)
init_db()

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "rate limit exceeded", "detail": str(e.description)}), 429


@app.post("/submit")
@limiter.limit("10 per minute;100 per hour;300 per day")
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
    lexical = signal_lexical(text)
    verdict = score_confidence(llm, stylometry, lexical)
    label = build_label(verdict["attribution"])
    signals = [llm, stylometry, lexical]

    record = {
        "content_id": content_id,
        "creator_id": creator_id,
        "title": body.get("title"),
        "timestamp": _utc_now(),
        "content_excerpt": text[:300],
        "attribution": verdict["attribution"],
        "confidence": verdict["confidence"],
        "ai_likelihood": verdict["ai_likelihood"],
        "llm_score": llm["score"],
        "stylometry_score": stylometry["score"],
        "lexical_score": lexical["score"],
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
            "status": "classified",
            "created_at": record["timestamp"],
        }
    )


@app.post("/appeal")
@limiter.limit("5 per minute;20 per hour")
def appeal():
    body = request.get_json(silent=True) or {}
    content_id = body.get("content_id")
    reasoning = (body.get("creator_reasoning") or "").strip()

    if not content_id:
        return jsonify({"error": "field 'content_id' is required"}), 400
    if not reasoning:
        return jsonify({"error": "field 'creator_reasoning' is required"}), 400

    result = log_appeal(content_id, reasoning)
    if result is None:
        return jsonify({"error": f"no submission found for content_id {content_id}"}), 404

    return jsonify({**result, "message": "Appeal received. This content is now under review."})


@app.get("/log")
@limiter.limit("30 per minute")
def log():
    limit = request.args.get("limit", default=50, type=int)
    return jsonify({"entries": get_log(limit)})


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

"""Confidence fusion — combine the two signals into one calibrated verdict.

Implements planning.md §2 exactly:
  weights        : 0.60 LLM / 0.40 stylometry, or 0.85 / 0.15 if stylometry is low-reliability
  combined       : weighted average of the two AI-likelihoods
  decisiveness   : 2·|combined − 0.5|              (0 at the fence, 1 at the extremes)
  agreement      : 1 − |s1 − s2|                   (1 when signals agree, 0 when opposite)
  confidence     : decisiveness · (0.4 + 0.6·agreement)
  low-reliability: confidence capped at 0.55

Verdict thresholds (asymmetric — harder to assert AI than human):
  confidence < 0.50                          -> uncertain
  confidence ≥ 0.50  and human side          -> likely_human
  0.50 ≤ confidence < 0.65 and AI side       -> uncertain   (not sure enough to accuse)
  confidence ≥ 0.65  and AI side             -> likely_ai
"""
from config import ATTR_AI, ATTR_HUMAN, ATTR_UNCERTAIN

HUMAN_CONF_BAR = 0.50
AI_CONF_BAR = 0.65


def _verdict(ai_likelihood: float, confidence: float) -> str:
    if confidence < HUMAN_CONF_BAR:
        return ATTR_UNCERTAIN
    if ai_likelihood < 0.5:
        return ATTR_HUMAN
    # AI side: require the higher bar
    return ATTR_AI if confidence >= AI_CONF_BAR else ATTR_UNCERTAIN


def score_confidence(llm: dict, stylometry: dict) -> dict:
    s1 = llm["score"]
    s2 = stylometry["score"]
    low_reliability = stylometry.get("low_reliability", False)

    w_llm, w_sty = (0.85, 0.15) if low_reliability else (0.60, 0.40)
    combined = w_llm * s1 + w_sty * s2

    decisiveness = 2 * abs(combined - 0.5)
    agreement = 1 - abs(s1 - s2)
    confidence = decisiveness * (0.4 + 0.6 * agreement)
    if low_reliability:
        confidence = min(confidence, 0.55)

    attribution = _verdict(combined, confidence)

    return {
        "attribution": attribution,
        "ai_likelihood": round(combined, 4),
        "confidence": round(confidence, 4),
        "agreement": round(agreement, 4),
        "weights": {"llm": w_llm, "stylometry": w_sty},
    }

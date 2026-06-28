"""Confidence fusion — combine the two signals into one calibrated verdict.

Implements planning.md §2. The LLM is the PRIMARY signal (it's far stronger at this task);
stylometry corroborates or dissents but cannot assert a verdict on its own.

  ai_likelihood : weighted average of the two AI-likelihoods (direction only)
                  weights 0.60 LLM / 0.40 stylometry, or 0.85 / 0.15 if stylometry is low-reliability

  base          : 2·|s1 − 0.5|             -> LLM decisiveness sets the confidence ceiling
  overlap       : 2·min(|s1−0.5|, |s2−0.5|) -> how strongly the weaker signal weighs in
  confidence    : if signals on the SAME side of 0.5 -> base + (1−base)·overlap   (corroborate)
                  if on OPPOSITE sides            -> base · (1 − overlap)         (dissent erodes)
                  if stylometry is neutral        -> base                          (no change)
  low-reliability: confidence capped at 0.55

Because `base` comes only from the LLM, a failed/neutral LLM (score 0.5 -> base 0) yields low
confidence -> "uncertain". Stylometry alone can never produce a confident accusation. Fail-closed.

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

    d1 = s1 - 0.5
    d2 = s2 - 0.5
    base = 2 * abs(d1)  # LLM decisiveness — the primary driver
    overlap = 2 * min(abs(d1), abs(d2))  # contribution of the weaker signal

    if d1 * d2 > 0:  # both signals on the same side -> stylometry corroborates
        confidence = base + (1 - base) * overlap
    elif d1 * d2 < 0:  # opposite sides -> stylometry dissents, erodes confidence
        confidence = base * (1 - overlap)
    else:  # one signal is exactly neutral -> LLM alone
        confidence = base

    if low_reliability:
        confidence = min(confidence, 0.55)

    attribution = _verdict(combined, confidence)

    return {
        "attribution": attribution,
        "ai_likelihood": round(combined, 4),
        "confidence": round(confidence, 4),
        "agreement": round(1 - abs(s1 - s2), 4),  # reported for transparency
        "weights": {"llm": w_llm, "stylometry": w_sty},
    }

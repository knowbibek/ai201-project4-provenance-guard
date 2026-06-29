"""Confidence fusion — combine the signals into one calibrated verdict.

Implements planning.md §2 + the ensemble stretch. The LLM is the PRIMARY signal (far stronger at this
task). The pure-Python heuristics (stylometry + lexical) form a SECONDARY PANEL that corroborates or
dissents but cannot assert a verdict on its own. `_panel()` combines them: `0.6·stylometry + 0.4·
lexical`, falling back to the lexical score when stylometry trips its short-text reliability guard.

  ai_likelihood : weighted average of LLM and panel (direction only)
                  weights 0.60 LLM / 0.40 panel, or 0.85 / 0.15 if the panel is low-reliability

  base          : 2·|s1 − 0.5|              -> LLM decisiveness sets the confidence ceiling
  overlap       : 2·min(|s1−0.5|, |panel−0.5|) -> how strongly the panel weighs in
  confidence    : if LLM and panel on the SAME side of 0.5 -> base + (1−base)·overlap  (corroborate)
                  if on OPPOSITE sides                  -> base · (1 − overlap)        (dissent erodes)
                  if panel is neutral                   -> base                         (no change)
  low-reliability: confidence capped at 0.55

Because `base` comes only from the LLM, a failed/neutral LLM (score 0.5 -> base 0) yields low
confidence -> "uncertain". The heuristic panel alone can never produce a confident accusation. Fail-closed.

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


def _panel(stylometry: dict, lexical: dict | None) -> tuple[float, bool]:
    """Combine the heuristic signals (stylometry + lexical) into one secondary-panel score.

    Returns (panel_score, panel_low_reliability). When stylometry trips its short-text guard,
    the panel falls back to the lexical score; the panel is only "low reliability" when *neither*
    heuristic has solid evidence (short text AND no lexical markers).
    """
    s_sty = stylometry["score"]
    sty_low = stylometry.get("low_reliability", False)
    if lexical is None:  # backward-compatible: stylometry-only panel
        return s_sty, sty_low

    s_lex = lexical["score"]
    if sty_low:
        # stylometry unreliable -> lean on the lexical detector
        return s_lex, lexical.get("distinct_markers", 0) == 0
    return 0.60 * s_sty + 0.40 * s_lex, False


def score_confidence(llm: dict, stylometry: dict, lexical: dict | None = None) -> dict:
    s1 = llm["score"]
    panel, low_reliability = _panel(stylometry, lexical)

    w_llm, w_panel = (0.85, 0.15) if low_reliability else (0.60, 0.40)
    combined = w_llm * s1 + w_panel * panel

    d1 = s1 - 0.5
    dp = panel - 0.5
    base = 2 * abs(d1)  # LLM decisiveness — the primary driver
    overlap = 2 * min(abs(d1), abs(dp))  # contribution of the secondary panel

    if d1 * dp > 0:  # LLM and panel on the same side -> panel corroborates
        confidence = base + (1 - base) * overlap
    elif d1 * dp < 0:  # opposite sides -> panel dissents, erodes confidence
        confidence = base * (1 - overlap)
    else:  # panel is exactly neutral -> LLM alone
        confidence = base

    if low_reliability:
        confidence = min(confidence, 0.55)

    attribution = _verdict(combined, confidence)

    return {
        "attribution": attribution,
        "ai_likelihood": round(combined, 4),
        "confidence": round(confidence, 4),
        "panel_score": round(panel, 4),
        "agreement": round(1 - abs(s1 - panel), 4),  # LLM vs panel, for transparency
        "weights": {"llm": w_llm, "panel": w_panel},
    }

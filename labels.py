"""Transparency label generation.

Maps a verdict (which is itself derived from confidence + direction in scoring.py) to the exact
reader-facing text. Three variants, finalized in planning.md §3. Even the AI label is phrased as an
*estimate*, never an accusation, and names the appeal path.
"""
from config import ATTR_AI, ATTR_HUMAN, ATTR_UNCERTAIN

_LABELS = {
    ATTR_HUMAN: {
        "variant": "high_confidence_human",
        "text": (
            "✍️ Likely written by a person. Our automated check found strong signs of human "
            "authorship. This is an automated estimate, not a guarantee. (Confidence: High)"
        ),
    },
    ATTR_AI: {
        "variant": "high_confidence_ai",
        "text": (
            "🤖 Likely AI-generated. Our automated check found strong signs this was produced with "
            "AI assistance. This is an estimate, not a certainty — if you wrote this yourself, you "
            "can appeal. (Confidence: High)"
        ),
    },
    ATTR_UNCERTAIN: {
        "variant": "uncertain",
        "text": (
            "❓ Origin unclear. Our automated check couldn't reliably tell whether a person or AI "
            "wrote this, so we're not making a claim either way. (Confidence: Low)"
        ),
    },
}


def build_label(attribution: str) -> dict:
    """Return {variant, text} for the given verdict. Falls back to the uncertain label."""
    return _LABELS.get(attribution, _LABELS[ATTR_UNCERTAIN])

"""Standalone signal + scoring self-test (run locally, where Groq is reachable).

    python selftest.py

Prints all three signal scores, the fused confidence, and the verdict for four deliberately chosen
inputs spanning the confidence range. This is the Milestone 4 calibration check — if the LLM
column shows available=False, your environment can't reach Groq (check GROQ_API_KEY / network).
"""
from scoring import score_confidence
from signals import signal_lexical, signal_llm, signal_stylometry

CASES = {
    "CLEAR AI": (
        "Artificial intelligence represents a transformative paradigm shift in modern society. "
        "It is important to note that while the benefits of AI are numerous, it is equally "
        "essential to consider the ethical implications. Furthermore, stakeholders across "
        "various sectors must collaborate to ensure responsible deployment."
    ),
    "CLEAR HUMAN": (
        "ok so i finally tried that new ramen place downtown and honestly? underwhelming. the "
        "broth was fine but they put WAY too much sodium in it and i was thirsty for like three "
        "hours after. my friend got the spicy version and said it was better. probably won't go "
        "back unless someone drags me there"
    ),
    "BORDERLINE formal-human": (
        "The relationship between monetary policy and asset price inflation has been extensively "
        "studied in the literature. Central banks face a fundamental tension between their mandate "
        "for price stability and the unintended consequences of prolonged low interest rates on "
        "equity and real estate valuations. Many papers explore this dynamic in detail."
    ),
    "BORDERLINE edited-AI": (
        "I've been thinking a lot about remote work lately. There are genuine tradeoffs: "
        "flexibility and no commute on one side, isolation and blurred work-life boundaries on the "
        "other. Studies show productivity varies widely by individual and role type."
    ),
}


def main() -> None:
    print(
        f"{'case':26s} {'llm':>6s} {'avail':>6s} {'sty':>6s} {'lex':>6s} "
        f"{'ai_lik':>7s} {'conf':>6s}  verdict"
    )
    print("-" * 86)
    for name, text in CASES.items():
        llm = signal_llm(text)
        sty = signal_stylometry(text)
        lex = signal_lexical(text)
        v = score_confidence(llm, sty, lex)
        print(
            f"{name:26s} {llm['score']:>6.3f} {str(llm['available']):>6s} "
            f"{sty['score']:>6.3f} {lex['score']:>6.3f} {v['ai_likelihood']:>7.3f} "
            f"{v['confidence']:>6.3f}  {v['attribution']}"
        )


if __name__ == "__main__":
    main()

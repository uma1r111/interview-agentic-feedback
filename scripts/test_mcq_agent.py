"""
Standalone test script for MCQCheckerAgent.
Run from the repo root:

    pdm run python scripts/test_mcq_agent.py
    pdm run python scripts/test_mcq_agent.py fixtures/sample_mcq_answers.txt

You can also pass any other .txt / .pdf / .docx MCQ file as the first argument.
"""

import sys
import logging
from pathlib import Path

# Force UTF-8 output on Windows terminals that default to cp1252
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Make sure repo root is on the path regardless of where the script is run from
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
)

from agents.mcq_checker_agent import MCQCheckerAgent


def main():
    # ── File to test ─────────────────────────────────────────────────────────
    if len(sys.argv) > 1:
        mcq_file = sys.argv[1]
    else:
        mcq_file = str(
            Path(__file__).resolve().parent.parent
            / "fixtures"
            / "sample_mcq_answers.txt"
        )

    print(f"\n{'='*60}")
    print(f"  MCQ Checker Agent — Standalone Test")
    print(f"  File : {mcq_file}")
    print(f"{'='*60}\n")

    # ── Run the agent ─────────────────────────────────────────────────────────
    agent = MCQCheckerAgent()

    try:
        score, insight, details = agent.evaluate(mcq_file)
    except Exception as e:
        print(f"[ERROR] Agent raised an exception:\n  {e}")
        sys.exit(1)

    # ── Print results ─────────────────────────────────────────────────────────
    total   = len(details)
    correct = sum(1 for r in details if r.is_correct)

    print(f"  SCORE  : {score:.2f} / 5.0  ({correct}/{total} correct)\n")

    print("─" * 60)
    print("  INSIGHT")
    print("─" * 60)
    print(f"\n{insight}\n")

    print("─" * 60)
    print("  QUESTION-BY-QUESTION BREAKDOWN")
    print("─" * 60)

    for r in details:
        status = "✔  CORRECT" if r.is_correct else "✘  WRONG  "
        print(
            f"\n  Q{r.question_number:02d} [{r.topic_tag}]  {status}"
            f"\n       Question : {r.question_text[:80]}{'...' if len(r.question_text) > 80 else ''}"
            f"\n       Candidate : {r.candidate_answer}"
            f"\n       Correct   : {r.correct_answer}"
            f"\n       Note      : {r.explanation}"
        )

    print(f"\n{'='*60}")
    print(f"  Done. Final MCQ score: {score:.2f}/5.0")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

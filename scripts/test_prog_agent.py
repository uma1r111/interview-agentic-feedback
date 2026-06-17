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

from agents.programming_checker_agent import ProgrammingCheckerAgent

def main():
    if len(sys.argv) > 1:
        prog_file = sys.argv[1]
    else:
        prog_file = str(
            Path(__file__).resolve().parent.parent
            / "fixtures"
            / "sample_programming_answers.txt"
            
        )

    print(f"\n{'='*60}")
    print(f"  Programming Checker Agent — Standalone Test")
    print(f"  File : {prog_file}")
    print(f"{'='*60}\n")

    agent = ProgrammingCheckerAgent()

    try:
        passed, insight, details = agent.evaluate(prog_file)
    except Exception as e:
        print(f"[ERROR] Agent raised an exception:\n  {e}")
        sys.exit(1)

    status_str = "✅ PASS" if passed else "❌ FAIL"
    print(f"  OVERALL STATUS: {status_str}\n")

    print("─" * 60)
    print("  INSIGHT")
    print("─" * 60)
    print(f"\n{insight}\n")

    print("─" * 60)
    print("  QUESTION-BY-QUESTION BREAKDOWN")
    print("─" * 60)

    for r in details:
        q_status = "✅ PASS" if r.is_pass else "❌ FAIL"
        print(
            f"\n  Q{r.question_number:02d}  {q_status}"
            f"\n       Question : {r.question_text}"
            f"\n       Feedback : {r.feedback}"
        )

    print(f"\n{'='*60}")
    print(f"  Done. Final Result: {status_str}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()

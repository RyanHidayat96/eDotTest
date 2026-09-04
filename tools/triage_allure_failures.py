from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from edot_qa.ai.triage import triage_allure_results
from edot_qa.config import load_settings


def main() -> int:
    settings = load_settings()
    parser = argparse.ArgumentParser(description="Create an eDOT QA failure triage report from Allure results.")
    parser.add_argument("--results-dir", type=Path, default=settings.allure_results_dir)
    parser.add_argument(
        "--history-dir",
        type=Path,
        action="append",
        default=[],
        help="Optional prior Allure result/history directory used only for safe status history.",
    )
    parser.add_argument("--output", type=Path, default=settings.triage_report_path)
    parser.add_argument("--no-ai", action="store_true", help="Use deterministic triage only.")
    args = parser.parse_args()

    report = triage_allure_results(
        args.results_dir,
        args.output,
        history_dirs=args.history_dir,
        settings=settings,
        use_ai=not args.no_ai,
    )
    counts = Counter(report.summary)
    print(f"triage_report={report.output_path}")
    print(f"failures={len(report.verdicts)}")
    for verdict, count in sorted(counts.items()):
        print(f"{verdict}={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

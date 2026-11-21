"""Run test questions through the reply loop and score the answers.

    uv run python scripts/eval_questions.py                       # sample CSV + sample sheet data
    uv run python scripts/eval_questions.py --tenant 1            # that tenant's live Google Sheet
    uv run python scripts/eval_questions.py my_questions.csv --show

CSV columns: question, expected_keywords
  expected_keywords: required keywords separated by ";". Alternatives inside one keyword are
  separated by "|". Matching ignores case and Vietnamese accents.
  Example: "2.500.000;đặt lịch|hẹn"  ->  must contain "2.500.000" AND ("đặt lịch" OR "hẹn").

Calls the real Claude API (needs ANTHROPIC_API_KEY) and costs a little money.
"""

import argparse
import csv
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import django_setup

HERE = Path(__file__).resolve().parent
DEFAULT_CSV = HERE / "eval_sample.csv"
SAMPLE_SHEET_DIR = HERE / "sample_sheet"


@dataclass
class Case:
    question: str
    expected: list[list[str]]  # AND of ORs


@dataclass
class Outcome:
    case: Case
    reply: str
    passed: bool
    missing: list[str]
    latency_ms: int
    input_tokens: int
    output_tokens: int
    tools: list[str]
    fallback: bool


def load_cases(path: Path) -> list[Case]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    cases = []
    for row in rows:
        groups = [
            [alt.strip() for alt in group.split("|") if alt.strip()]
            for group in row.get("expected_keywords", "").split(";")
        ]
        cases.append(Case(row["question"].strip(), [g for g in groups if g]))
    return cases


def missing_keywords(reply: str, expected: list[list[str]]) -> list[str]:
    from clinic.text_utils import remove_diacritics

    folded = remove_diacritics(reply)
    return [
        "|".join(group)
        for group in expected
        if not any(remove_diacritics(alt) in folded for alt in group)
    ]


def run_eval(cases: Sequence[Case], engine, tenant) -> list[Outcome]:
    outcomes = []
    for case in cases:
        result = engine.reply(tenant, [SimpleNamespace(role="user", text=case.question)])
        missing = missing_keywords(result.text, case.expected)
        outcomes.append(
            Outcome(
                case=case,
                reply=result.text,
                passed=not missing and not result.is_fallback,
                missing=missing,
                latency_ms=result.latency_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                tools=[f"{t.name}({next(iter(t.input.values()), '')})" for t in result.tool_calls],
                fallback=result.is_fallback,
            )
        )
    return outcomes


def print_report(outcomes: Sequence[Outcome], show: bool) -> None:
    from clinic.ai.reply_engine import estimate_cost_usd

    for i, o in enumerate(outcomes, 1):
        status = "PASS" if o.passed else "FAIL"
        print(f"[{status}] {i:2}. {o.case.question}")
        print(f"         {o.latency_ms} ms | tools: {', '.join(o.tools) or '-'}")
        if o.fallback:
            print("         FALLBACK reply (Claude or Sheet error, see logs)")
        if o.missing:
            print(f"         missing: {', '.join(o.missing)}")
        if show or not o.passed:
            print("         reply: " + o.reply.replace("\n", "\n                "))

    n = len(outcomes) or 1
    passed = sum(o.passed for o in outcomes)
    total_in = sum(o.input_tokens for o in outcomes)
    total_out = sum(o.output_tokens for o in outcomes)
    cost = estimate_cost_usd(total_in, total_out)
    print()
    print(f"Passed:        {passed}/{len(outcomes)}")
    print(f"Avg latency:   {sum(o.latency_ms for o in outcomes) / n:.0f} ms")
    print(f"Tokens:        {total_in} in / {total_out} out")
    print(f"Cost:          ${cost:.4f} total, ${cost / n:.5f} per question (upper bound)")


def build_engine_and_tenant(tenant_id: int | None):
    from clinic.ai.prompt_builder import PromptBuilder
    from clinic.ai.reply_engine import ReplyEngine, default_claude_client
    from clinic.knowledge.csv_source import CsvKnowledgeSource
    from clinic.knowledge.google_sheet import GoogleSheetSource
    from clinic.models import Tenant
    from clinic.tools.registry import default_registry

    if tenant_id is None:
        knowledge = CsvKnowledgeSource(SAMPLE_SHEET_DIR)
        tenant = Tenant(name="Nha khoa Nụ Cười (dữ liệu mẫu)")  # not saved
    else:
        knowledge = GoogleSheetSource()
        tenant = Tenant.objects.get(pk=tenant_id)
    engine = ReplyEngine(
        default_claude_client(), default_registry(knowledge), PromptBuilder(knowledge)
    )
    return engine, tenant


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("csv", nargs="?", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--tenant", type=int, help="Use this tenant's Google Sheet")
    parser.add_argument("--show", action="store_true", help="Print every reply")
    args = parser.parse_args()

    django_setup.setup()
    engine, tenant = build_engine_and_tenant(args.tenant)
    outcomes = run_eval(load_cases(args.csv), engine, tenant)
    print_report(outcomes, args.show)
    sys.exit(0 if all(o.passed for o in outcomes) else 1)


if __name__ == "__main__":
    main()

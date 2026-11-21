import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import eval_questions  # noqa: E402

from clinic.ai.prompt_builder import PromptBuilder  # noqa: E402
from clinic.ai.reply_engine import ReplyEngine  # noqa: E402
from clinic.models import Tenant  # noqa: E402
from clinic.tools.registry import default_registry  # noqa: E402
from tests.fakes import (  # noqa: E402
    FakeClaude,
    anthropic_connection_error,
    claude_response,
    sample_knowledge,
    text_block,
    tool_use_block,
)


def test_sample_csv_has_20_questions_with_keywords():
    cases = eval_questions.load_cases(eval_questions.DEFAULT_CSV)
    assert len(cases) == 20
    assert all(case.expected for case in cases)


def test_keyword_groups_and_alternatives(tmp_path):
    path = tmp_path / "q.csv"
    path.write_text("question,expected_keywords\nhi,2.500.000; đặt lịch | hẹn\n", encoding="utf-8")
    [case] = eval_questions.load_cases(path)
    assert case.expected == [["2.500.000"], ["đặt lịch", "hẹn"]]


@pytest.mark.parametrize(
    ("reply", "missing"),
    [
        ("Dạ giá là 2.500.000đ, chị muốn hẹn lịch không ạ?", []),
        ("Dạ giá là 2.500.000đ ạ", ["đặt lịch|hẹn"]),
        ("Dạ em DAT LICH cho chị nhé, gia 2.500.000d", []),  # accents/case ignored
    ],
)
def test_missing_keywords(reply, missing):
    assert eval_questions.missing_keywords(reply, [["2.500.000"], ["đặt lịch", "hẹn"]]) == missing


def test_run_eval_and_report(capsys):
    knowledge = sample_knowledge()
    claude = FakeClaude(
        claude_response(tool_use_block("get_price", {"service": "tẩy trắng"})),
        claude_response(text_block("Dạ 2.500.000đ ạ"), output_tokens=10),
        anthropic_connection_error(),
    )
    engine = ReplyEngine(claude, default_registry(knowledge), PromptBuilder(knowledge))
    cases = [
        eval_questions.Case("tẩy trắng bao nhiêu", [["2.500.000"]]),
        eval_questions.Case("implant", [["18.000.000"]]),
    ]

    outcomes = eval_questions.run_eval(cases, engine, Tenant(name="Demo"))
    eval_questions.print_report(outcomes, show=False)

    assert [o.passed for o in outcomes] == [True, False]
    assert outcomes[0].tools == ["get_price(tẩy trắng)"]
    assert outcomes[1].fallback
    out = capsys.readouterr().out
    assert "Passed:        1/2" in out
    assert "Avg latency:" in out
    assert "Cost:" in out

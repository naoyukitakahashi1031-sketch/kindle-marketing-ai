from types import SimpleNamespace

import pytest
from kma.claude_client import build_request, extract_text


def test_sonnet_55_disables_upfront_thinking():
    req = build_request("claude-sonnet-5-5", 2500, "system", "prompt")
    assert req["thinking"] == {"type": "between_tools"}
    assert req["max_tokens"] == 2500
    assert req["messages"][0]["content"] == "prompt"


def test_other_model_omits_model_specific_thinking():
    req = build_request("claude-sonnet-4-5", 2500, "system", "prompt")
    assert "thinking" not in req


def test_extracts_text_and_ignores_thinking():
    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="thinking", text="non-visible"),
            SimpleNamespace(type="text", text="分析結果"),
        ],
        stop_reason="end_turn",
    )
    assert extract_text(response) == "分析結果"


def test_empty_max_tokens_response_has_diagnostic():
    response = SimpleNamespace(
        content=[SimpleNamespace(type="thinking", text="")],
        stop_reason="max_tokens",
    )
    with pytest.raises(ValueError, match="出力上限"):
        extract_text(response)

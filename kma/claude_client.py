"""Claude API request configuration and safe text extraction.

Claude Sonnet 5.5 uses adaptive thinking by default, which can exhaust a
short max_tokens allowance before returning visible text. For text-only
reports, between_tools avoids up-front thinking on Sonnet 5.5.
"""
from __future__ import annotations


def build_request(model: str, max_tokens: int, system: str, prompt: str) -> dict:
    if max_tokens < 1:
        raise ValueError("max_tokens must be positive")
    request = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    if model.strip().startswith("claude-sonnet-5-5"):
        # Sonnet 5.5 rejects thinking=disabled; between_tools is supported.
        request["thinking"] = {"type": "between_tools"}
    return request


def extract_text(response) -> str:
    """Return user-visible text, never hidden thinking or API metadata."""
    output = "\n".join(
        str(getattr(block, "text", ""))
        for block in getattr(response, "content", [])
        if getattr(block, "type", "") == "text"
    ).strip()
    if output:
        return output
    stop_reason = getattr(response, "stop_reason", "不明")
    if stop_reason == "max_tokens":
        raise ValueError(
            "出力上限に達し、文章を受信できませんでした。"
            "出力上限を増やすか思考設定を見直してください。"
        )
    raise ValueError(
        f"API応答に表示可能な文章がありません（終了理由：{stop_reason}）。"
        "モデルの応答設定を確認してください。"
    )

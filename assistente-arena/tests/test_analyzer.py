from __future__ import annotations

import pytest
from fakes import FakeClaude
from PIL import Image

from assistente_arena.claude.analyzer import AnalysisError, analyze, build_request
from assistente_arena.screen.capture import prepare


def _image():  # type: ignore[no-untyped-def]
    return prepare(Image.new("RGB", (100, 50)))


def test_request_shape_opus() -> None:
    req = build_request(_image(), "claude-opus-5-5", "medium", "Histórico")
    assert req["fallbacks"] == "default"
    assert req["betas"] == ["server-side-fallback-2026-07-01"]
    assert req["thinking"] == {"type": "adaptive"}
    assert req["output_config"]["effort"] == "medium"
    assert req["output_config"]["format"]["type"] == "json_schema"
    content = req["messages"][0]["content"]
    assert content[0]["type"] == "image" and "Histórico" in content[1]["text"]
    assert "temperature" not in req


def test_haiku_has_no_server_fallback() -> None:
    req = build_request(_image(), "claude-haiku-5-5", "low", "Histórico")
    assert "fallbacks" not in req and "betas" not in req


def test_analyze_parses_structured_output() -> None:
    result = analyze(
        FakeClaude(), _image(), model="claude-opus-5-5", effort="medium", format_hint="Histórico"
    )
    assert result.analysis.tipo_tela == "construtor_de_deck"
    assert result.analysis.cartas[0].quantidade == 4
    assert result.usage.input_tokens == 3000


@pytest.mark.parametrize(
    ("client", "message"),
    [
        (FakeClaude(stop_reason="refusal"), "recusou"),
        (FakeClaude(stop_reason="max_tokens"), "cortada"),
        (FakeClaude(text="isto não é json"), "formato"),
    ],
)
def test_errors_keep_usage_for_billing(client: FakeClaude, message: str) -> None:
    with pytest.raises(AnalysisError, match=message) as info:
        analyze(client, _image(), model="claude-opus-5-5", effort="medium", format_hint="H")
    assert info.value.usage is not None

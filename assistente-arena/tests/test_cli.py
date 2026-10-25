from __future__ import annotations

import argparse

import pytest

from assistente_arena import cli


def test_no_arguments_starts_guided_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(cli, "cmd_iniciar", lambda: calls.append("iniciar") or 0)
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    assert cli.main([]) == 0
    assert calls == ["iniciar"]


def test_guided_mode_asks_key_then_observes(monkeypatch: pytest.MonkeyPatch) -> None:
    steps: list[str] = []
    monkeypatch.setattr(cli, "get_api_key", lambda: None)
    monkeypatch.setattr(cli, "cmd_chave", lambda a: steps.append("chave") or 0)
    monkeypatch.setattr(cli, "cmd_status", lambda a: steps.append("status") or 0)

    def fake_observar(a: argparse.Namespace) -> int:
        steps.append(f"observar:{a.atalho}:{a.exportar}")
        return 0

    monkeypatch.setattr(cli, "cmd_observar", fake_observar)
    monkeypatch.setattr(cli, "cmd_atalho", lambda a: steps.append("atalho") or 0)
    monkeypatch.setattr(cli.sys, "platform", "win32")
    answers = iter(["s"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert cli.cmd_iniciar() == 0
    assert steps == ["chave", "atalho", "status", "observar:ctrl+shift+a:True"]
    # Na segunda vez não pergunta de novo sobre o atalho.
    steps.clear()
    assert cli.cmd_iniciar() == 0
    assert steps == ["chave", "status", "observar:ctrl+shift+a:True"]


def test_unexpected_error_keeps_window_open(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts: list[str] = []

    def boom() -> int:
        raise ValueError("falhou")

    monkeypatch.setattr(cli, "cmd_iniciar", boom)
    monkeypatch.setattr("builtins.input", lambda prompt="": prompts.append(prompt) or "")
    assert cli.main([]) == 1
    assert prompts and "Enter" in prompts[0]


def test_subcommands_still_work(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["status", "--log", "nao-existe.log"]) == 0
    assert "Análise de tela: bloqueada" in capsys.readouterr().out

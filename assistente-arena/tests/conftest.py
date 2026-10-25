from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cada teste usa uma pasta de dados própria e nunca a chave real."""
    monkeypatch.setenv("ASSISTENTE_ARENA_DADOS", str(tmp_path / "dados"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

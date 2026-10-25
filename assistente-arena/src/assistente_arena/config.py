"""Configurações locais, pastas de dados e chave da API.

Nada aqui é salvo dentro do repositório: os dados ficam em
%APPDATA%\\AssistenteArena (Windows) ou ~/.config/assistente-arena (outros).
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

KEYRING_SERVICE = "assistente-arena"
KEYRING_USER = "anthropic"


def data_dir() -> Path:
    override = os.environ.get("ASSISTENTE_ARENA_DADOS")
    if override:
        base = Path(override)
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home())) / "AssistenteArena"
    else:
        base = Path.home() / ".config" / "assistente-arena"
    base.mkdir(parents=True, exist_ok=True)
    return base


@dataclass
class Settings:
    modelo: str = "claude-opus-5-5"
    esforco: str = "medium"
    orcamento_mensal_brl: float = 20.0
    cotacao_dolar_manual: float = 5.50
    formato_padrao: str = "Histórico"
    atalho_oferecido: bool = False

    @classmethod
    def load(cls) -> Settings:
        path = data_dir() / "config.json"
        if not path.exists():
            settings = cls()
            settings.save()
            return settings
        raw = json.loads(path.read_text(encoding="utf-8"))
        known = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def save(self) -> None:
        path = data_dir() / "config.json"
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")


def get_api_key() -> str | None:
    """Variável de ambiente primeiro; depois o Gerenciador de Credenciais do Windows."""
    env = os.environ.get("ANTHROPIC_API_KEY")
    if env:
        return env
    try:
        import keyring

        value: str | None = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
        return value
    except Exception:
        return None


def set_api_key(value: str) -> None:
    import keyring

    keyring.set_password(KEYRING_SERVICE, KEYRING_USER, value)


def delete_api_key() -> None:
    import keyring

    keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)

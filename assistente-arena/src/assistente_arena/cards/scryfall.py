"""Cliente do Scryfall com cache local em SQLite.

Boas práticas da API: User-Agent e Accept próprios, ~100 ms entre chamadas e
nunca repetir uma busca já feita.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

from assistente_arena import __version__

BASE_URL = "https://api.scryfall.com"
HEADERS = {"User-Agent": f"AssistenteArena/{__version__}", "Accept": "application/json"}
MIN_INTERVAL_S = 0.1


@dataclass(frozen=True)
class CardInfo:
    name_en: str
    name_pt: str | None
    oracle_id: str
    arena_id: int | None
    rarity: str
    type_line: str
    mana_cost: str
    set_code: str
    collector_number: str

    @property
    def display(self) -> str:
        """Nome em português com o inglês entre parênteses."""
        if self.name_pt and self.name_pt != self.name_en:
            return f"{self.name_pt} ({self.name_en})"
        return self.name_en


def _same_name(card: CardInfo, key: str) -> bool:
    """Aceita o nome completo ou só uma das faces (cartas dupla-face)."""
    names = [card.name_en.lower(), *(n.strip().lower() for n in card.name_en.split("//"))]
    return key in names


class Scryfall:
    def __init__(self, cache_path: Path, client: httpx.Client | None = None) -> None:
        self._db = sqlite3.connect(cache_path)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS lookup (query TEXT PRIMARY KEY, card TEXT, fetched REAL)"
        )
        self._client = client or httpx.Client(base_url=BASE_URL, headers=HEADERS, timeout=15)
        self._last_call = 0.0

    def close(self) -> None:
        self._db.close()
        self._client.close()

    def find(self, name_en: str) -> tuple[CardInfo | None, bool]:
        """Busca pelo nome em inglês. Devolve (carta, nome_corrigido?).

        Tenta o nome exato; se não achar, a busca aproximada do Scryfall.
        Resultados (inclusive "não encontrada") ficam no cache.
        """
        key = name_en.strip().lower()
        row = self._db.execute("SELECT card FROM lookup WHERE query = ?", (key,)).fetchone()
        if row is not None:
            if row[0] is None:
                return None, False
            card = CardInfo(**json.loads(row[0]))
            return card, not _same_name(card, key)

        data = self._get("/cards/named", {"exact": name_en})
        corrected = False
        if data is None:
            data = self._get("/cards/named", {"fuzzy": name_en})
            corrected = data is not None
        found = self._to_card(data) if data is not None else None
        self._db.execute(
            "INSERT OR REPLACE INTO lookup VALUES (?, ?, ?)",
            (key, json.dumps(asdict(found)) if found else None, time.time()),
        )
        self._db.commit()
        if found is not None:
            corrected = corrected and not _same_name(found, key)
        return found, corrected

    def _to_card(self, data: dict[str, Any]) -> CardInfo:
        faces = data.get("card_faces") or []
        mana_cost = data.get("mana_cost") or " // ".join(
            f.get("mana_cost", "") for f in faces if f.get("mana_cost")
        )
        return CardInfo(
            name_en=data["name"],
            name_pt=self._portuguese_name(data["oracle_id"]) if data.get("oracle_id") else None,
            oracle_id=data.get("oracle_id", ""),
            arena_id=data.get("arena_id"),
            rarity=data.get("rarity", ""),
            type_line=data.get("type_line", ""),
            mana_cost=mana_cost,
            set_code=data.get("set", "").upper(),
            collector_number=str(data.get("collector_number", "")),
        )

    def _portuguese_name(self, oracle_id: str) -> str | None:
        data = self._get(
            "/cards/search",
            {
                "q": f"oracleid:{oracle_id} lang:pt",
                "include_multilingual": "true",
                "unique": "prints",
            },
        )
        if not data or not data.get("data"):
            return None
        card = data["data"][0]
        if card.get("printed_name"):
            return str(card["printed_name"])
        faces = [f.get("printed_name") for f in card.get("card_faces") or []]
        if faces and all(faces):
            return " // ".join(str(f) for f in faces)
        return None

    def _get(self, path: str, params: dict[str, str]) -> dict[str, Any] | None:
        wait = MIN_INTERVAL_S - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()
        response = self._client.get(path, params=params)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result

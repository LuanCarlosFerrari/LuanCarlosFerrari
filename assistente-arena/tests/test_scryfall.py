from __future__ import annotations

from pathlib import Path

from fakes import scryfall_client

from assistente_arena.cards.scryfall import Scryfall


def test_exact_name_with_portuguese_double_faced(tmp_path: Path) -> None:
    calls: list[str] = []
    scry = Scryfall(tmp_path / "c.db", scryfall_client(calls))
    card, corrected = scry.find("Tovolar, Dire Overlord")
    assert card is not None and not corrected
    assert card.display == (
        "Tovolar, Soberano Medonho // Tovolar, Flagelo da Meia-noite "
        "(Tovolar, Dire Overlord // Tovolar, the Midnight Scourge)"
    )
    assert card.arena_id == 78613 and card.mana_cost == "{1}{R}{G}"


def test_fuzzy_correction_and_cache(tmp_path: Path) -> None:
    calls: list[str] = []
    scry = Scryfall(tmp_path / "c.db", scryfall_client(calls))
    card, corrected = scry.find("Forrest")
    assert card is not None and corrected and card.display == "Floresta (Forest)"
    count = len(calls)
    assert scry.find("forrest") == (card, True)
    assert len(calls) == count  # veio do cache


def test_not_found_is_cached(tmp_path: Path) -> None:
    calls: list[str] = []
    scry = Scryfall(tmp_path / "c.db", scryfall_client(calls))
    assert scry.find("Carta Inexistente") == (None, False)
    count = len(calls)
    assert scry.find("Carta Inexistente") == (None, False)
    assert len(calls) == count

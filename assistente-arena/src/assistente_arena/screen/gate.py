"""Decide se a análise de tela é permitida agora.

Regra: nunca durante uma partida. Na captura ao vivo, se não for possível
confirmar pelo log que você está fora da partida, a análise fica bloqueada.
"""

from __future__ import annotations

from dataclasses import dataclass

from assistente_arena.arena_log.reader import ArenaState


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason: str
    warning: str = ""


def evaluate(state: ArenaState | None, *, live: bool) -> GateDecision:
    if state is not None and state.in_match:
        return GateDecision(False, "Partida em andamento: a análise de tela fica bloqueada.")

    if not live:
        warning = ""
        if state is None:
            warning = "Player.log não encontrado; analisando só o arquivo de imagem informado."
        return GateDecision(True, "Imagem de arquivo, fora da partida.", warning)

    if state is None:
        return GateDecision(
            False,
            "Player.log não encontrado. Abra o Arena com o Registro Detalhado ligado.",
        )
    if state.detailed_logs is False:
        return GateDecision(
            False,
            "O Registro Detalhado está desligado. Ative em Opções → Conta → "
            "Registro Detalhado (Suporte a plugins) e reinicie o Arena.",
        )
    if state.detailed_logs is None and not state.saw_game_json:
        return GateDecision(
            False,
            "Não consegui confirmar pelo log que você está fora da partida "
            "(o Registro Detalhado está ligado?).",
        )
    return GateDecision(True, "Fora da partida.")

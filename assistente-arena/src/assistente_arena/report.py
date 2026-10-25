"""Texto do relatório no terminal e exportação no formato do Arena."""

from __future__ import annotations

from assistente_arena.claude.costs import format_brl
from assistente_arena.flow import CheckedCard, Report

SCREEN_NAMES = {
    "construtor_de_deck": "Construtor de decks",
    "colecao": "Coleção",
    "outra": "Outra tela",
}
STATUS_MARK = {
    "ok": "  ",
    "corrigida": "~ ",
    "conferir": "? ",
    "nao_encontrada": "! ",
}


def card_label(item: CheckedCard) -> str:
    if item.card is not None:
        return item.card.display
    return item.read.nome_na_tela or item.read.nome_ingles


def arena_export(cards: list[CheckedCard]) -> str:
    """Lista no formato de importação do Arena (nomes em inglês)."""
    lines = ["Deck"]
    for item in cards:
        name = item.card.name_en if item.card else item.read.nome_ingles
        lines.append(f"{item.read.quantidade} {name.split('//')[0].strip()}")
    return "\n".join(lines)


def render(report: Report) -> str:
    out: list[str] = []
    if report.blocked:
        out.append(f"✖ {report.blocked}")
        out.extend(f"! {w}" for w in report.warnings)
        if report.cost_brl:
            out.append(f"Custo desta chamada: {format_brl(report.cost_brl)}")
        return "\n".join(out)

    analysis = report.analysis
    assert analysis is not None
    out.append(f"Tela: {SCREEN_NAMES[analysis.tipo_tela]}")
    if analysis.nome_do_deck:
        out.append(f"Deck: {analysis.nome_do_deck}")
    if analysis.formato_visivel:
        out.append(f"Formato na tela: {analysis.formato_visivel}")
    out.extend(f"! {w}" for w in report.warnings)

    total = sum(c.read.quantidade for c in report.cards)
    out.append("")
    out.append(f"Cartas reconhecidas ({total}):")
    for item in report.cards:
        out.append(f"  {STATUS_MARK[item.status]}{item.read.quantidade}x {card_label(item)}")
    if any(c.status != "ok" for c in report.cards):
        out.append("  Legenda: ~ nome corrigido pelo Scryfall · ? conferir · ! não encontrada")
    if analysis.tipo_tela == "construtor_de_deck" and total and total != 60:
        out.append(f"  Atenção: {total} cartas lidas (o normal no Histórico é 60).")

    guide = analysis.guia
    if analysis.tipo_tela == "construtor_de_deck" and guide.resumo:
        out.append("")
        out.append("── Como jogar este deck ──")
        out.append(guide.resumo)
        if guide.plano_de_jogo:
            out.extend(["", "Plano de jogo:", guide.plano_de_jogo])
        if guide.mulligan:
            out.extend(["", "Mulligan:", guide.mulligan])
        if guide.dicas:
            out.extend(["", "Dicas:"])
            out.extend(f"  • {d}" for d in guide.dicas)
        if guide.trocas:
            out.extend(["", "Trocas sugeridas:"])
            out.extend(f"  − {t.sai}  →  + {t.entra}\n    {t.motivo}" for t in guide.trocas)

    out.append("")
    out.append(
        f"Custo: {format_brl(report.cost_brl)} · no mês: {format_brl(report.month_brl)} "
        f"de {format_brl(report.budget_brl)} · cotação: {report.rate_source}"
    )
    return "\n".join(out)

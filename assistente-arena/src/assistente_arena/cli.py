"""Linha de comando do protótipo: `assistente-arena <comando>`."""

from __future__ import annotations

import argparse
import contextlib
import getpass
import json
import sys
import time
from pathlib import Path

from assistente_arena.arena_log.events import DetailedLogsStatus, LogReset, MatchEnded, MatchStarted
from assistente_arena.arena_log.monitor import LogMonitor, read_state
from assistente_arena.arena_log.tailer import default_log_path
from assistente_arena.claude.costs import Ledger, format_brl
from assistente_arena.config import Settings, data_dir, delete_api_key, get_api_key, set_api_key
from assistente_arena.flow import Report, run_analysis
from assistente_arena.report import arena_export, render
from assistente_arena.screen import capture
from assistente_arena.screen.gate import evaluate

MIN_SECONDS_BETWEEN_PRESSES = 5.0


def _print_report(report: Report, args: argparse.Namespace) -> None:
    print(render(report))
    if report.analysis and report.cards:
        if args.exportar:
            print("\n── Para importar no Arena ──")
            print(arena_export(report.cards))
        if args.json:
            data = report.analysis.model_dump()
            Path(args.json).write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
            print(f"\nJSON salvo em {args.json}")


def cmd_analisar(args: argparse.Namespace) -> int:
    settings = Settings.load()
    log_path = Path(args.log) if args.log else default_log_path()
    state = read_state(log_path)
    if args.imagem:
        image = capture.load_file(Path(args.imagem))
        warning = ""
        live = False
    else:
        # Bloqueio antes de capturar: nada de imagem durante a partida.
        decision = evaluate(state, live=True)
        if not decision.allowed:
            print(f"✖ {decision.reason}")
            return 2
        if args.atraso:
            print(f"Capturando em {args.atraso} s — mude para a janela do Arena...")
            time.sleep(args.atraso)
        try:
            image, warning = capture.capture_arena()
        except capture.CaptureError as e:
            print(f"✖ {e}")
            return 2
        live = True
    if args.guardar_imagem:
        Path(args.guardar_imagem).write_bytes(image.png)
    print(f"Analisando imagem {image.width}×{image.height} com {settings.modelo}...")
    report = run_analysis(
        image,
        live=live,
        settings=settings,
        log_path=log_path,
        format_hint=args.formato or settings.formato_padrao,
        state=state,
    )
    if warning:
        report.warnings.insert(0, warning)
    _print_report(report, args)
    return 1 if report.blocked else 0


def cmd_observar(args: argparse.Namespace) -> int:
    settings = Settings.load()
    log_path = Path(args.log) if args.log else default_log_path()
    monitor = LogMonitor(log_path)
    monitor.poll(final=True)
    last_press = 0.0

    def describe() -> str:
        if not monitor.exists:
            return "Player.log não encontrado"
        return "EM PARTIDA — análise bloqueada" if monitor.state.in_match else "fora da partida"

    print(f"Observando {log_path}")
    print(f"Atalho: {args.atalho.upper()} analisa a janela do Arena. Ctrl+C encerra.")
    print(f"Estado: {describe()}")

    def on_idle() -> None:
        for event in monitor.poll():
            if isinstance(event, MatchStarted):
                print("▶ Partida iniciada — análise de tela bloqueada.")
            elif isinstance(event, MatchEnded):
                print("■ Partida encerrada — análise de tela liberada.")
            elif isinstance(event, LogReset):
                print("↻ O Arena reabriu; log recriado.")
            elif isinstance(event, DetailedLogsStatus) and not event.enabled:
                print("! Registro Detalhado desligado: a análise fica bloqueada.")

    def on_press() -> None:
        nonlocal last_press
        now = time.monotonic()
        if now - last_press < MIN_SECONDS_BETWEEN_PRESSES:
            return
        last_press = now
        on_idle()  # estado mais recente antes de decidir
        decision = evaluate(monitor.state if monitor.exists else None, live=True)
        if not decision.allowed:
            print(f"✖ {decision.reason}")
            return
        try:
            image, warning = capture.capture_arena()
        except capture.CaptureError as e:
            print(f"✖ {e}")
            return
        print(f"\nAnalisando imagem {image.width}×{image.height} com {settings.modelo}...")
        report = run_analysis(
            image,
            live=True,
            settings=settings,
            log_path=log_path,
            format_hint=args.formato or settings.formato_padrao,
            state=monitor.state,
        )
        if warning:
            report.warnings.insert(0, warning)
        _print_report(report, args)
        print(f"\nEstado: {describe()}")

    from assistente_arena.screen.hotkey import run_hotkey_loop

    try:
        run_hotkey_loop(args.atalho, on_press, on_idle)
    except KeyboardInterrupt:
        print("\nEncerrado.")
    except RuntimeError as e:
        print(f"✖ {e}")
        return 2
    finally:
        monitor.close()
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    settings = Settings.load()
    log_path = Path(args.log) if args.log else default_log_path()
    state = read_state(log_path)
    print(f"Pasta de dados: {data_dir()}")
    print(f"Player.log: {log_path} {'(encontrado)' if state else '(não encontrado)'}")
    if state:
        detailed = {True: "ligado", False: "DESLIGADO", None: "não confirmado"}[state.detailed_logs]
        print(f"Registro Detalhado: {detailed}")
        print(f"Partidas vistas neste log: {state.matches_seen}")
        print(f"Agora: {'em partida' if state.in_match else 'fora da partida'}")
    decision = evaluate(state, live=True)
    print(f"Análise de tela: {'liberada' if decision.allowed else 'bloqueada'} — {decision.reason}")
    print(f"Chave da API: {'configurada' if get_api_key() else 'não configurada'}")
    print(f"Modelo: {settings.modelo} (esforço {settings.esforco})")
    ledger = Ledger(data_dir() / "gastos.db")
    try:
        print(
            f"Gasto no mês: {format_brl(ledger.month_total_brl())} de "
            f"{format_brl(settings.orcamento_mensal_brl)} ({ledger.month_count()} chamadas)"
        )
    finally:
        ledger.close()
    return 0


def cmd_chave(args: argparse.Namespace) -> int:
    try:
        if args.remover:
            delete_api_key()
            print("Chave removida do Gerenciador de Credenciais.")
            return 0
        value = getpass.getpass("Cole a chave da API da Anthropic (não aparece na tela): ").strip()
        if not value:
            print("Nada foi salvo.")
            return 1
        set_api_key(value)
    except Exception as e:
        print(f"✖ Não consegui acessar o cofre de credenciais ({e}).")
        print("  Alternativa: defina a variável de ambiente ANTHROPIC_API_KEY.")
        return 2
    print("Chave salva no Gerenciador de Credenciais do Windows.")
    return 0


def cmd_atalho(args: argparse.Namespace) -> int:
    from assistente_arena.shortcut import manage_shortcut

    try:
        lines = manage_shortcut(start_menu=not args.so_area_de_trabalho, remove=args.remover)
    except RuntimeError as e:
        print(f"✖ {e}")
        return 2
    for line in lines:
        print(line.replace("criado:", "Atalho criado:").replace("removido:", "Atalho removido:"))
    if not args.remover:
        print('Dê dois cliques em "Assistente Arena" para abrir; Ctrl+Shift+A analisa a tela.')
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    monitor = LogMonitor(Path(args.arquivo))
    events = monitor.poll() + monitor.poll(final=True)
    monitor.close()
    for event in events:
        print(event)
    failures = dict(monitor.reader.stats.failures)
    print(f"\n{len(events)} eventos · falhas de leitura: {failures or 'nenhuma'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="assistente-arena", description="Assistente Arena — protótipo da análise de tela."
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--formato", help="formato que você pretende jogar (padrão: Histórico)")
        p.add_argument("--log", help="caminho do Player.log (padrão: o do Arena)")
        p.add_argument("--exportar", action="store_true", help="mostra a lista para o Arena")
        p.add_argument("--json", help="salva a análise neste arquivo .json")

    p = sub.add_parser("analisar", help="analisa a janela do Arena (ou uma imagem) agora")
    common(p)
    p.add_argument("--imagem", help="analisa um arquivo de imagem em vez de capturar a tela")
    p.add_argument("--atraso", type=int, default=0, help="segundos de espera antes de capturar")
    p.add_argument("--guardar-imagem", help="salva a imagem enviada (padrão: não salva)")
    p.set_defaults(func=cmd_analisar)

    p = sub.add_parser("observar", help="fica em segundo plano e analisa ao apertar o atalho")
    common(p)
    p.add_argument("--atalho", default="ctrl+shift+a", help="padrão: ctrl+shift+a")
    p.set_defaults(func=cmd_observar)

    p = sub.add_parser("status", help="mostra log, bloqueio, chave e gastos")
    p.add_argument("--log", help="caminho do Player.log")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("chave", help="salva a chave da API no cofre do Windows")
    p.add_argument("--remover", action="store_true")
    p.set_defaults(func=cmd_chave)

    p = sub.add_parser("atalho", help="cria o atalho com ícone na área de trabalho")
    p.add_argument("--remover", action="store_true", help="apaga os atalhos criados")
    p.add_argument("--so-area-de-trabalho", action="store_true", help="não cria no Menu Iniciar")
    p.set_defaults(func=cmd_atalho)

    p = sub.add_parser("log", help="reproduz um Player.log e lista os eventos (depuração)")
    p.add_argument("arquivo")
    p.set_defaults(func=cmd_log)
    return parser


def _ask_yes(question: str) -> bool:
    answer = input(f"{question} [S/n] ").strip().lower()
    return answer in ("", "s", "sim", "y", "yes")


def cmd_iniciar() -> int:
    """Dois cliques no ícone/executável: configura o que falta e começa a observar."""
    print("Assistente Arena — análise de tela fora das partidas\n")
    settings = Settings.load()

    if not get_api_key():
        print("Primeiro uso: falta a chave da API da Anthropic (crie em console.anthropic.com).")
        if cmd_chave(argparse.Namespace(remover=False)) != 0:
            return 2
        print()

    if sys.platform == "win32" and not settings.atalho_oferecido:
        settings.atalho_oferecido = True
        settings.save()
        if _ask_yes("Criar um atalho com ícone na área de trabalho?"):
            cmd_atalho(argparse.Namespace(remover=False, so_area_de_trabalho=False))
        print()

    cmd_status(argparse.Namespace(log=None))
    print()
    return cmd_observar(
        argparse.Namespace(formato=None, log=None, exportar=True, json=None, atalho="ctrl+shift+a")
    )


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args_list = sys.argv[1:] if argv is None else argv
    if not args_list:
        # Aberto por dois cliques: a janela não pode sumir antes de você ler.
        try:
            return cmd_iniciar()
        except KeyboardInterrupt:
            return 0
        except Exception as e:
            print(f"\n✖ Erro inesperado: {e}")
            return 1
        finally:
            with contextlib.suppress(EOFError, KeyboardInterrupt):
                input("\nPressione Enter para fechar...")
    args = build_parser().parse_args(args_list)
    result: int = args.func(args)
    return result

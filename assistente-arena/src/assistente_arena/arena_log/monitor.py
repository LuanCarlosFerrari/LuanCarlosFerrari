"""Une Tailer + LogReader: leitura única ou acompanhamento contínuo."""

from __future__ import annotations

from pathlib import Path

from assistente_arena.arena_log.events import Event
from assistente_arena.arena_log.reader import ArenaState, LogReader
from assistente_arena.arena_log.tailer import Tailer


class LogMonitor:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.reader = LogReader()
        self._tailer = Tailer(path)

    @property
    def state(self) -> ArenaState:
        return self.reader.state

    @property
    def exists(self) -> bool:
        return self.path.exists()

    def poll(self, final: bool = False) -> list[Event]:
        """Lê o que chegou. Se o arquivo parou, fecha a entrada pendente.

        `final=True` também processa uma última linha sem quebra (leitura única);
        no acompanhamento contínuo ela pode estar sendo escrita, então espera.
        """
        reset, lines = self._tailer.poll()
        events: list[Event] = []
        if reset:
            events.extend(self.reader.reset())
        if lines:
            events.extend(self.reader.feed_lines(lines))
        else:
            if final:
                events.extend(self.reader.feed_lines(self._tailer.pending_lines()))
            events.extend(self.reader.flush())
        return events

    def close(self) -> None:
        self._tailer.close()


def read_state(path: Path) -> ArenaState | None:
    """Lê o log inteiro uma vez. Devolve None se o arquivo não existir."""
    if not path.exists():
        return None
    monitor = LogMonitor(path)
    try:
        monitor.poll()
        monitor.poll(final=True)  # segunda passada fecha a última entrada
    finally:
        monitor.close()
    return monitor.state

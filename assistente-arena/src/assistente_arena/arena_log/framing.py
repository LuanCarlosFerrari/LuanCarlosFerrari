"""Separa o Player.log em entradas e extrai os objetos JSON de cada uma.

Uma entrada começa num cabeçalho `[UnityCrossThreadLogger]` ou numa linha de
resposta `<==` e vai até a próxima. O JSON pode ocupar várias linhas e pode
vir escapado dentro de um campo `request` (parse duplo).
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

HEADER = "[UnityCrossThreadLogger]"
RESPONSE = "<=="


@dataclass
class Entry:
    header: str
    body: str
    objects: list[dict[str, Any]] = field(default_factory=list)


def _starts_entry(line: str) -> bool:
    return line.startswith(HEADER) or line.startswith(RESPONSE)


def extract_json_objects(text: str) -> Iterator[dict[str, Any]]:
    """Encontra objetos JSON de nível superior contando chaves fora de strings."""
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            if depth > 0:
                in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    yield _unwrap_request(obj)


def _unwrap_request(obj: dict[str, Any]) -> dict[str, Any]:
    request = obj.get("request")
    if isinstance(request, str) and request.lstrip().startswith("{"):
        with contextlib.suppress(json.JSONDecodeError):
            obj = {**obj, "request": json.loads(request)}
    return obj


class EntrySplitter:
    """Recebe linhas aos poucos (tail) e devolve entradas completas."""

    def __init__(self) -> None:
        self._header: str | None = None
        self._body: list[str] = []

    def feed(self, lines: Iterable[str]) -> Iterator[Entry]:
        for line in lines:
            if _starts_entry(line):
                done = self._close()
                if done is not None:
                    yield done
                self._header = line
                self._body = []
            elif self._header is not None:
                self._body.append(line)
            # Linhas antes do primeiro cabeçalho são diagnóstico da Unity: ignoradas.

    def flush(self) -> Iterator[Entry]:
        done = self._close()
        if done is not None:
            yield done

    def _close(self) -> Entry | None:
        if self._header is None:
            return None
        body = "\n".join(self._body)
        text = self._header + "\n" + body
        entry = Entry(self._header, body, list(extract_json_objects(text)))
        self._header = None
        self._body = []
        return entry


def split_entries(lines: Iterable[str]) -> list[Entry]:
    splitter = EntrySplitter()
    entries = list(splitter.feed(lines))
    entries.extend(splitter.flush())
    return entries

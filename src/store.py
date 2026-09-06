"""File-backed storage for the pipeline's state.

Everything lives under docs/data/ so the same JSON files that the
pipeline writes are the files GitHub Pages serves -- no separate
"data" vs "public" copy to keep in sync.

    docs/data/seen_ids.json    -> [str, ...]              dedup index
    docs/data/incidents.json   -> [Incident, ...]          full incident log
    docs/data/score.json       -> Score                    latest computed score
    docs/data/history.json     -> [Score, ...]              score over time (trend)

Swap this module out for a database-backed one later without touching
ingest/extract/scoring -- they only depend on the methods below.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dateutils import age_days


class JsonStore:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        return self.data_dir / name

    def _read(self, name: str, default: Any) -> Any:
        path = self._path(name)
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, name: str, value: Any) -> None:
        path = self._path(name)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
        tmp.replace(path)  # atomic on POSIX

    # -- dedup ----------------------------------------------------------
    def load_seen_ids(self) -> set[str]:
        return set(self._read("seen_ids.json", []))

    def save_seen_ids(self, ids: set[str]) -> None:
        # Cap growth: keep the most recent 20k ids (FIFO-ish via sort is not
        # possible without insertion order, so this is a soft cap only).
        ids_list = list(ids)
        if len(ids_list) > 20000:
            ids_list = ids_list[-20000:]
        self._write("seen_ids.json", ids_list)

    # -- incidents --------------------------------------------------------
    def load_incidents(self) -> list[dict]:
        return self._read("incidents.json", [])

    def append_incidents(self, new_incidents: list[dict]) -> list[dict]:
        incidents = self.load_incidents()
        incidents.extend(new_incidents)
        self._write("incidents.json", incidents)
        return incidents

    def prune_old_incidents(self, window_days: int, now: datetime | None = None) -> list[dict]:
        """Drop incidents whose `date` is older than the rolling window.

        This is the actual deletion the rolling-window design calls for --
        `scoring.py` merely *ignores* out-of-window incidents when computing
        a score, it never removes them. Without this, incidents.json (and
        the seen_ids dedup index) would grow forever even though only
        metadata/IDs/URLs/timestamps/scores are ever stored (no article
        full text, so this is about bounded storage and staying "current",
        not copyright).
        """
        now = now or datetime.now(timezone.utc)
        incidents = self.load_incidents()
        kept = [inc for inc in incidents if age_days(inc.get("date"), now=now) <= window_days]
        if len(kept) != len(incidents):
            self._write("incidents.json", kept)
        return kept

    # -- score / history --------------------------------------------------
    def save_score(self, score: dict) -> None:
        self._write("score.json", score)

    def append_history(self, score: dict, max_entries: int = 1000) -> None:
        history = self._read("history.json", [])
        history.append(score)
        if len(history) > max_entries:
            history = history[-max_entries:]
        self._write("history.json", history)

    def prune_old_history(self, window_days: int, now: datetime | None = None) -> None:
        """Drop score-history entries older than the rolling window, keyed
        on their own `computed_at` timestamp (independent of incident
        dates -- this is about how much score *trend* we keep, not which
        incidents are still in scope).
        """
        now = now or datetime.now(timezone.utc)
        history = self._read("history.json", [])
        kept = [h for h in history if age_days(h.get("computed_at"), now=now) <= window_days]
        if len(kept) != len(history):
            self._write("history.json", kept)

    # -- top 10 synthesis ---------------------------------------------------
    def save_top10(self, top10: dict) -> None:
        self._write("top10.json", top10)

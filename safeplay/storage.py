from __future__ import annotations

from dataclasses import asdict
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

from .models import Movie, Scene

TTL = timedelta(days=29)


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self._migrate()
        self.purge_expired()

    def _migrate(self):
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version > 1:
            raise RuntimeError("Database was created by a newer SafePlay version")
        if version == 0:
            with self.db:
                self.db.executescript("""
                CREATE TABLE preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE guides (id TEXT PRIMARY KEY, title TEXT NOT NULL, year INTEGER,
                    runtime REAL, source TEXT NOT NULL, fetched_at TEXT NOT NULL, warnings TEXT NOT NULL);
                CREATE TABLE scenes (guide_id TEXT NOT NULL, key TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY (guide_id, key), FOREIGN KEY (guide_id) REFERENCES guides(id));
                CREATE TABLE edits (guide_id TEXT NOT NULL, key TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY (guide_id, key));
                CREATE TABLE activity (id INTEGER PRIMARY KEY, at TEXT NOT NULL, kind TEXT NOT NULL,
                    detail TEXT NOT NULL);
                PRAGMA user_version=1;
                """)

    def preference(self, key: str, default=None):
        row = self.db.execute("SELECT value FROM preferences WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_preference(self, key: str, value):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO preferences VALUES (?,?)", (key, json.dumps(value)))

    def log(self, kind: str, detail: str):
        at = datetime.now(timezone.utc).isoformat()
        with self.db:
            self.db.execute("INSERT INTO activity(at,kind,detail) VALUES (?,?,?)", (at, kind, detail[:2000]))

    def recent(self, limit=200):
        return [tuple(r) for r in self.db.execute(
            "SELECT at,kind,detail FROM activity ORDER BY id DESC LIMIT ?", (limit,))]

    def save_guide(self, movie: Movie):
        if not movie.external_id:
            raise ValueError("Guide requires an external ID")
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO guides VALUES (?,?,?,?,?,?,?)", (
                movie.external_id, movie.title, movie.year, movie.runtime, movie.source,
                datetime.now(timezone.utc).isoformat(), json.dumps(movie.warnings)))
            self.db.execute("DELETE FROM scenes WHERE guide_id=?", (movie.external_id,))
            self.db.executemany("INSERT INTO scenes VALUES (?,?,?)", [
                (movie.external_id, s.key, json.dumps(asdict(s))) for s in movie.scenes])

    def save_edit(self, guide_id: str, scene: Scene, reviewed=False):
        if reviewed:
            scene.manual = True
            scene.reliability = "manual" if scene.valid() else "unreliable"
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO edits VALUES (?,?,?)", (
                guide_id, scene.key, json.dumps(asdict(scene))))

    def purge_expired(self):
        cutoff = (datetime.now(timezone.utc) - TTL).isoformat()
        with self.db:
            self.db.execute("DELETE FROM scenes WHERE guide_id IN (SELECT id FROM guides WHERE fetched_at < ?)", (cutoff,))
            self.db.execute("DELETE FROM guides WHERE fetched_at < ?", (cutoff,))

    def load_guide(self, guide_id: str, allow_stale=False) -> Movie | None:
        row = self.db.execute("SELECT * FROM guides WHERE id=?", (guide_id,)).fetchone()
        if not row:
            return None
        age = datetime.now(timezone.utc) - datetime.fromisoformat(row["fetched_at"])
        if age > TTL and not allow_stale:
            self.purge_expired()
            return None
        scenes = [Scene(**json.loads(r[0])) for r in self.db.execute(
            "SELECT payload FROM scenes WHERE guide_id=?", (guide_id,))]
        edits = {r["key"]: Scene(**json.loads(r["payload"])) for r in self.db.execute(
            "SELECT key,payload FROM edits WHERE guide_id=?", (guide_id,))}
        scenes = [edits.pop(s.key, s) for s in scenes]
        scenes.extend(edits.values())
        return Movie(row["title"], row["year"], guide_id, row["runtime"],
                     row["source"], scenes, json.loads(row["warnings"]))

    def close(self):
        self.db.close()

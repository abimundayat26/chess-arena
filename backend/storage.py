"""Small local SQLite snapshot store for authoritative games."""

import json
from pathlib import Path
import sqlite3
from time import time
from typing import Callable


class LocalStorage:
    def __init__(self, path: str, wall_clock: Callable[[], float] = time):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(target, check_same_thread=False)
        self.connection.execute("CREATE TABLE IF NOT EXISTS games (id TEXT PRIMARY KEY, payload TEXT NOT NULL, saved_wall REAL NOT NULL)")
        self.connection.commit()
        self.wall_clock = wall_clock

    def save(self, game_id: str, payload: dict) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO games(id, payload, saved_wall) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, saved_wall=excluded.saved_wall",
                (game_id, json.dumps(payload, separators=(",", ":")), self.wall_clock()),
            )

    def load_all(self) -> list[tuple[str, str, float]]:
        return [(game_id, payload, saved_wall) for game_id, payload, saved_wall
                in self.connection.execute("SELECT id, payload, saved_wall FROM games")]

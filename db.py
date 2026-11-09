"""Lưu trữ trận đấu vào SQLite và đọc ra DataFrame."""
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent / "football.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    id           INTEGER PRIMARY KEY,
    competition  TEXT NOT NULL,
    season       INTEGER,
    matchday     INTEGER,
    utc_date     TEXT NOT NULL,
    status       TEXT,
    home_id      INTEGER,
    home_team    TEXT NOT NULL,
    away_id      INTEGER,
    away_team    TEXT NOT NULL,
    home_goals   INTEGER,
    away_goals   INTEGER,
    ht_home      INTEGER,
    ht_away      INTEGER,
    winner       TEXT
);
CREATE INDEX IF NOT EXISTS idx_matches_comp ON matches(competition, season);
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(utc_date);
"""

COLUMNS = [
    "id", "competition", "season", "matchday", "utc_date", "status",
    "home_id", "home_team", "away_id", "away_team",
    "home_goals", "away_goals", "ht_home", "ht_away", "winner",
]


def connect(path=DB_PATH):
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def upsert_matches(rows, path=DB_PATH):
    """rows: list[dict] có đủ các khóa trong COLUMNS. Trả về số dòng ghi."""
    if not rows:
        return 0
    placeholders = ",".join(f":{c}" for c in COLUMNS)
    sql = f"INSERT OR REPLACE INTO matches ({','.join(COLUMNS)}) VALUES ({placeholders})"
    with connect(path) as conn:
        conn.executemany(sql, rows)
    return len(rows)


def load_matches(competition=None, path=DB_PATH):
    with connect(path) as conn:
        if competition:
            df = pd.read_sql_query(
                "SELECT * FROM matches WHERE competition = ? ORDER BY utc_date",
                conn, params=(competition,))
        else:
            df = pd.read_sql_query("SELECT * FROM matches ORDER BY utc_date", conn)
    if not df.empty:
        df["utc_date"] = pd.to_datetime(df["utc_date"], utc=True)
    return df


def list_competitions(path=DB_PATH):
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT competition, COUNT(*) FROM matches GROUP BY competition ORDER BY competition"
        ).fetchall()
    return rows


def clear_competition(competition, path=DB_PATH):
    with connect(path) as conn:
        conn.execute("DELETE FROM matches WHERE competition = ?", (competition,))

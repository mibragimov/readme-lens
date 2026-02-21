from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scans (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          owner TEXT NOT NULL,
          repo TEXT NOT NULL,
          branch TEXT NOT NULL,
          sha TEXT NOT NULL,
          scanned_at INTEGER NOT NULL,
          result_json TEXT NOT NULL,
          UNIQUE(owner, repo, sha)
        )
        """
    )
    conn.commit()


def get_cached(conn: sqlite3.Connection, owner: str, repo: str, sha: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT result_json FROM scans WHERE owner=? AND repo=? AND sha=?",
        (owner, repo, sha),
    ).fetchone()
    if not row:
        return None
    return json.loads(row["result_json"])


def save_scan(
    conn: sqlite3.Connection,
    *,
    owner: str,
    repo: str,
    branch: str,
    sha: str,
    scanned_at: int,
    result: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO scans(owner, repo, branch, sha, scanned_at, result_json)
        VALUES(?, ?, ?, ?, ?, ?)
        """,
        (owner, repo, branch, sha, scanned_at, json.dumps(result, ensure_ascii=False)),
    )
    conn.commit()


def list_recent(conn: sqlite3.Connection, limit: int = 20):
    return conn.execute(
        """
        SELECT owner, repo, branch, sha, scanned_at
        FROM scans
        ORDER BY scanned_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

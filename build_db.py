#!/usr/bin/env python3
"""Reconstruct the Dictionarry relational snapshot that Profilarr consumes.

Clones (or reuses) two upstream dependencies:
  - Dictionarry-Hub/schema   (DDL: ops/0.schema.sql .. 3.quality-group-member-position.sql)
  - Dictionarry-Hub/database (data: ops/0.rosettarr.sql .. N.sql migrations)

Then replays schema ops, then database ops, each in strict numeric-prefix order,
into a local SQLite file. Foreign keys are enabled so the cascading deletes used
by the upstream migrations behave the same way Profilarr sees them.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

SCHEMA_REPO = "https://github.com/Dictionarry-Hub/schema.git"
DATABASE_REPO = "https://github.com/Dictionarry-Hub/database.git"

HERE = Path(__file__).resolve().parent


def clone_or_update(url: str, dest: Path, depth: int | None = 1) -> None:
    if dest.exists() and (dest / ".git").is_dir():
        # Refresh an existing checkout (avoids re-downloading on every run).
        subprocess.run(
            ["git", "-C", str(dest), "fetch", "--all", "--quiet"],
            check=False,
        )
        subprocess.run(
            ["git", "-C", str(dest), "reset", "--hard", "origin/HEAD", "--quiet"],
            check=False,
        )
        return
    if dest.exists():
        shutil.rmtree(dest)
    cmd = ["git", "clone", "--quiet"]
    if depth:
        cmd += ["--depth", str(depth)]
    cmd += [url, str(dest)]
    subprocess.run(cmd, check=True)


def replay_dir(db: sqlite3.Connection, ops_dir: Path, kind: str) -> None:
    """Replay ops/*.sql in numeric-prefix order into the connection."""
    sqls = sorted(ops_dir.glob("*.sql"), key=lambda p: numeric_key(p.name))
    for path in sqls:
        db.executescript(path.read_text())
    print(f"[build_db] replayed {len(sqls)} {kind} op file(s) from {ops_dir}")


def numeric_key(name: str) -> int:
    prefix = name.split(".", 1)[0]
    try:
        return int(prefix)
    except ValueError:
        return 1_000_000_000  # unpinned numeric ops sort last


def build(deps_dir: Path, db_path: Path) -> None:
    deps_dir.mkdir(parents=True, exist_ok=True)
    schema_dir = deps_dir / "schema"
    database_dir = deps_dir / "database"

    clone_or_update(SCHEMA_REPO, schema_dir)
    clone_or_update(DATABASE_REPO, database_dir)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    db = sqlite3.connect(db_path)
    try:
        db.execute("PRAGMA foreign_keys = ON")
        replay_dir(db, schema_dir / "ops", "schema")
        replay_dir(db, database_dir / "ops", "database")
        db.commit()
    finally:
        db.close()

    print(f"[build_db] wrote {db_path}")
    print(f"[build_db] schema+data at {db_path} ({db_path.stat().st_size} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--deps",
        type=Path,
        default=HERE / ".deps",
        help="directory to clone build-time deps into (default: .deps)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=HERE / ".deps" / "dictionarry.sqlite",
        help="output SQLite path (default: .deps/dictionarry.sqlite)",
    )
    args = parser.parse_args()
    build(args.deps, args.db)


if __name__ == "__main__":
    main()
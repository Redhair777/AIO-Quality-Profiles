#!/usr/bin/env python3
"""Reconstruct a Profilarr PCD relational snapshot that AIOStreams consumes.

Clones (or reuses) two upstream dependencies:
  - Dictionarry-Hub/schema   (DDL: ops/0.schema.sql .. 3.quality-group-member-position.sql)
  - a Profilarr PCD database, either Dictionarry-Hub/database or
    Dumpstarr/Database (both: data ops/0..N.sql migrations, same schema)

Then replays schema ops, then database ops, each in strict numeric-prefix order,
into a local SQLite file. Foreign keys are enabled so the cascading deletes used
by the upstream migrations behave the same way Profilarr sees them.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

SCHEMA_REPO = "https://github.com/Dictionarry-Hub/schema.git"
DATABASE_REPOS = {
    "dictionarry": "https://github.com/Dictionarry-Hub/database.git",
    "dumpstarr": "https://github.com/Dumpstarr/Database.git",
}

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
    """Replay ops/*.sql in numeric-prefix order into the connection.

    The Profilarr PCD export format records row *updates* as plain
    INSERT statements (a bare INSERT with no surrounding DELETE, labelled
    in the SQL comments as an "update" op). Replaying those verbatim hits
    the table's unique/PK constraint; so rewrite INSERT INTO -> INSERT OR
    REPLACE INTO so an existing row is updated instead of rejected. This
    also guards against the silent-drop behaviour where executescript()
    aborts all remaining statements in a file on the first error.
    """
    insert_re = re.compile(r"\bINSERT INTO\b", re.IGNORECASE)
    sqls = sorted(ops_dir.glob("*.sql"), key=lambda p: numeric_key(p.name))
    for path in sqls:
        sql = path.read_text()
        sql = insert_re.sub("INSERT OR REPLACE INTO", sql)
        db.executescript(sql)
    print(f"[build_db] replayed {len(sqls)} {kind} op file(s) from {ops_dir}")


def numeric_key(name: str) -> int:
    prefix = name.split(".", 1)[0]
    try:
        return int(prefix)
    except ValueError:
        return 1_000_000_000  # unpinned numeric ops sort last


def build(deps_dir: Path, db_path: Path, source: str = "dictionarry") -> None:
    deps_dir.mkdir(parents=True, exist_ok=True)
    schema_dir = deps_dir / "schema"
    database_dir = deps_dir / ("database" if source == "dictionarry" else "dumpstarr")

    clone_or_update(SCHEMA_REPO, schema_dir)
    clone_or_update(DATABASE_REPOS[source], database_dir)

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
        "--source",
        choices=sorted(DATABASE_REPOS),
        default="dictionarry",
        help="Profilarr PCD database to replay (default: dictionarry)."
        " dumpstarr uses Dumpstarr/Database with the same Dictionarry-Hub/schema.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=HERE / ".deps" / "dictionarry.sqlite",
        help="output SQLite path (default: .deps/dictionarry.sqlite)",
    )
    args = parser.parse_args()
    build(args.deps, args.db, source=args.source)


if __name__ == "__main__":
    main()
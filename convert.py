#!/usr/bin/env python3
"""Convert Dictionarry quality profiles into AIOStreams "Synced" files.

For every quality profile in the Dictionarry snapshot this emits:
  profiles/<slug>.expressions.json   -> rankedStreamExpressions  (per-arr-side items)
  profiles/<slug>.regexes.json       -> rankedRegexPatterns      (named regexes used)

Condition semantics mirror Profilarr's evaluator (and Radarr/Sonarr):
  - conditions are filtered per target arr type ('all' or matching side;
    'quality_modifier' is dropped for sonarr, 'release_type' for radarr)
  - conditions are grouped by type; between types -> AND
  - within a type: if any condition is required, ALL required must pass and
    optionals are IGNORED; otherwise at least ONE must pass (OR, via merge)
  - a condition's negate flag inverts its own match

Scoring: a profile/CF can carry a per-side score; each side is emitted as a
separate ranked expression item guarded by queryType ('movie'/'series') carrying
its own score. Regexes referenced by a profile are emitted with the 'i' flag
(Radarr compiles all specs with RegexOptions.IgnoreCase).

Verification: expression items are structurally validated (comment/quote/paren
balance) and regexes are JS-compiled with Node when available.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "profiles"

# Profilarr PCD db default paths mirroring build_db.py's --source.
SOURCE_DBS = {
    "dictionarry": HERE / ".deps" / "dictionarry.sqlite",
    "dumpstarr": HERE / ".deps" / "dumpstarr.sqlite",
    "trash-pcd": HERE / ".deps" / "trash-pcd.sqlite",
}

# Source value -> AIOStreams quality names (canonical spelling; the engine
# compares case-insensitively). A Dictionarry source covers several qualities.
SOURCE_TO_QUALITIES: dict[str, list[str]] = {
    "television": ["HDTV"],
    "web_dl": ["WEB-DL"],
    "webrip": ["WEBRip"],
    "dvd": ["DVDRip", "DVD REMUX"],
    "bluray": ["BluRay", "BluRay REMUX"],
    "bluray_raw": ["BluRay"],  # disc-only (non-remux) bluray
}

# quality_modifier value -> AIOStreams quality names.
MODIFIER_TO_QUALITIES: dict[str, list[str]] = {
    "remux": ["BluRay REMUX", "DVD REMUX"],
    # AIOStreams has no BR-DISK quality; a full-disc bluray parses as plain
    # 'BluRay' (its non-remux bluray regex) -- documented approximation.
    "brdisk": ["BluRay"],
}

# release_type value -> AIOStreams seasonPack() mode ('seasonPack'|'onlySeasons').
RELEASE_TYPE_TO_MODE: dict[str, str] = {
    "season_pack": "seasonPack",
}

REGEX_TYPES = {"release_title", "release_group", "edition"}


class CFError(Exception):
    """A custom format (or one side of it) cannot be emitted."""


# ------------------------------------------------------------------ helpers

def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "profile"


def iter_profiles(db: sqlite3.Connection) -> list[str]:
    return [r[0] for r in db.execute("SELECT name FROM quality_profiles ORDER BY name")]


def profile_scores(db: sqlite3.Connection, profile: str) -> dict[str, dict[str, int]]:
    """cf_name -> {'all'|'radarr'|'sonarr' -> score} for one profile."""
    out: dict[str, dict[str, int]] = {}
    for cf, arr_type, score in db.execute(
        "SELECT custom_format_name, arr_type, score"
        " FROM quality_profile_custom_formats"
        " WHERE quality_profile_name = ?",
        (profile,),
    ):
        out.setdefault(cf, {})[arr_type] = score
    return out


def effective_score(assignments: dict[str, int], side: str) -> int | None:
    """Per-side score resolution (side-specific overrides 'all'), as in read.ts."""
    if side in assignments:
        return assignments[side]
    return assignments.get("all")


def load_conditions(db: sqlite3.Connection) -> dict[str, list[dict]]:
    """cf_name -> list of condition dicts joined with their value rows."""
    conds = db.execute(
        "SELECT custom_format_name, name, type, arr_type, negate, required, id"
        " FROM custom_format_conditions ORDER BY id"
    ).fetchall()

    by_cf: dict[str, list[dict]] = {}
    for cf, name, ctype, arr_type, negate, required, cid in conds:
        by_cf.setdefault(cf, []).append(
            {
                "name": name,
                "type": ctype,
                "arr_type": arr_type,
                "negate": bool(negate),
                "required": bool(required),
                "values": [],
            }
        )

    def attach(table: str, column: str, key: str) -> None:
        for cf, cond, value in db.execute(
            f"SELECT {table}.custom_format_name, {table}.condition_name,"
            f" {table}.{column} FROM {table}"
        ):
            for c in by_cf.get(cf, []):
                if c["name"] == cond:
                    c["values"].append({key: value})

    attach("condition_resolutions", "resolution", "resolution")
    attach("condition_sources", "source", "source")
    attach("condition_quality_modifiers", "quality_modifier", "quality_modifier")
    attach("condition_release_types", "release_type", "release_type")
    attach("condition_indexer_flags", "flag", "flag")
    attach("condition_languages", "language_name", "language")
    # year tables are empty in the snapshot; kept for completeness.
    attach("condition_years", "min_year", "min_year")
    attach("condition_years", "max_year", "max_year")

    # condition_languages also carries an except flag.
    for cf, cond, lang, except_lang in db.execute(
        "SELECT custom_format_name, condition_name, language_name,"
        " except_language FROM condition_languages"
    ):
        for c in by_cf.get(cf, []):
            if c["name"] == cond and c["type"] == "language":
                for v in c["values"]:
                    if v.get("language") == lang:
                        v["except"] = bool(except_lang)
    for c_list in by_cf.values():
        for c in c_list:
            if c["type"] == "language":
                for v in c["values"]:
                    v.setdefault("except", False)

    return by_cf


def load_patterns(db: sqlite3.Connection) -> dict[str, str]:
    """`cf\x00cond` -> regular_expression_name."""
    return {
        f"{cf}\x00{cond}": regex
        for cf, cond, regex in db.execute(
            "SELECT custom_format_name, condition_name, regular_expression_name"
            " FROM condition_patterns"
        )
    }


def load_regexes(db: sqlite3.Connection) -> dict[str, str]:
    return {
        name: sanitize_pattern(pattern)
        for name, pattern in db.execute("SELECT name, pattern FROM regular_expressions")
    }


def _escape_leading_rbracket(pattern: str) -> str:
    """Translate .NET's positional ']'-as-first-member class idiom to JS.

    In .NET, ']' as the very first member of a character class ('[]...]')
    is a literal ']'. JS has no such positional escape: '[]' is an empty
    class, and a ')' after it is an unmatched group. Escape the leading ']'
    so the class keeps matching the same member set ('[])]' -> '[\\])]').
    """
    out: list[str] = []
    in_class = False
    i = 0
    n = len(pattern)
    while i < n:
        ch = pattern[i]
        if ch == "\\" and i + 1 < n:
            out.append(ch + pattern[i + 1])
            i += 2
            continue
        if not in_class:
            if ch == "[":
                if i + 1 < n and pattern[i + 1] == "]":
                    out.append("[\\]")
                    in_class = True
                    i += 2
                    continue
                in_class = True
            out.append(ch)
            i += 1
            continue
        if ch == "]":
            in_class = False
        out.append(ch)
        i += 1
    return "".join(out)


def sanitize_pattern(pattern: str) -> str:
    """Make a Dictionarry (.NET) pattern safe for a JS RegExp.

    Radarr compiles every spec with RegexOptions.IgnoreCase, so inline
    '(?i)' toggles are no-ops and are removed (JS RegExp rejects them).
    """
    pattern = pattern.replace("(?i)", "")
    return _escape_leading_rbracket(pattern)


# ------------------------------------------------------------- SEL building

def filter_for_side(conditions: list[dict], side: str) -> list[dict]:
    """Mirror Profilarr's filterConditionsForArrType."""
    kept = []
    for c in conditions:
        if c["arr_type"] not in ("all", side):
            continue
        if side == "sonarr" and c["type"] == "quality_modifier":
            continue
        if side == "radarr" and c["type"] == "release_type":
            continue
        kept.append(c)
    return kept


def render(sel: str, base: str) -> str:
    """Substitute the BASE placeholder in an atom predicate."""
    if base == "BASE":
        return sel
    if base == "streams":
        return sel.replace("BASE", "streams")
    return sel.replace("BASE", f"({base})")


def apply_negate(sel: str, negate: bool, base: str) -> str:
    if not negate:
        return sel
    return f"negate({sel}, {base})"


def build_atoms(condition: dict, cf: str, patterns: dict[str, str],
                regexes: dict[str, str], invalid: set[str], names: set[str]) -> list[dict]:
    """One atom per condition; each is a positive predicate of BASE."""
    ctype = condition["type"]
    values = condition["values"]
    required = condition["required"]
    negate = condition["negate"]

    if ctype in REGEX_TYPES:
        name = patterns.get(f"{cf}\x00{condition['name']}")
        if not name:
            raise CFError(f"no regex linked for condition '{condition['name']}'")
        if name not in regexes:
            raise CFError(f"regex '{name}' missing from regular_expressions")
        if name in invalid:
            return [{"required": required, "impossible": True, "negate": negate,
                     "sel": "BASE"}]
        names.add(name)
        return [{"required": required, "impossible": False, "negate": negate,
                 "sel": f"regexMatched(BASE, {json.dumps(name)})"}]

    if ctype == "resolution":
        res = [v["resolution"] for v in values if "resolution" in v]
        if not res:
            raise CFError("resolution condition has no values")
        args = ", ".join(json.dumps(r) for r in res)
        return [{"required": required, "impossible": False, "negate": negate,
                 "sel": f"resolution(BASE, {args})"}]

    if ctype == "release_type":
        modes = [RELEASE_TYPE_TO_MODE.get(v["release_type"], v["release_type"])
                 for v in values if "release_type" in v]
        if not modes:
            raise CFError("release_type condition has no values")
        args = ", ".join(json.dumps(m) for m in modes)
        return [{"required": required, "impossible": False, "negate": negate,
                 "sel": f"seasonPack(BASE, {args})"}]

    if ctype in ("source", "quality_modifier"):
        key = "source" if ctype == "source" else "quality_modifier"
        mapping = SOURCE_TO_QUALITIES if ctype == "source" else MODIFIER_TO_QUALITIES
        quals: list[str] = []
        for v in values:
            value = v.get(key)
            if not value:
                continue
            qs = mapping.get(value)
            if qs is None:
                raise CFError(f"unmapped {key} value '{value}'")
            quals.extend(q for q in qs if q not in quals)
        if not quals:
            raise CFError(f"{ctype} condition has no values")
        args = ", ".join(json.dumps(q) for q in quals)
        return [{"required": required, "impossible": False, "negate": negate,
                 "sel": f"quality(BASE, {args})"}]

    if ctype == "language":
        atoms: list[dict] = []
        for v in values:
            lang = v.get("language")
            except_lang = v.get("except", False)
            # matches == (language present)  <=>  except == negate ('except'
            # rows and negated conditions both want the language ABSENT).
            want_present = except_lang == negate
            # 'Original' resolves per-item to that item's own original
            # language, so it filters exactly like any other language value.
            sel = f"language(BASE, {json.dumps(lang)})"
            atoms.append({"required": required, "impossible": False,
                          "negate": not want_present, "sel": sel})
        if not atoms:
            atoms = [{"required": required, "impossible": False,
                      "negate": False, "sel": "BASE"}]
        return atoms

    raise CFError(f"unsupported condition type '{ctype}'")


def group_expression(atoms: list[dict], base: str, ctype: str = "") -> str:
    """Combine one type group into a single SEL string (raises CFError)."""
    required = [a for a in atoms if a["required"]]
    if required:
        if any(a.get("impossible") for a in required):
            raise CFError("a required condition can never pass on this side")
        # Several required language atoms all demanding the ABSENCE of their
        # value combine via De Morgan: (NOT a AND NOT b) == NOT (a OR b) ==
        # one negated merge, instead of nested negates chained through
        # `current`. Scoped to language so other formats' existing output is
        # preserved.
        if (ctype == "language" and len(required) > 1
                and all(a["negate"] for a in required)):
            inner = ", ".join(render(a["sel"], base) for a in required)
            return f"negate(merge({inner}), {base})"
        current = base
        for a in required:
            current = apply_negate(render(a["sel"], current), a["negate"], current)
        return current

    passing = [a for a in atoms if not a.get("impossible")]
    if not passing:
        raise CFError("no condition in the group can pass")
    exprs = [apply_negate(render(a["sel"], base), a["negate"], base)
             for a in passing]
    if len(exprs) == 1:
        return exprs[0]
    return "merge(" + ", ".join(exprs) + ")"


def build_expression(condition_cf: dict[str, list[dict]], cf: str, side: str,
                     patterns: dict[str, str], regexes: dict[str, str],
                     invalid: set[str], names: set[str]) -> str:
    """Full CF-side SEL predicate over `streams`."""
    conditions = filter_for_side(condition_cf[cf], side)
    if not conditions:
        # a side with no remaining conditions matches every stream
        return "streams"

    # group by type; process type groups in deterministic order
    groups: dict[str, list[dict]] = {}
    for cond in conditions:
        atoms = build_atoms(cond, cf, patterns, regexes, invalid, names)
        groups.setdefault(cond["type"], []).extend(atoms)

    current = "streams"
    for ctype in sorted(groups):
        current = group_expression(groups[ctype], current, ctype)
    return current


# ------------------------------------------------------------------ output

def to_expression_item(guard: str, label: str, name: str, expr: str,
                       score: int) -> dict:
    return {
        "expression": f"/*#{label}*/ /*{name}*/ queryType=='{guard}' ? {expr} : []",
        "score": score,
        "enabled": True,
    }


def write_json(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(items, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


# -------------------------------------------------------------- validation

_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
_QUOTE_RE = re.compile(r"'(?:[^'\\]|\\.)*'")


def sel_balanced(expression: str) -> bool:
    """Strip comments/quoted strings, then verify () and [] balance."""
    expr = _COMMENT_RE.sub("", expression)
    expr = _QUOTE_RE.sub("''", expr)
    stack: list[str] = []
    for ch in expr:
        if ch in "([":
            stack.append(ch)
        elif ch in ")]":
            if not stack or stack.pop() != ("(" if ch == ")" else "["):
                return False
    return not stack


def js_validate_regexes(node: Path | None, regexes: dict[str, str]) -> set[str]:
    """Compile every pattern in a fresh node process; return invalid names."""
    if node is None or not node.exists():
        print("[convert] node not found - skipping JS regex validation", file=sys.stderr)
        return set()
    script = (
        "const data=JSON.parse(process.argv[1]); const bad=[];"
        "for (const [n,p] of Object.entries(data)){"
        "try{new RegExp(p,'i')}catch{ bad.push(n) }}"
        "console.log(JSON.stringify(bad));"
    )
    payload = json.dumps(regexes, ensure_ascii=False)
    try:
        proc = subprocess.run(
            [str(node), "-e", script, payload],
            capture_output=True, text=True, timeout=60,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(f"[convert] regex validation failed: {exc}", file=sys.stderr)
        return set()
    if proc.returncode != 0:
        print(f"[convert] node regex validation error: {proc.stderr.strip()}",
              file=sys.stderr)
        return set()
    try:
        return set(json.loads(proc.stdout.strip().splitlines()[-1]))
    except (json.JSONDecodeError, IndexError):
        return set()


# ------------------------------------------------------------------- main

def convert_profile(db: sqlite3.Connection, profile: str, out_dir: Path,
                    all_conditions: dict[str, list[dict]],
                    patterns: dict[str, str], regexes: dict[str, str],
                    invalid: set[str]) -> dict:
    scores = profile_scores(db, profile)
    slug = slugify(profile)

    items: list[dict] = []
    used_regex_names: set[str] = set()
    stats = {
        "profile": profile,
        "assigned_cfs": len(scores),
        "radarr_items": 0,
        "sonarr_items": 0,
        "skipped": [],
        "regexes": 0,
    }

    for cf in sorted(scores):
        for side, label, guard in (
            ("radarr", "Radarr", "movie"),
            ("sonarr", "Sonarr", "series"),
        ):
            score = effective_score(scores[cf], side)
            if score is None:
                continue  # not assigned for this side
            try:
                expr = build_expression(all_conditions, cf, side,
                                        patterns, regexes, invalid,
                                        used_regex_names)
            except CFError as exc:
                stats["skipped"].append(f"{cf} [{side}]: {exc}")
                continue

            item = to_expression_item(guard, label, cf, expr, score)
            if not sel_balanced(item["expression"]):
                stats["skipped"].append(f"{cf} [{side}]: unbalanced SEL")
                continue

            items.append(item)
            stats[f"{side}_items"] += 1

    write_json(out_dir / f"{slug}.expressions.json", items)

    regex_items = []
    for name in sorted(used_regex_names):
        regex_items.append({
            "name": name,
            "pattern": f"/{regexes[name]}/i",
            "score": 0,
        })
    write_json(out_dir / f"{slug}.regexes.json", regex_items)
    stats["regexes"] = len(regex_items)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=sorted(SOURCE_DBS),
        default="dictionarry",
        help="Profilarr PCD database the snapshot came from (default: dictionarry)."
        " Selects the default --db path, exactly mirroring build_db.py --source.",
    )
    parser.add_argument(
        "--db", type=Path, default=None,
        help="path to the rebuilt SQLite snapshot (default: .deps/<source>.sqlite)",
    )
    parser.add_argument(
        "--out", type=Path, default=OUT_DIR,
        help="output directory (default: profiles/)",
    )
    parser.add_argument(
        "--profile", action="append", metavar="NAME",
        help="convert only the named quality profile(s); may be repeated"
        " (default: all profiles in the snapshot)",
    )
    parser.add_argument(
        "--node",
        default=(Path(shutil.which("node")) if shutil.which("node") else None),
        help="node binary for regex validation (default: from PATH)",
    )
    args = parser.parse_args()

    if args.db is None:
        args.db = SOURCE_DBS[args.source]
    if not args.db.exists():
        sys.exit(f"[convert] snapshot not found: {args.db} (run build_db.py first)")

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    all_conditions = load_conditions(db)
    patterns = load_patterns(db)
    regexes = load_regexes(db)
    invalid = js_validate_regexes(args.node, regexes)

    if invalid:
        print(f"[convert] invalid regexes (referencing CFs degrade): "
              f"{sorted(invalid)}", file=sys.stderr)

    profiles = iter_profiles(db)
    if args.profile:
        wanted = set(args.profile)
        missing = wanted - set(profiles)
        if missing:
            sys.exit(f"[convert] unknown profile(s): {sorted(missing)}\n"
                     f"  available: {sorted(profiles)}")
        profiles = [p for p in profiles if p in wanted]

    total = {"expressions": 0, "regexes": 0, "skipped": 0}
    for profile in profiles:
        stats = convert_profile(
            db, profile, args.out, all_conditions, patterns, regexes, invalid,
        )
        total["expressions"] += stats["radarr_items"] + stats["sonarr_items"]
        total["regexes"] += stats["regexes"]
        total["skipped"] += len(stats["skipped"])
        print(f"[convert] {profile}: {stats['radarr_items']} radarr + "
              f"{stats['sonarr_items']} sonarr expressions, "
              f"{stats['regexes']} regexes, {len(stats['skipped'])} skipped")
        for skip in stats["skipped"]:
            print(f"          - {skip}")

    print(f"[convert] wrote profiles to {args.out}")
    print(f"[convert] totals: {total['expressions']} expressions, "
          f"{total['regexes']} regex entries, {total['skipped']} skipped sides")


if __name__ == "__main__":
    main()
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
its own score. Anime profiles (see is_anime_profile) are guarded by
'anime.movie'/'anime.series' instead, so they only fire for anime-scoped
queries and never cross-score plain movie/series content. Regexes referenced
by a profile are emitted with the 'i' flag (Radarr compiles all specs with
RegexOptions.IgnoreCase).

Verification: expression items are structurally validated (comment/quote/paren
balance) and regexes are JS-compiled with Node when available.

Size: emitted expression items are passed through collapse_expression(), a
deterministic, semantics-preserving pass that collapses OR-of-name merges into
multi-name regexMatched calls, folds chained negate-regexMatched blocks, and
strips the redundant grouping parens the builders add per call argument.
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


def is_anime_profile(profile: str) -> bool:
    """True for anime-scoped quality profiles (Dumpstarr 'Anime 1080p',
    trash-pcd '[Anime] Remux-1080p').

    Anime profiles must branch on queryType=='anime.movie'/'anime.series'
    (the AIOStreams anime query types) instead of plain 'movie'/'series',
    otherwise they also fire for, and cross-score, non-anime content. Kept
    here in convert.py (not patched into the JSON) so every regeneration -
    including the automated daily sync - preserves the scoping.
    """
    return "anime" in profile.lower()


def guards_for_profile(profile: str) -> tuple[str, str]:
    """The queryType guards emitted for radarr/sonarr sides of a profile."""
    if is_anime_profile(profile):
        return "anime.movie", "anime.series"
    return "movie", "series"


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


# ------------------------------------------------------------- SEL collapse

class _SelNode:
    __slots__ = ("kind", "name", "args", "value")

    def __init__(self, kind, name=None, args=None, value=None):
        self.kind = kind
        self.name = name
        self.args = args or []
        self.value = value


def _parse_sel(s: str, i: int) -> tuple[_SelNode, int]:
    """Recursive-descent parse of a nested-call SEL body (no infix ops)."""
    n = len(s)
    while i < n and s[i] in " \t\r\n":
        i += 1
    if i >= n:
        raise ValueError("unexpected end of expression")
    c = s[i]
    if c == "(":
        inner, j = _parse_sel(s, i + 1)
        while j < n and s[j] in " \t\r\n":
            j += 1
        if j < n and s[j] == ")":
            j += 1
        return inner, j
    if c in "\"'":
        quote = c
        j = i + 1
        buf: list[str] = []
        while j < n:
            ch = s[j]
            if ch == "\\":
                buf.append(s[j:j + 2])
                j += 2
                continue
            if ch == quote:
                j += 1
                break
            buf.append(ch)
            j += 1
        return _SelNode("str", value=quote + "".join(buf) + quote), j
    if c == "[":
        j = i
        depth = 0
        while j < n:
            if s[j] == "[":
                depth += 1
            elif s[j] == "]":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        return _SelNode("list"), j
    if c.isalpha() or c == "_":
        j = i
        while j < n and (s[j].isalnum() or s[j] == "_"):
            j += 1
        name = s[i:j]
        k = j
        while k < n and s[k] in " \t\r\n":
            k += 1
        if k < n and s[k] == "(":
            args: list[_SelNode] = []
            k += 1
            while True:
                while k < n and s[k] in " \t\r\n":
                    k += 1
                if s[k] == ")":
                    k += 1
                    break
                arg, k = _parse_sel(s, k)
                args.append(arg)
                while k < n and s[k] in " \t\r\n":
                    k += 1
                if k < n and s[k] == ",":
                    k += 1
                    continue
                if k < n and s[k] == ")":
                    k += 1
                    break
                raise ValueError(f"malformed argument list at offset {k}")
            return _SelNode("call", name=name, args=args), k
        return _SelNode("ident", name=name), j
    raise ValueError(f"unexpected character {c!r} at offset {i}")


def _render_sel(node: _SelNode) -> str:
    if node.kind == "str":
        return node.value
    if node.kind == "ident":
        return node.name
    if node.kind == "list":
        return "[]"
    return f"{node.name}({', '.join(_render_sel(a) for a in node.args)})"


def _plain_str(node: _SelNode) -> str | None:
    """The inner text of a plain double-quoted string, else None."""
    if node.kind != "str" or not (node.value.startswith('"')
                                  and node.value.endswith('"')):
        return None
    inner = node.value[1:-1]
    if '"' in inner:
        return None
    return inner


def _regex_name(node: _SelNode) -> str | None:
    """The name string if node is exactly regexMatched(streams, \"name\")."""
    if node.kind != "call" or node.name != "regexMatched":
        return None
    if len(node.args) != 2:
        return None
    base, val = node.args
    if base.kind != "ident" or base.name != "streams":
        return None
    return _plain_str(val)


def _collapse_negate_chain(node: _SelNode) -> bool:
    """Collapse negate(regexMatched(cur, n_i), cur) chains produced by chained
    required conditions into one negate(regexMatched(base, n_1..n_k), base).

    Runs on the raw tree before child collapse so the twin copies of `cur`
    (regexMatched's first arg vs negate's second arg) still render identically.
    Semantics: negate(match, base) == base AND NOT match, so chaining
    `cur = negate(regexMatched(cur, n_i), cur)` is exactly
    `base AND NOT (n_1 OR ... OR n_k)`.
    """
    cur = node
    names: list[str] = []
    while cur.kind == "call" and cur.name == "negate" and len(cur.args) == 2:
        rm, base = cur.args
        if not (rm.kind == "call" and rm.name == "regexMatched"):
            break
        if len(rm.args) != 2:
            break
        if _render_sel(rm.args[0]) != _render_sel(base):
            break
        name = _plain_str(rm.args[1])
        if name is None:
            break
        names.append(name)
        cur = base
    if len(names) < 2:
        return False
    names = list(reversed(names))
    node.kind = "call"
    node.name = "negate"
    node.args = [
        _SelNode("call", name="regexMatched",
                 args=[cur] + [_SelNode("str", value=f'"{n}"') for n in names]),
        cur,
    ]
    return True


def _collapse_negate_duplicate(node: _SelNode) -> bool:
    """Collapse negate(regexMatched(regexMatched(X, *L1), *L2), regexMatched(X, *L1))
    into negate(regexMatched(X, *L2), regexMatched(X, *L1))."""
    first, second = node.args
    if first.kind != "call" or first.name != "regexMatched":
        return False
    if second.kind != "call" or second.name != "regexMatched":
        return False
    if len(first.args) < 2 or len(second.args) < 2:
        return False
    inner = first.args[0]
    if inner.kind != "call" or inner.name != "regexMatched":
        return False
    if len(inner.args) < 2:
        return False
    L2 = first.args[1:]
    X1 = inner.args[0]
    L1 = inner.args[1:]
    X2 = second.args[0]
    L1b = second.args[1:]
    if _render_sel(X1) != _render_sel(X2):
        return False
    if len(L1) != len(L1b):
        return False
    for a, b in zip(L1, L1b):
        if _render_sel(a) != _render_sel(b):
            return False
    node.args = [
        _SelNode("call", name="regexMatched", args=[X1] + list(L2)),
        _SelNode("call", name="regexMatched", args=[X2] + list(L1)),
    ]
    return True


def _optimize_sel_node(node: _SelNode) -> None:
    if node.kind != "call":
        return
    if node.name == "negate" and len(node.args) == 2 and _collapse_negate_chain(node):
        for a in node.args:
            _optimize_sel_node(a)
        return
    for a in node.args:
        _optimize_sel_node(a)
    if node.name == "negate" and len(node.args) == 2:
        _collapse_negate_duplicate(node)
    if node.name == "merge":
        names = [_regex_name(a) for a in node.args]
        if len(node.args) >= 2 and all(n is not None for n in names):
            node.name = "regexMatched"
            node.args = [_SelNode("ident", name="streams")] + [
                _SelNode("str", value=f'"{n}"') for n in names
            ]


_EXPR_BODY_RE = re.compile(
    r"^(.*queryType=='(anime\.movie|anime\.series|movie|series)' \? )(.*)( : \[\])$",
    re.S)


def collapse_expression(expression: str) -> str:
    """Deterministic SEL size reduction on a generated expression item.

    Two idempotent rewrites, both semantics-preserving:
      - merge(regexMatched(streams, n1), regexMatched(streams, n2), ...)
        -> regexMatched(streams, n1, n2, ...)   (OR of name matches)
      - negate(regexMatched(cur, n_i), cur) chains
        -> negate(regexMatched(base, n_1, ..., n_k), base)
    plus removal of the redundant grouping parens the builders add around
    every call argument. Unknown shapes are returned untouched.
    """
    m = _EXPR_BODY_RE.match(expression)
    if not m:
        return expression
    prefix, body, suffix = m.group(1), m.group(3), m.group(4)
    try:
        node, end = _parse_sel(body, 0)
    except ValueError:
        return expression
    k = end
    while k < len(body) and body[k] in " \t\r\n":
        k += 1
    if k != len(body):
        return expression
    _optimize_sel_node(node)
    return prefix + _render_sel(node) + suffix


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


# --------------------------------------------------------------- precompile

def _find_regex_matched_lists(expr_body: str) -> list[tuple[int, int, tuple[str, ...]]]:
    """Find all regexMatched(streams, "name1", "name2", ...) with 3+ names.
    Returns list of (start, end, name_tuple) in descending start order."""
    results: list[tuple[int, int, tuple[str, ...]]] = []
    i = 0
    while True:
        idx = expr_body.find("regexMatched(", i)
        if idx < 0:
            break
        start = idx
        paren = start + len("regexMatched")
        depth = 0
        j = paren
        while j < len(expr_body):
            if expr_body[j] == '(':
                depth += 1
            elif expr_body[j] == ')':
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        inner = expr_body[paren+1:j-1]
        args: list[str] = []
        arg_depth = 0
        arg_start = 0
        for k, ch in enumerate(inner):
            if ch == ',' and arg_depth == 0:
                args.append(inner[arg_start:k].strip())
                arg_start = k + 1
            elif ch == '(':
                arg_depth += 1
            elif ch == ')':
                arg_depth -= 1
        args.append(inner[arg_start:].strip())
        if len(args) >= 2 and args[0].strip() == "streams":
            names = tuple(a.strip('" ') for a in args[1:] if a.strip().startswith('"') and a.strip().endswith('"'))
            if len(names) >= 3:
                results.append((start, j, names))
        i = j
    results.reverse()
    return results


def _patterns_share_shape(patterns: list[str]) -> str | None:
    """If all patterns share the same shape prefix+GROUP+suffix, return the
    combined pattern with an OR group. Otherwise return None."""
    if not patterns:
        return None
    template = patterns[0]
    for p in patterns:
        if len(p) != len(template):
            return None
        mismatch = [i for i in range(len(p)) if p[i] != template[i] and not (p[i].isalnum() or template[i].isalnum())]
        if mismatch:
            return None

    all_names: list[str] = []
    for p in patterns:
        name_part = ""
        for i, ch in enumerate(p):
            if ch != template[i]:
                name_part += ch
        if name_part:
            all_names.append(name_part)

    if len(all_names) == len(patterns):
        prefix, suffix = "", ""
        for i in range(len(template)):
            if any(p[i] != template[i] for p in patterns):
                prefix = template[:i]
                suffix = template[i + len(all_names[0]):] if len(all_names[0]) > 0 else template[i+1:]
                break
        if prefix or suffix:
            combined = f"(?:{prefix}(?:{'|'.join(all_names)}){suffix})"
            return combined

    return None


def _combine_patterns(names: tuple[str, ...], full_patterns: dict[str, str]) -> str | None:
    """Combine multiple regex patterns into one OR pattern.
    Returns the combined pattern body (without /i wrapper)."""
    patterns = [full_patterns[n] for n in names if n in full_patterns]
    if len(patterns) != len(names):
        return None

    combined = _patterns_share_shape(patterns)
    if combined:
        return combined

    return "(?:" + "|".join(patterns) + ")"


def _slug_for_names(names: tuple[str, ...], slug: str) -> str:
    """Generate a readable name for a consolidated regex pattern."""
    first = names[0][:20]
    last = names[-1][:20]
    if first == last:
        return f"Precompiled-{first}"
    return f"Precompiled-{first}-to-{last}"


def _hash_names(names: tuple[str, ...]) -> str:
    """Deterministic short hash for a tuple of names."""
    import hashlib
    return hashlib.md5("|".join(names).encode()).hexdigest()[:8]


def _precompile_repeated_groups(items: list[dict], regexes: dict[str, str],
                                 used_regex_names: set[str], slug: str) -> None:
    """Find all regexMatched(streams, "name1", "name2", ...) with 3+ names
    that appear multiple times within an expression and pre-compile them
    into a single named regex pattern. Modifies items and used_regex_names in place."""
    import hashlib

    for item in items:
        expr = item["expression"]
        m = re.search(r"\?(.*):\s*\[\]", expr)
        if not m:
            continue
        body = m.group(1).strip()
        prefix = expr[:m.start(1)]
        suffix = expr[m.end(1):]

        calls = _find_regex_matched_lists(body)
        if not calls:
            continue

        by_names: dict[tuple[str, ...], list[tuple[int, int]]] = {}
        for start, end, names in calls:
            by_names.setdefault(names, []).append((start, end))

        replacements: list[tuple[int, int, str, str]] = []
        for names, positions in by_names.items():
            if len(positions) < 2:
                continue
            combined_pattern = _combine_patterns(names, regexes)
            if combined_pattern is None:
                continue

            combined_name = f"Precompiled-{_hash_names(names)}"
            combined_call = f"regexMatched(streams, {json.dumps(combined_name)})"

            for start, end in positions:
                old_text = body[start:end]
                replacements.append((start, end, old_text, combined_call))

            used_regex_names.add(combined_name)
            regexes[combined_name] = combined_pattern

        if replacements:
            new_body = body
            for start, end, old_text, new_text in sorted(replacements, reverse=True):
                new_body = new_body[:start] + new_text + new_body[end:]
            item["expression"] = prefix + new_body + suffix


# ------------------------------------------------------------------- main

def convert_profile(db: sqlite3.Connection, profile: str, out_dir: Path,
                    all_conditions: dict[str, list[dict]],
                    patterns: dict[str, str], regexes: dict[str, str],
                    invalid: set[str]) -> dict:
    scores = profile_scores(db, profile)
    slug = slugify(profile)
    guard_movie, guard_series = guards_for_profile(profile)

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
            ("radarr", "Radarr", guard_movie),
            ("sonarr", "Sonarr", guard_series),
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
            item["expression"] = collapse_expression(item["expression"])
            if not sel_balanced(item["expression"]):
                stats["skipped"].append(f"{cf} [{side}]: unbalanced SEL")
                continue

            items.append(item)
            stats[f"{side}_items"] += 1

    _precompile_repeated_groups(items, regexes, used_regex_names, slug)

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
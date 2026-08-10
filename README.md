# AIO-Quality-Profiles

Dictionarry quality profiles converted into AIOStreams **Synced** format.

The official [Dictionarry-Hub](https://github.com/Dictionarry-Hub) quality profiles
(`1080p Compact`, `2160p Efficient`, …) are translated into AIOStreams
"ranked" files so a Stremio/AIOStreams setup can taste TV/movie results the same
way Radarr/Sonarr do when scoring releases against those profiles.

## Files

```
build_db.py   # rebuild the Dictionarry relational snapshot into SQLite
convert.py    # snapshot -> profiles/<slug>.{expressions,regexes}.json
profiles/     # generated AIOStreams Synced files, one pair per quality profile
```

For each quality profile two files are emitted:

| File | AIOStreams Synced section |
| --- | --- |
| `profiles/<slug>.expressions.json` | ranked stream expressions (`userLimits.sel.urls`) |
| `profiles/<slug>.regexes.json` | ranked regex patterns (`userLimits.regex.patternsUrls`) |

`expressions.json` items carry `queryType` guards, so a single profile produces
one movie (Radarr) and one series (Sonarr) item per custom format, with the
per-side score the arr app would give it.

## Quick start (source of truth on GitHub)

1. Install AIOStreams (self-hosted or managed).
2. In AIOStreams, add the Synced URLs for the profile you want, e.g.:
   - `…/profiles/2160p-efficient.expressions.json`
   - `…/profiles/2160p-efficient.regexes.json`
   - *(use the raw GitHub URL of the file in this repo)*
3. Apply the ranked scores in AIOStreams sorting (the expressions carry your
   app's custom-format scores).

## Regenerating

```bash
python3 build_db.py            # clones schema+database deps, builds .deps/dictionarry.sqlite
python3 convert.py             # writes profiles/*.json
```

`convert.py --node <path>` JS-compiles every emitted regex; invalid regexes are
dropped and the custom formats that reference them degrade to "no match".

## How the conversion works

### Condition semantics (mirrors Profilarr / Radarr / Sonarr)

- Conditions are filtered per arr side: `'all'` or the matching side;
  `quality_modifier` conditions are dropped for sonarr, `release_type` for radarr.
- Conditions are grouped **by type**; different types are AND-ed.
- Within a type group:
  - if **any** condition is required → **all required** conditions must pass
    and the optional ones in that group are **ignored**;
  - if **none** is required → **at least one** must pass (OR, via `merge`).
- A condition's `negate` flag inverts its own match (`negate(...)`).

### Type mapping

| Dictionarry type | AIOStreams SEL |
| --- | --- |
| `resolution` | `resolution(streams, '2160p', …)` |
| `source` | `quality(streams, 'BluRay', 'BluRay REMUX', …)` |
| `quality_modifier` | `quality(streams, …)` |
| `release_type` | `seasonPack(streams, 'seasonPack')` |
| `language` | `language(streams, …)` / `negate(language(...), streams)`; `'Original'` resolves per-item to the release's own original language |
| `release_title`, `release_group`, `edition` | `regexMatched(streams, 'Regex Name')` |
| `year`, `size`, `indexer_flag` | **skipped** (unsupported / unused in these profiles) |

Source values cover multiple AIOStreams qualities:

| source | qualities |
| --- | --- |
| `television` | `HDTV` |
| `web_dl` | `WEB-DL` |
| `webrip` | `WEBRip` |
| `dvd` | `DVDRip`, `DVD REMUX` |
| `bluray` | `BluRay`, `BluRay REMUX` |
| `bluray_raw` | `BluRay` |

| modifier | qualities |
| --- | --- |
| `remux` | `BluRay REMUX`, `DVD REMUX` |
| `brdisk` | `BluRay` (approximation — AIOStreams has no BR-DISK quality) |

### Scoring

Each profile/CF row carries a score per arr type. Per-side score resolution:
side-specific score if present, otherwise the `'all'` score. Because one ranked
expression item has a single `score`, each custom format is split into up to two
items — `queryType=='movie'` with the Radarr score and `queryType=='series'`
with the Sonarr score.

### Regexes

Radarr compiles every regex specification with `RegexOptions.IgnoreCase`, so
patterns are emitted with the `i` flag (`/pattern/i`). Inline `(?i)` toggles are
no-ops under that flag and are stripped (JS `RegExp` rejects them). One regex
name maps to one `regexMatched(...)` reference.

## Known fidelity limits

- AIOStreams ranked regexes match against **filename and folder name only**
  (`precomputer.ts`), so Radarr's per-field regex matching (title vs edition vs
  release group) cannot be reproduced exactly — a regex matches wherever the
  token appears in the file name.
- AIOStreams' `language()` filter accepts `'Original'`, which resolves
  dynamically **per item** to that item's original language: during filtering a
  stream whose audio language matches the media's original language is tagged
  `Original` (see AIOStreams changelog v2.22.0, *"add 'Original' option in
  language filters"*), and the synthetic tag is removed from the final output.
  A Dictionarry language condition on `Original` therefore maps like any other
  language value: `language(base, 'Original')` when it must be present, or
  `negate(language(base, 'Original'), base)` when it must be absent. In
  particular `Not Original or English` now correctly expresses *neither
  Original nor English* as
  `negate(merge(language(streams, 'Original'), language(streams, 'English')), streams)`.
- `year` and `size` conditions are unsupported (the Dictionarry snapshot has no
  `condition_years`/`condition_sizes` rows; size has no AIOStreams equivalent in
  this SEL shape) and `indexer_flag` has no AIOStreams equivalent — none of the
  indexer-flag custom formats are assigned to these profiles anyway.
- Scores from rankings are **additive** on top of the normal streaming pipeline;
  the expressions also select the streams they rank.

## CI

`.github/workflows/sync.yml` re-runs `build_db.py` + `convert.py` on a schedule
and commits any changed profile files, keeping this repo synced with upstream
Dictionarry data.
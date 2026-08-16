# tools/verify

Verification harness that runs the **real AIOStreams stream-expression
evaluator** against this repo's generated `.expressions.json` profiles —
instead of a reimplementation.

## Why this exists

`profiles/*.expressions.json` are the "ranked stream expressions" (SEL) that
AIOStreams evaluates against candidate streams. On 2026-08-11 an automated
sync (`.github/workflows/sync.yml`, commit `e373b00`) silently reverted the
anime profiles' guards from `queryType=='anime.movie'` / `'anime.series'`
back to plain `'movie'` / `'series'`, because `convert.py` had no branching
for anime profiles — the earlier fix (commit `c1c479a`) had only been
hand-patched into the JSON, not into the generator. Under an anime query
(`queryType='anime.movie'`), the plain `'movie'` guard never fires, so every
anime stream got a SEL score of 0.

This harness proves the fix with the actual engine: it evaluates each profile
expression with a `StreamSelector` whose `queryType` matches the guard, and
asserts a realistic Tier-1 BluRay REMUX fixture scores non-zero. It also
asserts the regression case: plain `'movie'`/`'series'` guards under an anime
query select nothing.

## What is vendored (and what is not)

`vendor/` contains the real AIOStreams source, vendored from upstream commit
**`6b9ee1c8eaf9fb200c69d083315a58bf4ea54018`** (2026-08-12), copied with a
provenance header in each file:

| File | Upstream source | Notes |
|------|-----------------|-------|
| `vendor/streamExpression.ts` | `packages/core/src/parser/streamExpression.ts` | The actual evaluator (`StreamSelector`, `ExitConditionEvaluator`, `GroupConditionEvaluator`, all SEL functions). Copied verbatim; only import paths rewritten to local modules. |
| `vendor/schemas.ts` | `packages/core/src/db/schemas.ts` | `ParsedStreamSchema` closure, copied verbatim. The original's `config`-dependent max-length refinements are not in this closure, so `config` is not needed. |
| `vendor/constants.ts` | `packages/core/src/utils/constants.ts` | Constant arrays required by `schemas.ts`, copied verbatim. |
| `vendor/format-zod-error.ts` | `packages/core/src/utils/format-zod-error.ts` | Error formatting, copied verbatim. |
| `vendor/parser-utils.ts` | `packages/core/src/parser/utils.ts` | `parseBitrate`, copied verbatim. |
| `vendor/regex.ts` | `packages/core/src/utils/regex.ts` | `formRegexFromKeywordsSync` + helpers, copied verbatim. |
| `vendor/context.ts` | `packages/core/src/streams/context.ts` | `ExpressionContext` interface only, copied verbatim. |
| `vendor/logger.ts` | — | **Stub, not vendored.** The real logger is pino-based with a large transitive dependency graph and does not affect evaluation semantics. No-op implementation. |

npm dependencies (`expr-eval`, `bytes`, `zod@4`, `@types/bytes`) are declared
in `package.json`. `zod@4` matches upstream (`"zod": "^4.4.3"`).

To update the vendored evaluator later: re-copy the upstream files, remap the
import paths in `streamExpression.ts` to the sibling local modules, and keep
the schema/constants closures in sync with what `ParsedStreamSchema` needs.

## Usage

```sh
cd tools/verify
npm install
npm run verify
```

`verify.mjs`:

- builds a fixture stream whose `rankedRegexesMatched` comes from running the
  profile's **own** `.regexes.json` patterns against a realistic BluRay REMUX
  anime filename (so `regexMatched()` is genuinely profile-derived),
- for each `queryType` guard present in the profile, runs a real
  `StreamSelector` over every enabled expression and accumulates `score`,
  mirroring `precomputeRankedStreamExpressions()` in upstream
  `packages/core/src/streams/precomputer.ts`,
- asserts a non-zero total score per profile,
- runs the guard regression check (plain `'movie'`/`'series'` guards under an
  anime query must select nothing; `'anime.movie'`/`'anime.series'` guards
  must select the fixture).

Exit code 0 = all profiles pass; 1 = any profile fails.

You can verify a specific profile by passing its path, e.g.:

```sh
node verify.mjs ../../profiles/anime-remux-1080p.expressions.json
```

## Files in this directory

- `verify.mjs` — the harness (reads `profiles/` relative to this directory)
- `vendor/` — vendored AIOStreams evaluator source (see table above)
- `package.json` / `tsconfig.json` — deps + build (compiles `vendor/*.ts` → `dist/`)
- `dist/` — build output (gitignored)
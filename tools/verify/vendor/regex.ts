/**
 * VENDORED FROM AIOStreams (upstream commit 6b9ee1c8eaf9fb200c69d083315a58bf4ea54018,
 * 2026-08-12, packages/core/src/utils/regex.ts).
 *
 * Only `parseRegex`, `buildKeywordRegexPattern`, and
 * `formRegexFromKeywordsSync` are included, copied verbatim. These are the
 * functions used by the vendored evaluator's `keyword()` SEL function. The
 * original file's async cache-backed helpers (`compileRegex`,
 * `formRegexFromKeywords`) and their imports (Cache, crypto) are not needed.
 */

// parses regex and flags, also checks for existence of a custom flag - n - for negate
export function parseRegex(pattern: string): {
  regex: string;
  flags: string;
} {
  const regexFormatMatch = /^\/(.+)\/([gimuyn]*)$/.exec(pattern);
  return regexFormatMatch
    ? { regex: regexFormatMatch[1], flags: regexFormatMatch[2] }
    : { regex: pattern, flags: '' };
}

// Build the raw pattern string used to match a list of keywords against stream
// attributes. Exposed separately so synchronous callers (e.g. the SEL parser,
// which cannot await) can produce the exact same regex shape as the async
// `formRegexFromKeywords` helper used by the keyword UI filters.
export function buildKeywordRegexPattern(keywords: string[]): string {
  return `/(?:^|(?<![^ \\[(_\\-.]))(${keywords
    .map((filter) => filter.replace(/[-[\]{}()*+?.,\\^$]/g, '\\$&'))
    .map((filter) => filter.replace(/\s/g, '[\\s.\\-_]?'))
    .join('|')})(?=[ \\)\\]_.-]|$)/i`;
}

// Synchronous variant of `formRegexFromKeywords`. Produces an identical regex
// to the async version (same pattern + flags) but bypasses the async regex
// cache so it can be called from synchronous contexts such as SEL function
// implementations.
export function formRegexFromKeywordsSync(keywords: string[]): RegExp {
  const { regex, flags } = parseRegex(buildKeywordRegexPattern(keywords));
  const cleanedFlags = flags.includes('n') ? flags.replace('n', '') : flags;
  return new RegExp(regex, cleanedFlags || undefined);
}
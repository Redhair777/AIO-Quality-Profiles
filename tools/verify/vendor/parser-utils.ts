/**
 * VENDORED FROM AIOStreams (upstream commit 6b9ee1c8eaf9fb200c69d083315a58bf4ea54018,
 * 2026-08-12, packages/core/src/parser/utils.ts).
 *
 * Only the `parseBitrate` function is included, copied verbatim. The original
 * file's other imports (fuzzball, logger, metadata utils) are not needed by
 * the vendored evaluator.
 */

export function parseBitrate(bitrateString: string): number | undefined {
  const match = bitrateString.match(
    /^(\d+(\.\d+)?)\s*(bps|kbps|mbps|gbps|tbps)$/i
  );
  if (!match) {
    const trimmed = bitrateString.trim();
    if (!/^\d+(\.\d+)?$/.test(trimmed)) {
      return undefined;
    }
    return parseFloat(trimmed);
  }
  const num = parseFloat(match[1]);
  const unit = match[3].toLowerCase();
  switch (unit) {
    case 'bps':
      return num;
    case 'kbps':
      return num * 1000;
    case 'mbps':
      return num * 1000000;
    case 'gbps':
      return num * 1000000000;
    case 'tbps':
      return num * 1000000000000;
    default:
      return undefined;
  }
}
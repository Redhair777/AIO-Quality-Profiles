/**
 * VENDORED FROM AIOStreams (upstream commit 6b9ee1c8eaf9fb200c69d083315a58bf4ea54018,
 * 2026-08-12, packages/core/src/streams/context.ts).
 *
 * Only the `ExpressionContext` interface is included (copied verbatim). The
 * original file also defines `StreamContext` (a full runtime class with
 * heavy dependencies); that is not needed by the vendored evaluator because
 * the evaluator only ever *receives* an `ExpressionContext`-shaped object.
 */

export interface ExtendedMetadata {
  absoluteEpisode?: number;
  relativeAbsoluteEpisode?: number; // Episode number within current AniDB entry (for split entries)
  seasonYear?: number; // For anime, the year of the season (e.g., 2021 for "Winter 2021")
}

export interface ExpressionContext {
  type?: string;
  id?: string;
  isAnime?: boolean;
  queryType?: string;
  season?: number;
  episode?: number;
  // Metadata fields
  title?: string;
  titles?: string[];
  year?: number;
  yearEnd?: number;
  genres?: string[];
  runtime?: number;
  absoluteEpisode?: number;
  relativeAbsoluteEpisode?: number; // Episode number within current AniDB entry (for split entries)
  originalLanguage?: string;
  daysSinceRelease?: number; // age in days of the movie / **episode**
  hasNextEpisode?: boolean;
  daysUntilNextEpisode?: number;
  daysSinceFirstAired?: number;
  daysSinceLastAired?: number;
  latestSeason?: number;
  // Anime entry data
  anilistId?: number;
  malId?: number;
  // SeaDex availability
  hasSeaDex?: boolean;
}
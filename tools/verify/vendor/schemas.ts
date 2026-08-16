/**
 * VENDORED FROM AIOStreams (upstream commit 6b9ee1c8eaf9fb200c69d083315a58bf4ea54018,
 * 2026-08-12, packages/core/src/db/schemas.ts).
 *
 * Only the zod schema definitions transitively required by `ParsedStreamSchema`
 * (used by the vendored `streamExpression.ts` evaluator) are included, copied
 * verbatim from the original. The original file imports `config` solely for
 * max-length refinements (`streamExpression()`, `formatterTemplate()`) that are
 * NOT part of the ParsedStreamSchema closure, so that dependency is absent here.
 */

import { z } from 'zod';
import * as constants from './constants.js';

const ServiceIds = z.enum(constants.SERVICES);

const Resolutions = z.enum(constants.RESOLUTIONS);

const Qualities = z.enum(constants.QUALITIES);

const VisualTags = z.enum(constants.VISUAL_TAGS);

const AudioTags = z.enum(constants.AUDIO_TAGS);

const AudioChannels = z.enum(constants.AUDIO_CHANNELS);

const Encodes = z.enum(constants.ENCODES);

const PassthroughStages = z.enum(constants.PASSTHROUGH_STAGES);

// Passthrough can be:
// - true: bypass all stages (backward compatible)
// - array of stages: bypass only specified stages
const PassthroughSchema = z.union([
  z.literal(true),
  z.array(PassthroughStages).min(1),
]);

export type PassthroughValue = z.infer<typeof PassthroughSchema>;
export type PassthroughStage = z.infer<typeof PassthroughStages>;

const SortCriterion = z.object({
  key: z.enum(constants.SORT_CRITERIA),
  direction: z.enum(constants.SORT_DIRECTIONS),
});

export type SortCriterion = z.infer<typeof SortCriterion>;

const StreamTypes = z.enum(constants.STREAM_TYPES);

const ResourceSchema = z.enum(constants.RESOURCES);

export type Resource = z.infer<typeof ResourceSchema>;

const ResourceList = z.array(ResourceSchema);

const AddonSchema = z.object({
  instanceId: z.string().min(1).optional(), // uniquely identifies the addon in a given list of addons
  preset: z.object({
    id: z.string(),
    type: z.string(),
    options: z.record(z.string(), z.any()),
  }),
  manifestUrl: z.string().url(),
  enabled: z.boolean(),
  resources: ResourceList.optional(),
  mediaTypes: z.array(z.enum(constants.TYPES)).optional(),
  name: z.string(),
  identifier: z.string().optional(), // true identifier for generating IDs
  displayIdentifier: z.string().optional(), // identifier for display purposes
  timeout: z.number().min(1),
  library: z.boolean().optional(),
  formatPassthrough: z.boolean().optional(),
  resultPassthrough: z.boolean().optional(),
  pinPosition: z.enum(['top', 'bottom']).optional(),
  serviceWrapped: z.boolean().optional(),
  headers: z.record(z.string().min(1), z.string().min(1)).optional(),
  ip: z.string().optional(),
});

export const SubtitleSchema = z
  .object({
    id: z.string().min(1),
    url: z.string(),
    lang: z.string().min(1),
  })
  .passthrough();

export type Subtitle = z.infer<typeof SubtitleSchema>;

export const SourceSchema = z.object({
  url: z.string(),
  bytes: z.number().nullable().optional(),
});

export const ReleaseKeySchema = z
  .string()
  .regex(/^wd1:[0-9a-f]{32}$/)
  .optional()
  .catch(undefined);

export const ParsedFileSchema = z.object({
  releaseGroup: z.string().optional(),
  resolution: z.string().optional(),
  quality: z.string().optional(),
  encode: z.string().optional(),
  audioChannels: z.array(z.string()),
  visualTags: z.array(z.string()),
  audioTags: z.array(z.string()),
  languages: z.array(z.string()),
  subtitles: z.array(z.string()).optional(),
  subbed: z.boolean().optional(),
  dubbed: z.boolean().optional(),
  title: z.string().optional(),
  year: z.coerce.string().optional(),
  country: z.string().optional(),
  episodeTitle: z.string().optional(),
  seasons: z.array(z.number()).optional(),
  volumes: z.array(z.number()).optional(),
  folderSeasons: z.array(z.number()).optional(),
  folderEpisodes: z.array(z.number()).optional(),
  date: z.string().optional(),
  episodes: z.array(z.number()).optional(),
  editions: z.array(z.string()).optional(),
  regraded: z.boolean().optional(),
  proper: z.boolean().optional(),
  repack: z.boolean().optional(),
  uncensored: z.boolean().optional(),
  unrated: z.boolean().optional(),
  upscaled: z.boolean().optional(),
  network: z.string().optional(),
  container: z.string().optional(),
  extension: z.string().optional(),
  seasonPack: z.boolean().optional(),
  hasChapters: z.boolean().optional(),
});

export const ParsedStreamSchema = z.object({
  id: z.string().min(1),
  proxied: z.boolean().optional(),
  addon: AddonSchema,
  parsedFile: ParsedFileSchema.optional(),
  message: z.string().max(1000).optional(),
  regexMatched: z
    .object({
      name: z.string().optional(),
      pattern: z.string().min(1).optional(),
      index: z.number(),
    })
    .optional(),
  rankedRegexesMatched: z.array(z.string()).optional(),
  regexScore: z.number().optional(),
  keywordMatched: z.boolean().optional(),
  streamExpressionMatched: z
    .object({
      name: z.string().optional(),
      index: z.number(),
    })
    .optional(),

  rankedStreamExpressionsMatched: z
    .array(z.string().min(1).optional())
    .optional(),
  streamExpressionScore: z.number().optional(),
  size: z.number().optional(),
  folderSize: z.number().optional(),
  type: StreamTypes,
  indexer: z.string().optional(),
  /**Age in hours since upload */
  age: z.number().optional(),
  torrent: z
    .object({
      infoHash: z.string().min(1).optional(),
      fileIdx: z.number().optional(),
      seeders: z.number().optional(),
      sources: z.array(z.string().min(1)).optional(),
      private: z.boolean().optional(),
      freeleech: z.boolean().optional(),
    })
    .optional(),
  countryWhitelist: z.array(z.string().length(3)).optional(),
  notWebReady: z.boolean().optional(),
  bingeGroup: z.string().min(1).optional(),
  requestHeaders: z.record(z.string().min(1), z.string().min(1)).optional(),
  responseHeaders: z.record(z.string().min(1), z.string().min(1)).optional(),
  videoHash: z.string().min(1).optional(),
  subtitles: z.array(SubtitleSchema).optional(),
  filename: z.string().optional(),
  folderName: z.string().optional(),
  service: z
    .object({
      id: z.enum(constants.SERVICES),
      cached: z.boolean(),
    })
    .optional(),
  /**Duration in milliseconds */
  duration: z.number().optional(),
  /**Bitrate in bps */
  bitrate: z.number().optional(),
  library: z.boolean().optional(),
  /** Upstream matched this release against an ID-indexed source, not a text search. */
  idMatched: z.boolean().optional(),
  seadex: z
    .object({
      isBest: z.boolean(),
      isSeadex: z.boolean(),
      method: z.enum(['hash', 'group']).optional(),
    })
    .optional(),
  passthrough: PassthroughSchema.optional(),
  url: z.string().optional(),
  nzbUrl: z.string().optional(),
  releaseKey: ReleaseKeySchema,
  failoverVariants: z
    .array(
      z.object({
        url: z.string(),
        type: z.enum(['usenet', 'debrid']),
        serviceId: z.string().optional(),
        filename: z.string().optional(),
        identity: z.string().optional(), // nzbUrl | infoHash | external host+path
        kind: z.enum(['owned', 'external']).optional(), // default 'owned'
        proxied: z.boolean().optional(), // computed at merge time
      })
    )
    .optional(),
  servers: z.array(z.string().min(1)).optional(),
  rarUrls: z.array(SourceSchema).nullable().optional(),
  zipUrls: z.array(SourceSchema).nullable().optional(),
  '7zipUrls': z.array(SourceSchema).nullable().optional(),
  tgzUrls: z.array(SourceSchema).nullable().optional(),
  tarUrls: z.array(SourceSchema).nullable().optional(),
  ytId: z.string().min(1).optional(),
  externalUrl: z.string().min(1).optional(),
  /** Whether the stream has been selected for preloading, should be set to true if the stream is selected */
  preloading: z.boolean().optional(),
  error: z
    .object({
      title: z.string().min(1),
      description: z.string().min(1),
    })
    .optional(),
  originalName: z.string().optional(),
  originalDescription: z.string().optional(),
  extra: z.record(z.string(), z.any()).optional(),
  otherBehaviorHints: z.record(z.string(), z.unknown()).optional(),
});

export type ParsedFile = z.infer<typeof ParsedFileSchema>;

export const ParsedStreams = z.array(ParsedStreamSchema);

export type ParsedStream = z.infer<typeof ParsedStreamSchema>;
export type ParsedStreams = z.infer<typeof ParsedStreams>;
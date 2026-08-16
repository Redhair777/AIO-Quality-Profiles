/**
 * VENDORED FROM AIOStreams (upstream commit 6b9ee1c8eaf9fb200c69d083315a58bf4ea54018,
 * 2026-08-12, packages/core/src/utils/constants.ts).
 *
 * Only the constant arrays transitively required by the vendored
 * `schemas.ts` (ParsedStreamSchema closure) are included, copied verbatim.
 * Everything else from the original file is intentionally omitted.
 */

const REALDEBRID_SERVICE = 'realdebrid';
const DEBRIDLINK_SERVICE = 'debridlink';
const PREMIUMIZE_SERVICE = 'premiumize';
const ALLDEBRID_SERVICE = 'alldebrid';
const TORBOX_SERVICE = 'torbox';
const EASYDEBRID_SERVICE = 'easydebrid';
const DEBRIDER_SERVICE = 'debrider';
const PUTIO_SERVICE = 'putio';
const PIKPAK_SERVICE = 'pikpak';
const OFFCLOUD_SERVICE = 'offcloud';
const SEEDR_SERVICE = 'seedr';
const EASYNEWS_SERVICE = 'easynews';
const NZBDAV_SERVICE = 'nzbdav';
const ALTMOUNT_SERVICE = 'altmount';
const STREMIO_NNTP_SERVICE = 'stremio_nntp';
const STREMTHRU_NEWZ_SERVICE = 'stremthru_newz';
const AIOSTREAMS_SERVICE = 'aiostreams';
const TORRIN_SERVICE = 'torrin';

const SERVICES = [
  REALDEBRID_SERVICE,
  DEBRIDLINK_SERVICE,
  PREMIUMIZE_SERVICE,
  ALLDEBRID_SERVICE,
  TORBOX_SERVICE,
  EASYDEBRID_SERVICE,
  DEBRIDER_SERVICE,
  PUTIO_SERVICE,
  PIKPAK_SERVICE,
  OFFCLOUD_SERVICE,
  SEEDR_SERVICE,
  EASYNEWS_SERVICE,
  NZBDAV_SERVICE,
  ALTMOUNT_SERVICE,
  STREMIO_NNTP_SERVICE,
  STREMTHRU_NEWZ_SERVICE,
  AIOSTREAMS_SERVICE,
  TORRIN_SERVICE,
] as const;

const RESOLUTIONS = [
  '2160p',
  '1440p',
  '1080p',
  '720p',
  '576p',
  '480p',
  '360p',
  '240p',
  '144p',
  'Unknown',
] as const;

const QUALITIES = [
  'BluRay REMUX',
  'BluRay',
  'WEB-DL',
  'WEBRip',
  'HDRip',
  'HC HD-Rip',
  'DVD REMUX',
  'DVDRip',
  'HDTV',
  'CAM',
  'TS',
  'TC',
  'SCR',
  'Unknown',
] as const;

export const FAKE_VISUAL_TAGS = ['HDR+DV', 'DV Only', 'HDR Only'] as const;

const VISUAL_TAGS = [
  ...FAKE_VISUAL_TAGS,
  'HDR10+',
  'HDR10',
  'DV',
  'HDR',
  'HLG',
  '10bit',
  '3D',
  'IMAX',
  'AI',
  'Upscaled',
  'SDR',
  'H-OU',
  'H-SBS',
  'Unknown',
] as const;

const AUDIO_TAGS = [
  'Atmos',
  'DD+',
  'DD',
  'DTS:X',
  'DTS-HD MA',
  'DTS-HD',
  'DTS-ES',
  'DTS',
  'TrueHD',
  'OPUS',
  'FLAC',
  'AAC',
  'Unknown',
] as const;

const AUDIO_CHANNELS = ['2.0', '5.1', '6.1', '7.1', 'Unknown'] as const;

const PASSTHROUGH_STAGES = [
  'filter',
  'language',
  'subtitle',
  'dedup',
  'limit',
  'excluded',
  'required',
  'title',
  'year',
  'episode',
  'digitalRelease',
] as const;

const ENCODES = [
  'AV1',
  'HEVC',
  'AVC',
  'VC-1',
  'XviD',
  'DivX',
  'Unknown',
] as const;

const SORT_CRITERIA = [
  'quality',
  'resolution',
  'language',
  'subtitle',
  'visualTag',
  'audioTag',
  'audioChannel',
  'streamType',
  'encode',
  'size',
  'service',
  'seeders',
  'private',
  'age',
  'addon',
  'regexPatterns',
  'cached',
  'library',
  'keyword',
  'streamExpressionMatched',
  'streamExpressionScore',
  'regexScore',
  'seadex',
  'bitrate',
  'releaseGroup',
] as const;

const SORT_DIRECTIONS = ['asc', 'desc'] as const;

export const P2P_STREAM_TYPE = 'p2p' as const;
export const LIVE_STREAM_TYPE = 'live' as const;
export const STREMIO_USENET_STREAM_TYPE = 'stremio-usenet' as const;
export const ARCHIVE_STREAM_TYPE = 'archive' as const;
export const USENET_STREAM_TYPE = 'usenet' as const;
export const DEBRID_STREAM_TYPE = 'debrid' as const;
export const HTTP_STREAM_TYPE = 'http' as const;
export const INFO_STREAM_TYPE = 'info' as const;
export const EXTERNAL_STREAM_TYPE = 'external' as const;
export const YOUTUBE_STREAM_TYPE = 'youtube' as const;
export const ERROR_STREAM_TYPE = 'error' as const;
export const STATISTIC_STREAM_TYPE = 'statistic' as const;

const STREAM_TYPES = [
  P2P_STREAM_TYPE,
  LIVE_STREAM_TYPE,
  STREMIO_USENET_STREAM_TYPE,
  ARCHIVE_STREAM_TYPE,
  USENET_STREAM_TYPE,
  DEBRID_STREAM_TYPE,
  HTTP_STREAM_TYPE,
  EXTERNAL_STREAM_TYPE,
  YOUTUBE_STREAM_TYPE,
  ERROR_STREAM_TYPE,
  STATISTIC_STREAM_TYPE,
  INFO_STREAM_TYPE,
] as const;

const STREAM_RESOURCE = 'stream' as const;
const SUBTITLES_RESOURCE = 'subtitles' as const;
const CATALOG_RESOURCE = 'catalog' as const;
const META_RESOURCE = 'meta' as const;
const ADDON_CATALOG_RESOURCE = 'addon_catalog' as const;

const RESOURCES = [
  STREAM_RESOURCE,
  SUBTITLES_RESOURCE,
  CATALOG_RESOURCE,
  META_RESOURCE,
  ADDON_CATALOG_RESOURCE,
] as const;

export const MOVIE_TYPE = 'movie' as const;
export const SERIES_TYPE = 'series' as const;
export const CHANNEL_TYPE = 'channel' as const;
export const TV_TYPE = 'tv' as const;
export const ANIME_TYPE = 'anime' as const;

export const TYPES = [
  MOVIE_TYPE,
  SERIES_TYPE,
  CHANNEL_TYPE,
  TV_TYPE,
  ANIME_TYPE,
] as const;

export {
  SERVICES,
  RESOLUTIONS,
  QUALITIES,
  VISUAL_TAGS,
  AUDIO_TAGS,
  AUDIO_CHANNELS,
  PASSTHROUGH_STAGES,
  ENCODES,
  SORT_CRITERIA,
  SORT_DIRECTIONS,
  STREAM_TYPES,
  RESOURCES,
};
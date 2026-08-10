# AIO Quality Profiles

Dictionarry quality profiles, converted into [AIOStreams](https://github.com/Viren070/AIOStreams) **Stream Expression Language (SEL)** and **Regex Filter** synced JSON. Each profile below is a direct 1:1 conversion of its source quality profile's custom formats and scores — nothing rescaled, nothing re-weighted.

Sources:
- **Dictionarry** (11 profiles) — [github.com/Dictionarry-Hub/database](https://github.com/Dictionarry-Hub/database)
- **Dumpstarr** (1 anime profile) — [github.com/Dumpstarr/Database](https://github.com/Dumpstarr/Database)
- **trash-pcd** (1 anime profile) — [github.com/Dictionarry-Hub/trash-pcd](https://github.com/Dictionarry-Hub/trash-pcd)

All three are rebuilt and re-synced automatically once a day — see [Automation](#automation) below.

For the original, authoritative documentation on how these profiles are designed and what they target, see the **[Dictionarry Quality Profile guide](https://v2.dictionarry.dev/quality-profile)**.

## How to use

In AIOStreams:
1. **Filters → Regex → Synced URLs** → add the profile's **Regex** link
2. **Filters → Stream Expressions → Synced URLs** → add the profile's **Stream Expression** link
3. **Sorting** → add **Stream Expression Score** to your sort order (nothing scores without this)

Only add one profile's pair of links at a time — mixing multiple profiles' expressions together will combine their scoring, not let you pick between them.

---

## Master List

### 1080p Balanced
1080p Balanced targets consistent & immutable 1080p WEB-DLs using the Streaming Source and Audio Formats to determine the level of Transparency.
- Average Movie Sizes ~ 4 to 8gb per Movie
- Movie Quality Ranking ~ 6/10
- Average TV Sizes ~ 2 to 4gb per Episode
- TV Quality Ranking ~ 7/10

Stream expression: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/1080p-balanced.expressions.json`  
Regex: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/1080p-balanced.regexes.json`

### 1080p Compact
1080p Compact targets low to medium quality x265 Bluray and WEB Encodes.
- Average Movie Sizes ~ 3 to 6gb per Movie
- Movie Quality Ranking ~ 4/10
- Average TV Sizes ~ 1 to 2gb per Episode
- TV Quality Ranking ~ 4/10

Stream expression: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/1080p-compact.expressions.json`  
Regex: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/1080p-compact.regexes.json`

### 1080p Efficient
1080p Efficient targets high quality x265 Bluray and WEB Encodes.
- Average Movie Sizes ~ 6 to 12gb per Movie
- Movie Quality Ranking ~ 7/10
- Average TV Sizes ~ 2 to 3gb per Episode
- TV Quality Ranking ~ 6/10

Stream expression: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/1080p-efficient.expressions.json`  
Regex: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/1080p-efficient.regexes.json`

### 1080p Quality
1080p Quality utilizes the Golden Popcorn Performance Index to target Transparent x264 1080p Encodes.
- Average Movie Sizes ~ 10 to 15gb per Movie
- Movie Quality Ranking ~ 8/10
- Average TV Sizes ~ 4 to 8gb per Episode
- TV Quality Ranking ~ 8/10

Stream expression: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/1080p-quality.expressions.json`  
Regex: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/1080p-quality.regexes.json`

### 1080p Quality HDR
1080p Quality HDR utilizes the Golden Popcorn Performance Index to target Transparent x265 HDR 1080p Encodes.
- Average Movie Sizes ~ 10 to 20gb per Movie
- Movie Quality Ranking ~ 9/10
- Average TV Sizes ~ 4 to 10gb per Episode
- TV Quality Ranking ~ 9/10

Stream expression: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/1080p-quality-hdr.expressions.json`  
Regex: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/1080p-quality-hdr.regexes.json`

### 1080p Remux
1080p Remux utilizes Audio Formats to prioritise high quality Lossless HD Blurays with a fallback to Transparent Bluray Encodes.
- Average Movie Sizes ~ 20 to 30gb per Movie
- Movie Quality Ranking ~ 10/10
- Average TV Sizes ~ 6 to 12gb per Episode
- TV Quality Ranking ~ 10/10

Stream expression: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/1080p-remux.expressions.json`  
Regex: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/1080p-remux.regexes.json`

### 2160p Balanced
2160p Balanced targets consistent & immutable 2160p WEB-DLs w/ Lossy Audio.
- Average Movie Sizes ~ 15 to 30gb per Movie
- Movie Quality Ranking ~ 8/10
- Average TV Sizes ~ 5 to 15gb per Episode
- TV Quality Ranking ~ 8/10

Stream expression: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/2160p-balanced.expressions.json`  
Regex: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/2160p-balanced.regexes.json`

### 2160p Efficient
2160p Efficient targets consistent & immutable 2160p WEB-DLs w/ Lossy Audio. Specialized Fallback to 1080p Efficient.
- Average Movie Sizes ~ 15 to 30gb per Movie
- Movie Quality Ranking ~ 6/10
- Average TV Sizes ~ 4 to 12gb per Episode
- TV Ranking ~ 6/10

Stream expression: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/2160p-efficient.expressions.json`  
Regex: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/2160p-efficient.regexes.json`

### 2160p Quality
2160p Quality utilizes the Encode Efficiency Index metric at a 60% target ratio to prioritize Transparent x265 4K Encodes.
- Average Movie Sizes ~ 30 to 50gb per Movie
- Movie Quality Ranking ~ 9/10
- Average TV Sizes ~ 10 to 20gb per Episode
- TV Quality Ranking ~ 9/10

Stream expression: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/2160p-quality.expressions.json`  
Regex: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/2160p-quality.regexes.json`

### 2160p Remux
2160p Remux utilizes Video / Audio Formats to prioritise high quality lossless copies of UHD Blurays.
- Average Movie Sizes ~ 40 to 60gb per Movie
- Movie Quality Ranking ~ 10/10
- Average TV Sizes ~ 15 to 30gb per Episode
- TV Quality Ranking ~ 10/10

Stream expression: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/2160p-remux.expressions.json`  
Regex: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/2160p-remux.regexes.json`

### 720p Quality
720p Quality utilizes the Golden Popcorn Performance Index to target Transparent x264 720p Encodes.
- Average Movie Sizes ~ 4 to 8gb per Movie
- Movie Quality Ranking ~ 5/10
- Average TV Sizes ~ 2 to 4gb per Episode
- TV Quality Ranking ~ 5/10

Stream expression: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/720p-quality.expressions.json`  
Regex: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/720p-quality.regexes.json`

### Anime 1080p (Dumpstarr)
Based on the TRaSH Guides Anime Profile, focusing on media that has Dual Audio.
- Grabs between SDTV and 1080p Bluray.
- Prefers Dual Audio media (English + original language) by default. For original-language-only, remove the Dual Audio custom format and set language preference separately. To always prefer Dual Audio, raise the Dual Audio format's score.
- Source: [Dumpstarr/Database](https://github.com/Dumpstarr/Database)

Stream expression: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/anime-1080p.expressions.json`  
Regex: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/anime-1080p.regexes.json`

### [Anime] Remux-1080p (trash-pcd)
Anime profile covering SDTV, DVD, HDTV 720p/1080p, WEBDL 480p/720p/1080p, Bluray 480p/576p/720p/1080p, and Remux 1080p.
- Capped at 1080p — 2160p tiers are present in the source data but disabled.
- Source: [Dictionarry-Hub/trash-pcd](https://github.com/Dictionarry-Hub/trash-pcd) (TRaSH Guides, converted to PCD format)

Stream expression: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/anime-remux-1080p.expressions.json`  
Regex: `https://raw.githubusercontent.com/Redhair777/AIO-Quality-Profiles/main/profiles/anime-remux-1080p.regexes.json`

---

## Automation

`.github/workflows/sync.yml` runs once a day (`0 3 * * *` UTC, plus manual `workflow_dispatch`):
1. Rebuilds a SQLite snapshot from each source's PCD ops (Dictionarry, Dumpstarr, trash-pcd), replayed against the shared [Dictionarry-Hub/schema](https://github.com/Dictionarry-Hub/schema)
2. Reconverts all 13 profiles to SEL/Regex JSON
3. Commits `profiles/*.json` only if the regenerated output actually differs from what's committed

AIOStreams picks up changes automatically on its own sync interval once you've added the links above — no manual re-download needed.


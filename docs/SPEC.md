# SPEC.md — Roblox Market Intelligence MCP Server

## Vision

A coding agent building a Roblox game should know what the market rewards before writing a single line of code. This MCP server delivers that context — live market data interpreted through the lens of Roblox's discovery algorithm — directly into the agent's context window.

The output isn't a leaderboard. It's market intelligence: which genres are algorithm-favored right now, where demand outpaces quality, and what signals the top performers share.

## Problem Statement

Roblox's Recommended for You (RFY) algorithm drives over 90% of organic discovery on the platform. It ranks games based on six per-user signals:

1. **QPTR** — Qualified Play-Through Rate (impressions → intentional plays)
2. **Deep Engagement Rate** — impressions → sustained plays
3. **7-Day Playtime per User** — capped at 60 min/day (grind loops don't count)
4. **7-Day Play Days per User** — return frequency
5. **7-Day Spend Days + Spend per User** — monetization signals
6. **7-Day Intentional Co-Play Days** — friends playing together (added Dec 2025)

These signals are per-user averages, not totals. A small game with highly engaged users competes equally with large games. This is Roblox's documented behavior.

Developers who understand this build differently: they prioritize first-minute onboarding (QPTR), social hooks (co-play), and loop depth over grind length (playtime cap). Coding agents have none of this context.

## What This Server Does

It pulls live public data, computes signal proxies, and presents them through the vocabulary of the discovery algorithm.

### Signal Proxies (derivable from public data)

| Algorithm Signal | Public Proxy | Formula |
|-----------------|-------------|---------|
| QPTR | Like Ratio | upvotes / (upvotes + downvotes) |
| Deep Engagement | Favorites Rate | favorites / total visits |
| Play Days / Playtime | Engagement Ratio | active players / total visits |
| Breakout (new game growing) | Breakout Score | engagement ratio × (1 / log(total_visits + 1)) |
| Co-play signal | Social Keywords | presence of "co-op", "friends", multiplayer mechanics in name/description |

These proxies don't perfectly replicate the algorithm signals — they can't, since those require Creator Dashboard access. But they're the best available approximation from public data, and they're directionally correct.

## MVP Scope (18-hour build)

### Tools

#### `get_trending_genres()`
Returns the top genres ranked by aggregate engagement ratio across their games.

**Input:** none

**Output:**
```json
{
  "genres": [
    {
      "genre": "Survival",
      "game_count": 23,
      "avg_engagement_ratio": 0.0082,
      "avg_like_ratio": 0.84,
      "avg_favorites_rate": 0.031,
      "discovery_signal": "Strong — high engagement and like ratio suggest algorithm is actively distributing these games",
      "top_game": "99 Nights in the Forest"
    }
  ]
}
```

#### `get_genre_analysis(genre: str)`
Deep breakdown of a specific genre through the discovery signal lens.

**Input:** `genre` — genre name or keyword (e.g., "Survival", "Tycoon", "Horror")

**Output:**
```json
{
  "genre": "Survival",
  "game_count": 23,
  "signals": {
    "engagement_ratio": { "avg": 0.0082, "benchmark": "above" },
    "like_ratio": { "avg": 0.84, "benchmark": "above" },
    "favorites_rate": { "avg": 0.031, "benchmark": "average" },
    "breakout_games": ["99 Nights in the Forest", "..."]
  },
  "design_patterns": ["co-op mechanics common", "progression systems", "night/day cycles"],
  "algorithm_read": "Survival games show strong QPTR and engagement proxies. The co-op prevalence aligns with Roblox's Dec 2025 co-play signal addition. Entry opportunity exists for high-quality executions.",
  "saturation": "moderate — 23 games in top 500, quality variance is high"
}
```

#### `get_gap_analysis()`
Identifies genres where demand signals are strong but quality signals are weak — the opening for a well-built entry.

**Input:** none

**Output:**
```json
{
  "gaps": [
    {
      "genre": "Horror",
      "demand_signal": "high — 18 games in top 500, avg 4,200 active players",
      "quality_signal": "weak — avg like ratio 0.61, high variance",
      "opportunity": "Players want horror experiences but current offerings don't retain them. A game with strong first-minute onboarding and social hooks would be algorithm-competitive.",
      "reference_games": ["Scary Elevator", "Piggy"]
    }
  ]
}
```

#### `get_top_performers(metric: str)`
Top games ranked by a specific signal proxy.

**Input:** `metric` — one of: `"engagement"`, `"sentiment"`, `"breakout"`, `"favorites"`

**Output:**
```json
{
  "metric": "breakout",
  "description": "Games with the highest engagement relative to their age — likely receiving current algorithm distribution",
  "games": [
    {
      "name": "99 Nights in the Forest",
      "genre": "Survival",
      "active_players": 142000,
      "engagement_ratio": 0.019,
      "like_ratio": 0.91,
      "breakout_score": 0.87
    }
  ]
}
```

#### `analyze_game_design(game_name: str, wiki_url: str = "")`
Scrapes a competitor game's public Fandom wiki to extract economy design, item costs, currency systems, and progression patterns. Interprets findings through the RFY discovery algorithm lens.

**Input:**
- `game_name` — name of any Roblox game (e.g. `"Blox Fruits"`, `"Adopt Me"`, `"Pet Simulator X"`)
- `wiki_url` — optional direct wiki base URL (e.g. `"https://bloxfruits.fandom.com"`). Auto-discovered if omitted.

**Output:**
```json
{
  "game": "Blox Fruits",
  "wiki_source": "https://bloxfruits.fandom.com",
  "description": "Blox Fruits is an action RPG where players fight enemies, level up, and collect Devil Fruits...",
  "currencies_detected": [
    "Robux (premium Roblox currency)",
    "Beli (in-game currency)"
  ],
  "economy_items_found": 47,
  "sample_items": [
    { "fruit": "Chop", "type": "Common", "cost": "3,000 Beli" },
    { "fruit": "Bomb", "type": "Common", "cost": "5,000 Beli" }
  ],
  "algorithm_lens": "Dual-currency economy (Robux + Beli grind): standard Roblox retention engine. In-game currency requires daily play sessions (boosts 7-day play-days proxy). Rich item catalog (47+ items): depth of collectibles correlates with repeat-session motivation and favorites rate.",
  "pages_fetched": 4,
  "data_note": "Sourced from public wiki. Item costs reflect wiki accuracy, not live game state."
}
```

**Data source:** Fandom wikis (most Roblox games with active communities are documented at `<gamename>.fandom.com`). Pages fetched include main page, shop, items, gamepasses, and currency sub-pages.

**When auto-discovery fails:** Provide `wiki_url` directly. Common reasons for failure: wiki slug doesn't follow standard patterns, game has no public wiki, or wiki is on a non-Fandom platform.

## Data Pipeline

```
Step 1: Rolimons gamelist
  GET api.rolimons.com/games/v1/gamelist
  → ~7,619 games with placeId, name, active_players
  → Filter: top 300 by active_players

Step 2: placeId → universeId conversion
  GET apis.rotunnel.com/universes/v1/places/{placeId}/universe
  → Batched with asyncio.gather, 50 concurrent max
  → Cache results in memory

Step 3: Game details
  GET games.rotunnel.com/v1/games?universeIds={ids}
  → Batched in groups of 100 (API limit)
  → Returns: visits, playing, upvotes, downvotes, maxPlayers, genre, created, updated

Step 4: Signal computation
  → engagement_ratio = active_players / visits
  → like_ratio = upvotes / (upvotes + downvotes)
  → favorites_rate = favorites / visits
  → breakout_score = engagement_ratio * (1 / log10(visits + 10))
  → genre clustering from genre field + keyword extraction from name

Step 5: Cache full dataset in memory
  → Refresh every 10 minutes
  → All tool calls read from cache (no per-call latency)
```

## Wiki Intelligence Pipeline

```
analyze_game_design(game_name, wiki_url?)
  → _discover_fandom_wiki()  (if no wiki_url provided)
      → probe <gamename>.fandom.com and <game-name>.fandom.com
      → return first URL where slug appears in final response URL
  → fetch up to 10 sub-pages per wiki
      → /wiki/, /wiki/Gamepasses, /wiki/Shop, /wiki/Items,
        /wiki/Currency, /wiki/Currencies, /wiki/Store, etc.
  → _parse_tables()           (stdlib html.parser, outermost tables only)
  → _table_to_records()       (first row = headers, rest = data)
  → _is_economy_table()       (keyword filter: cost/price/robux/coin/gem/…)
  → _detect_currencies()      (match known currency names in table content)
  → _build_algorithm_lens()   (interpret economy structure as algorithm signals)
  → return structured dict
```

**No new dependencies.** Uses `html.parser` from stdlib. `httpx` is already required.

**Graceful degradation:** Individual page failures are silently dropped. If all pages fail, returns an error dict with a hint for the user.

## Out of Scope (MVP)

- Revenue data (not publicly available)
- Historical trends (requires RTrack paid API)
- Per-game QPTR (requires Creator Dashboard access)
- Multi-platform support (Steam, mobile)
- Web UI or deployed endpoint
- Auth or rate limiting
- Persistent storage

## Post-Hackathon Roadmap

- Historical trend tracking (store snapshots in PostgreSQL)
- RTrack API integration for monetization score
- Multi-platform expansion (SteamSpy, itch.io)
- Deployed HTTP transport for remote access
- Subscription product ($10-20/mo, operator absorbs API costs)

## Success Criteria (Hackathon)

A coding agent given access to this MCP server should, without any additional prompting, produce a game concept that:
1. Targets a genre with strong observable discovery signals
2. Includes design elements that proxy well against the algorithm signals
3. Avoids genres with high saturation and weak quality signals

This is demonstrable in a 2-minute video.

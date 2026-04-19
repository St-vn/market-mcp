# CLAUDE.md — Roblox Market Intelligence MCP Server

## What This Is

An MCP server that delivers Roblox market intelligence into a coding agent's context window before it builds. It pulls live market data and interprets it through the lens of Roblox's Recommended for You (RFY) discovery algorithm — the system that determines organic growth on the platform.

The agent gets market intelligence, not raw numbers.

## Project Structure

```
roblox-market-mcp/
├── server.py          # FastMCP server entry point, all four tool definitions
├── data/
│   ├── fetcher.py     # HTTP pipeline: Rolimons → universeIds → game details
│   └── signals.py     # Signal computation, genre aggregation, gap analysis
├── requirements.txt
├── README.md
├── SPEC.md
├── ARCHITECTURE.md
└── CLAUDE.md          # This file
```

## What to Build

Implement the files exactly as specified in `ARCHITECTURE.md`. The code there is a complete reference implementation — use it directly.

### Build order

1. `requirements.txt` — two dependencies only: `fastmcp>=3.2.0` and `httpx>=0.27.0`
2. `data/signals.py` — pure Python, no I/O, easiest to test in isolation
3. `data/fetcher.py` — async HTTP pipeline, three data sources
4. `server.py` — FastMCP wiring and cache layer

## Data Pipeline (critical to understand)

```
Rolimons gamelist (one call, ~7,600 games)
  → sort by active_players, take top 300
  → each game has: place_id, name, active_players

placeId → universeId (300 concurrent calls, semaphore-limited to 50)
  → endpoint: apis.rotunnel.com/universes/v1/places/{place_id}/universe
  → games that fail conversion are silently dropped

universeId → game details (3 batched calls of 100)
  → endpoint: games.rotunnel.com/v1/games?universeIds={comma-separated}
  → adds: visits, upvotes, downvotes, favorites, genre, created, updated

Merge all data per game → pass to signals.py
```

## Signals (critical to understand)

All signals are proxies for Roblox's RFY algorithm signals. The algorithm documentation is public (create.roblox.com/docs/discovery) and these mappings are grounded in it:

| Computed signal | Algorithm proxy | Formula |
|----------------|-----------------|---------|
| `engagement_ratio` | 7-day play days / playtime per user | `active_players / visits` |
| `like_ratio` | QPTR (qualified play-through rate) | `upvotes / (upvotes + downvotes)` |
| `favorites_rate` | Deep engagement rate | `favorites / visits` |
| `breakout_score` | New game gaining traction | `engagement_ratio / log10(visits + 10)` |

These are approximations, not exact replicas. The algorithm signals require Creator Dashboard access. The proxies are directionally correct based on public data.

## Tool Behavior

### `get_trending_genres()`
- Reads from cache
- Calls `compute_genre_stats(snapshot)` with no filter
- Returns all genres sorted by `avg_engagement_ratio` descending
- Each genre entry includes: game_count, three signal averages, benchmarks, discovery_signal string, top_game name

### `get_genre_analysis(genre)`
- Reads from cache
- Calls `compute_genre_stats(snapshot, filter_genre=genre)`
- Fuzzy matches genre name (case-insensitive substring match)
- Returns single genre detail with same structure as above
- Returns error + available genres list if no match found

### `get_gap_analysis()`
- Reads from cache
- Calls `compute_gap_analysis(snapshot)`
- Gap criteria: avg_active > 1000 AND like_ratio below "above" threshold AND engagement_ratio below "above" threshold
- Returns list of gap opportunities sorted by demand signal (avg active players) descending

### `get_top_performers(metric)`
- Reads from cache
- Calls `compute_top_performers(snapshot, metric)`
- Valid metrics: "engagement", "sentiment", "breakout", "favorites"
- Returns top 20 games for that metric with supporting context

## Cache Behavior

```python
_cache = {"data": None, "timestamp": 0}
CACHE_TTL = 600  # 10 minutes
```

- Cold start: first tool call triggers the full pipeline (~10-30 seconds)
- Warm: subsequent calls return immediately from cache
- Refresh: automatic after TTL expires
- This is acceptable for a demo — warn the user that first call may be slow

## Running Locally

```bash
pip install fastmcp httpx
python server.py
```

Add to Claude Code's MCP config:
```json
{
  "mcpServers": {
    "roblox-market": {
      "command": "python",
      "args": ["/absolute/path/to/server.py"]
    }
  }
}
```

## What NOT to Build

- No web UI
- No database or persistent storage
- No auth or API keys
- No rate limiting middleware
- No tests (hackathon scope)
- No HTTP transport (STDIO only)
- No revenue data tools (not publicly available, don't fake it)
- No historical trend tracking (requires paid APIs)

## Known Limitations

**universeId conversion may fail for some games.** Games where the conversion fails are dropped. This is acceptable — the top 200-250 games will reliably convert, which is the relevant dataset.

**RoTunnel is an unofficial proxy.** It may have occasional downtime. If it fails, the server degrades gracefully (affected games are dropped, others still return).

**Genre field from Roblox API is coarse.** The API returns broad genres (Action, RPG, Adventure, etc.). Game name keyword extraction is not implemented in MVP — genre clustering uses only the API's genre field.

**Signals are proxies, not ground truth.** The tool outputs say "proxy for QPTR" not "this is QPTR." This framing is intentional and accurate.

## Demo Script (for the 2-minute video)

1. Show Claude Code with MCP server configured
2. Prompt: "Use the market intelligence tools to research the Roblox market, then propose a game concept."
3. Claude Code calls `get_trending_genres()` — sees which genres are algorithm-favored
4. Claude Code calls `get_gap_analysis()` — identifies the best opportunity
5. Claude Code calls `get_genre_analysis(gap_genre)` — gets design signal context
6. Claude Code proposes a specific game concept with mechanics that proxy well against algorithm signals
7. Optionally: Claude Code starts scaffolding the game structure

**The demo proves the concept works.** The agent makes informed decisions it couldn't make without the MCP server.

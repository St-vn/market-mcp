# ARCHITECTURE.md — Roblox Market Intelligence MCP Server

## Overview

```
┌─────────────────────────────────────────────────────┐
│                   Claude Code                        │
│              (MCP client, STDIO)                    │
└────────────────────┬────────────────────────────────┘
                     │ MCP protocol (STDIO)
┌────────────────────▼────────────────────────────────┐
│              FastMCP Server (server.py)              │
│                                                     │
│  Tools:                                             │
│  • get_trending_genres()                            │
│  • get_genre_analysis(genre)                        │
│  • get_gap_analysis()                               │
│  • get_top_performers(metric)                       │
│                                                     │
│  Cache layer (in-memory, 10min TTL)                 │
└────────────────────┬────────────────────────────────┘
                     │ httpx async
     ┌───────────────┼───────────────┐
     ▼               ▼               ▼
Rolimons API    RoTunnel Proxy   RoTunnel Proxy
(gamelist)      (universes API)  (games detail API)
```

## File Structure

```
roblox-market-mcp/
├── server.py          # FastMCP server, tool definitions
├── data/
│   ├── fetcher.py     # All HTTP calls, async, batched
│   └── signals.py     # Signal computation and genre aggregation
├── README.md
├── SPEC.md
├── ARCHITECTURE.md
├── CLAUDE.md
└── requirements.txt
```

## server.py

Entry point and tool definitions. FastMCP handles all MCP protocol complexity.

```python
from fastmcp import FastMCP
from data.fetcher import get_market_snapshot
from data.signals import compute_genre_stats, compute_gap_analysis, compute_top_performers

mcp = FastMCP("Roblox Market Intelligence")

# In-memory cache
_cache = {"data": None, "timestamp": 0}
CACHE_TTL = 600  # 10 minutes

async def get_cached_snapshot():
    import time
    if _cache["data"] is None or time.time() - _cache["timestamp"] > CACHE_TTL:
        _cache["data"] = await get_market_snapshot()
        _cache["timestamp"] = time.time()
    return _cache["data"]

@mcp.tool
async def get_trending_genres() -> dict:
    """
    Returns genres ranked by algorithm-favorable engagement signals.
    Uses live Roblox market data interpreted through the discovery algorithm lens.
    Signals proxy: engagement ratio (play days), like ratio (QPTR), favorites rate (deep engagement).
    """
    snapshot = await get_cached_snapshot()
    return compute_genre_stats(snapshot)

@mcp.tool
async def get_genre_analysis(genre: str) -> dict:
    """
    Deep analysis of a specific genre through the Roblox discovery algorithm lens.
    Returns signal proxies, design pattern observations, saturation assessment,
    and an algorithm readiness summary.
    Args:
        genre: Genre name or keyword (e.g. "Survival", "Tycoon", "Horror", "RPG")
    """
    snapshot = await get_cached_snapshot()
    return compute_genre_stats(snapshot, filter_genre=genre)

@mcp.tool
async def get_gap_analysis() -> dict:
    """
    Identifies genres where player demand is high but quality signals are weak.
    These are the best entry opportunities: players want this content but existing
    games aren't satisfying the discovery algorithm's engagement signals.
    """
    snapshot = await get_cached_snapshot()
    return compute_gap_analysis(snapshot)

@mcp.tool
async def get_top_performers(metric: str) -> dict:
    """
    Top games ranked by a specific discovery signal proxy.
    Args:
        metric: One of "engagement" (play days proxy), "sentiment" (QPTR proxy),
                "breakout" (new games gaining algorithm traction), "favorites" (deep engagement proxy)
    """
    snapshot = await get_cached_snapshot()
    return compute_top_performers(snapshot, metric)

if __name__ == "__main__":
    mcp.run()  # STDIO transport, works directly with Claude Code
```

## data/fetcher.py

All network calls. Async, batched to respect rate limits.

```python
import httpx
import asyncio

ROLIMONS_GAMELIST = "https://api.rolimons.com/games/v1/gamelist"
ROTUNNEL_UNIVERSE = "https://apis.rotunnel.com/universes/v1/places/{place_id}/universe"
ROTUNNEL_GAMES = "https://games.rotunnel.com/v1/games"

TOP_N = 300          # Games to pull from Rolimons by player count
BATCH_SIZE = 100     # Roblox game detail API limit per request
CONCURRENT = 50      # Max concurrent universe ID lookups

async def get_market_snapshot() -> list[dict]:
    """Full pipeline: Rolimons → universeIds → game details → merged records"""
    async with httpx.AsyncClient(timeout=30) as client:
        # Step 1: Rolimons gamelist
        games = await fetch_rolimons(client)

        # Step 2: placeId → universeId
        games = await enrich_universe_ids(client, games)

        # Step 3: Game details
        games = await enrich_game_details(client, games)

    return games

async def fetch_rolimons(client: httpx.AsyncClient) -> list[dict]:
    resp = await client.get(ROLIMONS_GAMELIST)
    resp.raise_for_status()
    raw = resp.json()

    games = [
        {"place_id": str(pid), "name": data[0], "active_players": data[1]}
        for pid, data in raw["games"].items()
    ]

    # Top N by active players
    games.sort(key=lambda g: g["active_players"], reverse=True)
    return games[:TOP_N]

async def enrich_universe_ids(client: httpx.AsyncClient, games: list[dict]) -> list[dict]:
    sem = asyncio.Semaphore(CONCURRENT)

    async def fetch_one(game):
        async with sem:
            try:
                url = ROTUNNEL_UNIVERSE.format(place_id=game["place_id"])
                resp = await client.get(url)
                if resp.status_code == 200:
                    game["universe_id"] = str(resp.json()["universeId"])
            except Exception:
                pass  # Skip games where conversion fails
        return game

    return await asyncio.gather(*[fetch_one(g) for g in games])

async def enrich_game_details(client: httpx.AsyncClient, games: list[dict]) -> list[dict]:
    # Only process games that have a universe_id
    with_ids = [g for g in games if "universe_id" in g]
    id_map = {g["universe_id"]: g for g in with_ids}

    # Batch in groups of BATCH_SIZE
    universe_ids = list(id_map.keys())
    batches = [universe_ids[i:i+BATCH_SIZE] for i in range(0, len(universe_ids), BATCH_SIZE)]

    for batch in batches:
        try:
            params = {"universeIds": ",".join(batch)}
            resp = await client.get(ROTUNNEL_GAMES, params=params)
            if resp.status_code != 200:
                continue

            for detail in resp.json().get("data", []):
                uid = str(detail["id"])
                if uid in id_map:
                    id_map[uid].update({
                        "visits": detail.get("visits", 0),
                        "upvotes": detail.get("totalUpVotes", 0),
                        "downvotes": detail.get("totalDownVotes", 0),
                        "favorites": detail.get("favoritedCount", 0),
                        "genre": detail.get("genre", "Unknown"),
                        "created": detail.get("created", ""),
                        "updated": detail.get("updated", ""),
                    })
        except Exception:
            continue

    return games
```

## data/signals.py

Signal computation. This is where the discovery algorithm knowledge lives.

```python
import math
from collections import defaultdict

# Discovery algorithm context baked in as constants
ALGORITHM_SIGNALS = {
    "engagement_ratio": "Proxy for 7-day play days and playtime per user. High ratio = players returning, algorithm rewards this.",
    "like_ratio": "Proxy for QPTR (qualified play-through rate). High ratio = players not bouncing, algorithm rewards this.",
    "favorites_rate": "Proxy for deep engagement rate. Favorites = future intent, sustained interest signal.",
    "breakout_score": "Identifies new games gaining algorithm traction before they appear in raw player counts.",
}

BENCHMARK_THRESHOLDS = {
    "engagement_ratio": {"above": 0.005, "below": 0.001},
    "like_ratio": {"above": 0.80, "below": 0.65},
    "favorites_rate": {"above": 0.02, "below": 0.005},
}

def compute_signals(game: dict) -> dict:
    visits = max(game.get("visits", 1), 1)
    upvotes = game.get("upvotes", 0)
    downvotes = game.get("downvotes", 0)
    favorites = game.get("favorites", 0)
    active = game.get("active_players", 0)

    total_votes = upvotes + downvotes
    like_ratio = upvotes / total_votes if total_votes > 0 else 0.5
    engagement_ratio = active / visits
    favorites_rate = favorites / visits
    breakout_score = engagement_ratio * (1 / math.log10(visits + 10))

    return {
        **game,
        "like_ratio": round(like_ratio, 3),
        "engagement_ratio": round(engagement_ratio, 6),
        "favorites_rate": round(favorites_rate, 6),
        "breakout_score": round(breakout_score, 8),
    }

def benchmark(value: float, metric: str) -> str:
    thresholds = BENCHMARK_THRESHOLDS.get(metric, {})
    if value >= thresholds.get("above", float("inf")):
        return "above"
    if value <= thresholds.get("below", 0):
        return "below"
    return "average"

def cluster_by_genre(games: list[dict]) -> dict[str, list[dict]]:
    clusters = defaultdict(list)
    for g in games:
        genre = g.get("genre", "Unknown")
        if genre and genre != "Unknown":
            clusters[genre].append(g)
    return clusters

def genre_summary(genre: str, games: list[dict]) -> dict:
    if not games:
        return {}

    avg = lambda key: sum(g.get(key, 0) for g in games) / len(games)
    top_game = max(games, key=lambda g: g.get("active_players", 0))

    avg_engagement = avg("engagement_ratio")
    avg_like = avg("like_ratio")
    avg_favorites = avg("favorites_rate")

    # Discovery algorithm read
    signals_above = sum([
        avg_engagement >= BENCHMARK_THRESHOLDS["engagement_ratio"]["above"],
        avg_like >= BENCHMARK_THRESHOLDS["like_ratio"]["above"],
        avg_favorites >= BENCHMARK_THRESHOLDS["favorites_rate"]["above"],
    ])
    if signals_above >= 2:
        discovery_signal = "Strong — multiple engagement proxies above benchmark. Algorithm likely distributing these games."
    elif signals_above == 1:
        discovery_signal = "Moderate — some signals above benchmark. Opportunity if execution improves weaker signals."
    else:
        discovery_signal = "Weak — signals below benchmark. Existing games not satisfying the algorithm."

    return {
        "genre": genre,
        "game_count": len(games),
        "avg_engagement_ratio": round(avg_engagement, 6),
        "avg_like_ratio": round(avg_like, 3),
        "avg_favorites_rate": round(avg_favorites, 6),
        "engagement_benchmark": benchmark(avg_engagement, "engagement_ratio"),
        "like_benchmark": benchmark(avg_like, "like_ratio"),
        "discovery_signal": discovery_signal,
        "top_game": top_game.get("name", "Unknown"),
        "top_game_active_players": top_game.get("active_players", 0),
    }

def compute_genre_stats(games: list[dict], filter_genre: str = None) -> dict:
    enriched = [compute_signals(g) for g in games if g.get("visits", 0) > 0]
    clusters = cluster_by_genre(enriched)

    if filter_genre:
        # Fuzzy match genre name
        key = next(
            (k for k in clusters if filter_genre.lower() in k.lower()),
            None
        )
        if not key:
            return {"error": f"No genre found matching '{filter_genre}'", "available": list(clusters.keys())}
        summaries = [genre_summary(key, clusters[key])]
    else:
        summaries = [genre_summary(genre, games) for genre, games in clusters.items()]
        summaries.sort(key=lambda s: s.get("avg_engagement_ratio", 0), reverse=True)

    return {
        "algorithm_context": "Signals are proxies for Roblox's RFY algorithm: engagement_ratio→play days, like_ratio→QPTR, favorites_rate→deep engagement.",
        "genres": summaries,
    }

def compute_gap_analysis(games: list[dict]) -> dict:
    enriched = [compute_signals(g) for g in games if g.get("visits", 0) > 0]
    clusters = cluster_by_genre(enriched)

    gaps = []
    for genre, genre_games in clusters.items():
        if len(genre_games) < 3:
            continue
        summary = genre_summary(genre, genre_games)
        avg_active = sum(g.get("active_players", 0) for g in genre_games) / len(genre_games)

        # Gap = high demand (players exist) + weak quality signals (low like ratio)
        is_gap = (
            avg_active > 1000 and
            summary["avg_like_ratio"] < BENCHMARK_THRESHOLDS["like_ratio"]["above"] and
            summary["avg_engagement_ratio"] < BENCHMARK_THRESHOLDS["engagement_ratio"]["above"]
        )

        if is_gap:
            gaps.append({
                "genre": genre,
                "demand_signal": f"{int(avg_active):,} avg active players — players want this content",
                "quality_signal": f"Like ratio {summary['avg_like_ratio']:.0%}, engagement ratio below benchmark",
                "opportunity": (
                    f"{genre} shows clear player demand but existing games aren't satisfying "
                    f"the algorithm's engagement and QPTR signals. A well-executed entry with "
                    f"strong onboarding and social hooks would be algorithm-competitive."
                ),
                "game_count": len(genre_games),
                "top_games": [g["name"] for g in sorted(genre_games, key=lambda g: g.get("active_players", 0), reverse=True)[:3]],
            })

    gaps.sort(key=lambda g: int(g["demand_signal"].split(" ")[0].replace(",", "")), reverse=True)

    return {
        "algorithm_context": "Gaps are genres where player demand exists but quality signals suggest the algorithm is not distributing them efficiently. These represent the highest-opportunity entry points.",
        "gaps": gaps,
    }

def compute_top_performers(games: list[dict], metric: str) -> dict:
    enriched = [compute_signals(g) for g in games if g.get("visits", 0) > 0]

    metric_map = {
        "engagement": ("engagement_ratio", "Proxy for 7-day play days. High = players returning repeatedly."),
        "sentiment": ("like_ratio", "Proxy for QPTR. High = players not bouncing after first session."),
        "breakout": ("breakout_score", "New games gaining algorithm traction. Likely in active distribution phase."),
        "favorites": ("favorites_rate", "Proxy for deep engagement. Players saving for future play."),
    }

    if metric not in metric_map:
        return {"error": f"Unknown metric '{metric}'", "valid_metrics": list(metric_map.keys())}

    key, description = metric_map[metric]
    ranked = sorted(enriched, key=lambda g: g.get(key, 0), reverse=True)[:20]

    return {
        "metric": metric,
        "description": description,
        "algorithm_signal": ALGORITHM_SIGNALS.get(key, ""),
        "games": [
            {
                "name": g.get("name"),
                "genre": g.get("genre"),
                "active_players": g.get("active_players"),
                key: g.get(key),
                "like_ratio": g.get("like_ratio"),
            }
            for g in ranked
        ],
    }
```

## Key Design Decisions

**STDIO transport, not HTTP.** Claude Code connects to MCP servers via STDIO by default. No port, no deployment, no network config needed for the demo. The server is invoked as a subprocess.

**In-memory cache.** The full pipeline (Rolimons → universeIds → game details) takes 10-30 seconds on cold start due to batched HTTP calls. All four tools read from the same cached snapshot. Cache refreshes every 10 minutes. This makes tool calls feel instant after the first warm-up.

**RoTunnel proxy.** Roblox's own APIs have CORS restrictions and inconsistent rate limiting from external IPs. RoTunnel rotates IPs and proxies the exact same endpoints, no signup required. This eliminates the most fragile part of the data pipeline.

**Discovery knowledge in tool docstrings.** FastMCP uses Python docstrings to generate MCP tool descriptions. The algorithm context — what signals mean, why they matter, how they relate to organic growth — lives in the docstrings. When Claude Code reads the tool list, it gets the interpretation framework for free.

**Per-user signal framing.** All outputs are framed in per-user terms, not totals. This reflects how the algorithm actually works (per Roblox's official documentation) and prevents the agent from optimizing for raw player count instead of engagement quality.

## Rate Limit Handling

- Rolimons: No documented rate limit. One call per cache refresh (every 10 min). Low risk.
- RoTunnel (universeId): 50 concurrent requests max via semaphore. IP rotation handles rate limits.
- RoTunnel (game details): Batched in 100s. 3 batches for 300 games. Low risk.

If any step fails, games without that data are silently excluded. The server degrades gracefully rather than erroring.

## requirements.txt

```
fastmcp>=3.2.0
httpx>=0.27.0
```

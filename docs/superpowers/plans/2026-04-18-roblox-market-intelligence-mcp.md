# Roblox Market Intelligence MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastMCP server exposing four tools — `get_trending_genres`, `get_genre_analysis`, `get_gap_analysis`, `get_top_performers` — that deliver Roblox market intelligence framed through the Recommended-for-You (RFY) discovery algorithm directly into a coding agent's context window.

**Architecture:** STDIO-transport FastMCP server (`server.py`) wraps an in-memory 10-minute cache around a three-stage async HTTP pipeline (`data/fetcher.py`: Rolimons gamelist → RoTunnel universe-id lookups → RoTunnel game detail batches). A pure-Python computation module (`data/signals.py`) turns raw game records into per-user signal proxies (engagement ratio, like ratio, favorites rate, breakout score), clusters by genre, and produces gap analyses. Tool docstrings embed the discovery-algorithm vocabulary so MCP clients receive the interpretation framing as part of tool discovery.

**Tech Stack:** Python 3.9+ (uses PEP 585 generic builtins like `list[dict]`), `fastmcp>=3.2.0`, `httpx>=0.27.0` async client, `asyncio`, stdlib `math`. No database, no persistent storage, no auth, no automated tests (hackathon scope per CLAUDE.md).

---

## Conventions For This Plan

- **Testing deviation:** `CLAUDE.md` explicitly scopes out automated tests ("No tests (hackathon scope)"). The standard writing-plans test-first loop is replaced here with a manual **smoke verification** step per task, exercising each module via `python -c` or a live pipeline run. User instructions override the skill default per the superpowers instruction priority.
- **Reference implementation:** `docs/ARCHITECTURE.md` contains complete reference code. Each task below inlines the exact code verbatim — do not paraphrase or restructure.
- **Commands:** `git` commands are prefixed with `rtk` (token-optimized wrapper, per user's global instructions). `python` and `pip` commands pass through unchanged.
- **Working directory:** All paths are relative to repo root `C:/Users/megas/Documents/GitHub/market-mcp`. Forward slashes work in the bash shell on Windows.

## File Structure

| Path | Status | Responsibility |
|------|--------|----------------|
| `requirements.txt` | exists, untracked | Pin `fastmcp>=3.2.0` + `httpx>=0.27.0` |
| `CLAUDE.md`, `README.md`, `docs/` | exist, untracked | Specs + reference implementation — committed as baseline |
| `data/__init__.py` | create | Empty package marker |
| `data/signals.py` | create | Pure-Python: signal math, benchmarks, genre aggregation, gap analysis |
| `data/fetcher.py` | create | Async HTTP: Rolimons → universeId → game details |
| `server.py` | create | FastMCP entrypoint: cache layer + four tool definitions |

Files are split by responsibility: pure computation (signals) is isolated from I/O (fetcher) is isolated from MCP protocol wiring (server). This makes the signals module trivially smoke-testable without network and keeps the fetcher diagnosable in isolation.

---

### Task 1: Commit baseline (specs + deps)

**Why first:** The repo has no commits yet. Lock in the specs and pinned deps as the starting point so later feature commits diff cleanly against documented intent.

**Files:**
- Commit: `requirements.txt`, `CLAUDE.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/SPEC.md`, `docs/market-intelligence-mcp-generalized.md`, `docs/superpowers/plans/2026-04-18-roblox-market-intelligence-mcp.md`

- [ ] **Step 1: Verify working tree matches expectations**

```bash
rtk git status
```

Expected: the files listed above appear as untracked. Branch is `main`. No staged changes.

- [ ] **Step 2: Stage baseline files explicitly (no `git add .`)**

```bash
rtk git add requirements.txt CLAUDE.md README.md docs/ARCHITECTURE.md docs/SPEC.md docs/market-intelligence-mcp-generalized.md docs/superpowers/plans/2026-04-18-roblox-market-intelligence-mcp.md
```

Expected: no output. `rtk git status` now shows these files as staged, others unchanged.

- [ ] **Step 3: Commit the baseline**

```bash
rtk git commit -m "chore: baseline specs and pinned dependencies

Locks in CLAUDE.md, README.md, SPEC.md, ARCHITECTURE.md, and
the generalized-pattern doc as the reference implementation
brief. requirements.txt pins fastmcp>=3.2.0 and httpx>=0.27.0.
Also commits the implementation plan for traceability."
```

Expected: single commit on `main` with the files above.

---

### Task 2: Implement data/signals.py

**Why second:** `signals.py` is pure Python with no I/O. Verifying it against a synthetic dataset locks in the signal math and genre aggregation before any network dependency is introduced.

**Files:**
- Create: `data/__init__.py`
- Create: `data/signals.py`

- [ ] **Step 1: Create the empty package marker**

File: `data/__init__.py` (zero-byte file, no content).

- [ ] **Step 2: Create data/signals.py with the full signal-computation module**

File: `data/signals.py`

```python
import math
from collections import defaultdict

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

- [ ] **Step 3: Smoke-verify signal math against a synthetic dataset**

```bash
python -c "
from data.signals import compute_signals, genre_summary, compute_genre_stats, compute_gap_analysis, compute_top_performers
fake = [
    {'name':'A','genre':'Survival','visits':100000,'upvotes':9000,'downvotes':1000,'favorites':3000,'active_players':800},
    {'name':'B','genre':'Survival','visits':50000,'upvotes':4000,'downvotes':800,'favorites':1200,'active_players':400},
    {'name':'C','genre':'Survival','visits':20000,'upvotes':1500,'downvotes':500,'favorites':400,'active_players':150},
    {'name':'D','genre':'Horror','visits':800000,'upvotes':3000,'downvotes':2500,'favorites':1500,'active_players':4500},
    {'name':'E','genre':'Horror','visits':600000,'upvotes':2500,'downvotes':2200,'favorites':1100,'active_players':3800},
    {'name':'F','genre':'Horror','visits':300000,'upvotes':1800,'downvotes':1700,'favorites':700,'active_players':2200},
]
print('---genre_stats---')
print(compute_genre_stats(fake))
print('---gap_analysis---')
print(compute_gap_analysis(fake))
print('---top_performers(breakout)---')
print(compute_top_performers(fake, 'breakout'))
print('---top_performers(invalid)---')
print(compute_top_performers(fake, 'nonsense'))
"
```

Expected output sanity checks (exact numeric values not required — confirm shape and semantics):
- `genre_stats.genres` has two entries; `Survival` appears first (its avg engagement ratio ≈ 0.008 beats Horror's ≈ 0.006).
- `Survival.discovery_signal` starts with `"Strong —"` (all three signals above benchmark).
- `Horror.discovery_signal` starts with `"Weak —"` (like_ratio ≈ 0.54, favorites_rate ≈ 0.002, engagement_ratio ≈ 0.006 — only engagement is above).
- `gap_analysis.gaps` contains exactly one entry: `Horror`. Survival is filtered out (its like_ratio is above the 0.80 threshold).
- `top_performers.metric == 'breakout'`, `games` list has 6 entries sorted by `breakout_score` descending.
- `top_performers(invalid)` returns `{"error": "Unknown metric 'nonsense'", "valid_metrics": ["engagement", "sentiment", "breakout", "favorites"]}`.

Failure diagnostics:
- `SyntaxError: invalid syntax` on `list[dict]` / `dict[str, list[dict]]`: Python < 3.9. Run `python --version`. Upgrade or swap to `List[Dict]` from `typing`.
- Any entry in `gaps` that is not `Horror`: review the `is_gap` condition and BENCHMARK_THRESHOLDS values against the inlined code.
- `Survival` ranks below `Horror`: review `compute_genre_stats` sort key and ensure `compute_signals` is round-tripping `active_players`.

- [ ] **Step 4: Commit**

```bash
rtk git add data/__init__.py data/signals.py
rtk git commit -m "feat: signal proxies and genre aggregation

Pure-Python module computing four RFY-algorithm proxies from
raw game records (engagement_ratio, like_ratio, favorites_rate,
breakout_score), plus genre clustering, benchmark classification,
gap analysis, and top-performer ranking. No I/O — easy to reason
about in isolation. Discovery-algorithm vocabulary is baked in
as ALGORITHM_SIGNALS and surfaced via tool response payloads."
```

---

### Task 3: Implement data/fetcher.py (async HTTP pipeline)

**Why third:** `fetcher.py` is the riskiest module — external APIs, flaky network, unofficial proxy. Verifying it with a live run before the server wires it to the cache confirms the record shape handed to `signals.py`.

**Files:**
- Create: `data/fetcher.py`

- [ ] **Step 1: Create data/fetcher.py**

File: `data/fetcher.py`

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
        games = await fetch_rolimons(client)
        games = await enrich_universe_ids(client, games)
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
                pass
        return game

    return await asyncio.gather(*[fetch_one(g) for g in games])

async def enrich_game_details(client: httpx.AsyncClient, games: list[dict]) -> list[dict]:
    with_ids = [g for g in games if "universe_id" in g]
    id_map = {g["universe_id"]: g for g in with_ids}

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

- [ ] **Step 2: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: `fastmcp>=3.2.0` and `httpx>=0.27.0` resolved and installed (or "already satisfied").

- [ ] **Step 3: Smoke-verify the full live pipeline**

Hits Rolimons + RoTunnel live. Takes ~10–30 seconds. Network required.

```bash
python -c "
import asyncio, time
from data.fetcher import get_market_snapshot
t0 = time.time()
games = asyncio.run(get_market_snapshot())
elapsed = time.time() - t0
with_detail = [g for g in games if 'visits' in g]
with_genre = [g for g in with_detail if g.get('genre') not in (None, '', 'Unknown')]
print(f'elapsed: {elapsed:.1f}s  total: {len(games)}  with_detail: {len(with_detail)}  with_genre: {len(with_genre)}')
print('sample:', with_detail[0] if with_detail else 'NONE')
genres = sorted(set(g['genre'] for g in with_genre))
print('unique_genres:', genres)
"
```

Expected (approximate, varies day-to-day):
- `total` ≈ 300 (TOP_N from Rolimons).
- `with_detail` ≥ 200 (some games silently dropped when universeId conversion fails — acceptable per CLAUDE.md "Known Limitations").
- `with_genre` ≥ 200.
- `elapsed` 10–30 seconds.
- `sample` dict includes keys `place_id`, `name`, `active_players`, `universe_id`, `visits`, `upvotes`, `downvotes`, `favorites`, `genre`, `created`, `updated`.
- `unique_genres` contains typical Roblox genres (e.g. `Adventure`, `All Genres`, `Town and City`, `Action`, `Role-Playing`).

Failure diagnostics:
- `total == 0`: Rolimons API shape changed. Manually inspect `curl -s https://api.rolimons.com/games/v1/gamelist | head -c 500` — the code expects `raw["games"]` to be a dict of `{placeId: [name, active_players, ...]}`.
- `with_detail == 0`: RoTunnel likely down or blocked. Probe `curl https://apis.rotunnel.com/universes/v1/places/920587237/universe` (Adopt Me) — should return JSON containing `universeId`. If 5xx, wait and retry; if 4xx, RoTunnel endpoints may have changed.
- `elapsed > 60s`: RoTunnel slowness. Retry once. Not a blocker unless sustained.

- [ ] **Step 4: Smoke-verify signals compose correctly with live data**

```bash
python -c "
import asyncio
from data.fetcher import get_market_snapshot
from data.signals import compute_genre_stats, compute_gap_analysis, compute_top_performers
games = asyncio.run(get_market_snapshot())
g = compute_genre_stats(games)
print('top 3 genres by engagement:')
for row in g['genres'][:3]:
    print(' ', row['genre'], row['avg_engagement_ratio'], row['discovery_signal'][:40])
print('gaps:', [x['genre'] for x in compute_gap_analysis(games)['gaps']])
tp = compute_top_performers(games, 'breakout')
print('top breakout:', tp['games'][0]['name'] if tp['games'] else 'NONE')
"
```

Expected: real genre names (not `Unknown`), non-zero averages, at least one gap, a recognizable Roblox game name for top breakout. If the output is empty or all zeros, the merge between fetcher and signals is broken — check that `enrich_game_details` actually mutates records in `id_map` (which share identity with entries in the outer `games` list).

- [ ] **Step 5: Commit**

```bash
rtk git add data/fetcher.py
rtk git commit -m "feat: async HTTP pipeline for Rolimons + RoTunnel

Pulls top 300 games from Rolimons by active players, converts
placeIds to universeIds via RoTunnel with 50-way concurrency
(semaphore-limited), and enriches with game details in batches
of 100. Games that fail universeId conversion are silently
dropped per CLAUDE.md's graceful-degradation contract."
```

---

### Task 4: Implement server.py (FastMCP + cache)

**Files:**
- Create: `server.py`

- [ ] **Step 1: Create server.py**

File: `server.py`

```python
from fastmcp import FastMCP
from data.fetcher import get_market_snapshot
from data.signals import compute_genre_stats, compute_gap_analysis, compute_top_performers

mcp = FastMCP("Roblox Market Intelligence")

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

- [ ] **Step 2: Smoke-verify the server module imports cleanly**

```bash
python -c "
from server import mcp, get_cached_snapshot, _cache, CACHE_TTL
print('server name:', mcp.name)
print('CACHE_TTL:', CACHE_TTL)
print('cache starts empty:', _cache == {'data': None, 'timestamp': 0})
"
```

Expected: no ImportError, no AttributeError. Output includes `server name: Roblox Market Intelligence`, `CACHE_TTL: 600`, `cache starts empty: True`.

Failure diagnostics:
- `ImportError: cannot import name 'FastMCP' from 'fastmcp'`: FastMCP version mismatch. Confirm `pip show fastmcp` reports >= 3.2.0.
- `ModuleNotFoundError: No module named 'data'`: running from wrong cwd. Must run from repo root.

- [ ] **Step 3: Smoke-verify the cache behavior (cold vs warm)**

```bash
python -c "
import asyncio, time
from server import get_cached_snapshot, _cache
t0 = time.time(); s1 = asyncio.run(get_cached_snapshot()); t1 = time.time()
s2 = asyncio.run(get_cached_snapshot()); t2 = time.time()
print(f'cold: {t1-t0:.1f}s  warm: {(t2-t1)*1000:.1f}ms  identical: {s1 is s2}  size: {len(s1)}')
"
```

Expected: cold 10–30s, warm < 50ms, `identical: True`, `size` ≈ 300. If warm is slow or `identical: False`, the cache guard is broken — check the `_cache["data"] is None or time.time() - _cache["timestamp"] > CACHE_TTL` condition.

- [ ] **Step 4: Smoke-verify the server starts under STDIO transport**

```bash
python server.py
```

Expected: process starts silently and blocks waiting on stdin (STDIO MCP transport). No startup traceback. Send EOF (Ctrl+Z Enter on Windows, Ctrl+D on unix) or Ctrl+C to exit. Any exception printed before the block means the server will not register with Claude Code — fix before moving on.

- [ ] **Step 5: Commit**

```bash
rtk git add server.py
rtk git commit -m "feat: FastMCP server with four market-intelligence tools

Wires get_trending_genres, get_genre_analysis, get_gap_analysis,
and get_top_performers to a cached market snapshot. Docstrings
embed the RFY discovery-algorithm vocabulary so MCP clients
receive the interpretation framing as part of tool discovery.

In-memory cache with 10-minute TTL: cold start runs the full
Rolimons → RoTunnel pipeline (10-30s); subsequent tool calls
return instantly from the same snapshot."
```

---

### Task 5: End-to-end MCP client integration check

**Goal:** Confirm all four tools work inside Claude Code the way the demo script in CLAUDE.md expects. Manual verification — not automated.

**Files:** No code changes. Client config lives outside the repo.

- [ ] **Step 1: Add the server to Claude Code's MCP config**

Resolve the absolute path to `server.py`:
```bash
rtk git rev-parse --show-toplevel
```
Expected: `C:/Users/megas/Documents/GitHub/market-mcp` (or equivalent).

Edit Claude Code's MCP config (Windows path typically `%APPDATA%\Claude\claude_desktop_config.json`) to add:

```json
{
  "mcpServers": {
    "roblox-market": {
      "command": "python",
      "args": ["C:/Users/megas/Documents/GitHub/market-mcp/server.py"]
    }
  }
}
```

Restart Claude Code so the MCP server is re-discovered.

- [ ] **Step 2: Run the demo-script prompt and verify all four tools respond**

In a fresh Claude Code conversation:

```
Use the roblox-market MCP tools to research the Roblox market, then propose a game concept. Call get_trending_genres first, then get_gap_analysis, then get_genre_analysis on the most promising gap, then get_top_performers('breakout').
```

Expected:
- First tool call takes 10–30s (cold pipeline); subsequent calls feel instant.
- `get_trending_genres` returns ≥ 5 genre entries, each with `avg_engagement_ratio`, `discovery_signal` string, `top_game`.
- `get_gap_analysis` returns ≥ 1 gap with populated `demand_signal`, `quality_signal`, `opportunity`, `top_games`.
- `get_genre_analysis("<gap genre>")` returns a single genre summary — no `error` field.
- `get_top_performers("breakout")` returns 20 games sorted by `breakout_score` descending.
- Claude Code synthesizes a concrete game concept referencing specific genres, signal values, and design mechanics tied to the signal proxies.

- [ ] **Step 3: Verify the metric-validation error path**

In the same Claude Code conversation:

```
Call get_top_performers with metric "bogus"
```

Expected: tool returns `{"error": "Unknown metric 'bogus'", "valid_metrics": ["engagement", "sentiment", "breakout", "favorites"]}`. No Python traceback. Claude Code reports the error cleanly.

- [ ] **Step 4: Verify the unknown-genre error path**

```
Call get_genre_analysis with genre "zorkian"
```

Expected: tool returns `{"error": "No genre found matching 'zorkian'", "available": [ ...list of real genres... ]}`.

- [ ] **Step 5: Nothing to commit for this task**

The client config file is outside the repo. If any tool returned a traceback or malformed response, fix it in the relevant earlier task's module and add a follow-up commit there — do not create a config-only commit.

---

### Task 6: Implement data/wiki.py + analyze_game_design tool

**Why sixth:** Adds a second intelligence layer. Market data tells the agent *which genres to target*; wiki data tells it *how top games in those genres are designed* — economy structure, progression depth, monetization patterns — interpreted through the RFY algorithm lens.

**Files:**
- Create: `data/wiki.py`
- Update: `server.py` (add import + fifth tool)

- [ ] **Step 1: Create data/wiki.py**

Full implementation is in `docs/ARCHITECTURE.md` under `## data/wiki.py`. Key responsibilities:
- `_slug_candidates(game_name)` — generate Fandom subdomain patterns (hyphenated + no-separator)
- `_discover_fandom_wiki(client, game_name)` — probe slug candidates, return base URL or None
- `_TableParser` (HTMLParser subclass) — extract outermost tables, skip nested tables
- `_parse_tables(html)` — feed parser, return tables as nested lists
- `_table_to_records(table)` — first row = headers, rest = data dicts
- `_is_economy_table(records)` — keyword filter for cost/price/robux/coin/gem/etc.
- `_detect_currencies(records)` — match known Roblox currency patterns in table content
- `_build_algorithm_lens(currencies, item_count)` — interpret economy through RFY signal lens
- `analyze_game_wiki(game_name, wiki_url)` — main async entry point

- [ ] **Step 2: Update server.py to add the fifth tool**

Add import at top:
```python
from data.wiki import analyze_game_wiki
```

Add tool after `get_top_performers`:
```python
@mcp.tool
async def analyze_game_design(game_name: str, wiki_url: str = "") -> dict:
    """
    Scrapes a competitor game's public wiki to extract game design intelligence:
    economy structure (currencies, item costs), progression depth, and monetization
    patterns. Interprets findings through the RFY discovery algorithm lens —
    which design choices proxy well for QPTR, favorites rate, and 7-day play days.

    Use this BEFORE designing mechanics for a target genre. How top-performing
    games structure their economy reveals what keeps players returning daily —
    the core signal the algorithm rewards over raw player count.

    Roblox game wikis (typically at <gamename>.fandom.com) contain item tables,
    shop listings, and gamepass descriptions that expose the full progression
    design without needing Creator Dashboard access.

    Args:
        game_name: Roblox game name, e.g. "Blox Fruits", "Adopt Me", "Pet Simulator X"
        wiki_url: Optional base URL of the game's wiki, e.g. "https://bloxfruits.fandom.com".
                  Auto-discovered from game_name if omitted. Provide when auto-discovery fails.
    """
    return await analyze_game_wiki(game_name, wiki_url or None)
```

- [ ] **Step 3: Smoke-verify wiki discovery and table extraction**

```bash
python -c "
import asyncio
from data.wiki import analyze_game_wiki

# Test with a well-documented game (Blox Fruits has a large Fandom wiki)
result = asyncio.run(analyze_game_wiki('Blox Fruits'))
print('game:', result.get('game'))
print('wiki_source:', result.get('wiki_source'))
print('pages_fetched:', result.get('pages_fetched'))
print('currencies:', result.get('currencies_detected'))
print('items_found:', result.get('economy_items_found'))
print('algorithm_lens:', result.get('algorithm_lens', '')[:120])
print('sample_items count:', len(result.get('sample_items', [])))
"
```

Expected:
- `wiki_source` is `https://bloxfruits.fandom.com`
- `pages_fetched` ≥ 1
- `currencies_detected` includes Robux and/or Beli
- `economy_items_found` ≥ 1 (wiki table quality varies)
- `algorithm_lens` is a non-empty string with algorithm signal framing
- No Python traceback

If `wiki_source` is None or returns `error`: the slug auto-discovery probed the wrong URL. Test manually:
```bash
python -c "
import asyncio, httpx
async def test():
    async with httpx.AsyncClient(follow_redirects=True) as c:
        r = await c.get('https://bloxfruits.fandom.com/wiki/', timeout=8)
        print(r.status_code, str(r.url)[:80])
asyncio.run(test())
"
```
If status != 200 or URL doesn't contain "bloxfruits", the wiki may have moved. Try providing `wiki_url` directly to bypass auto-discovery.

- [ ] **Step 4: Smoke-verify unknown game returns clean error**

```bash
python -c "
import asyncio
from data.wiki import analyze_game_wiki
result = asyncio.run(analyze_game_wiki('Zorkian Destroyer 9000'))
print(result)
"
```

Expected: `{'error': \"No Fandom wiki found for 'Zorkian Destroyer 9000'.\", 'hint': '...'}` — no traceback.

- [ ] **Step 5: Smoke-verify tool wires correctly in server.py**

```bash
python -c "
from server import mcp
tools = [t.name for t in mcp._tool_manager.list_tools()]
print('tools:', tools)
assert 'analyze_game_design' in tools, 'tool not registered'
print('OK')
"
```

Expected: `tools` list contains all five tool names including `analyze_game_design`.

- [ ] **Step 6: Commit**

```bash
git add data/wiki.py server.py docs/ARCHITECTURE.md docs/SPEC.md docs/superpowers/plans/2026-04-18-roblox-market-intelligence-mcp.md
git commit -m "feat: wiki intelligence layer — analyze_game_design tool

Adds data/wiki.py: auto-discovers a game's Fandom wiki by probing
slug patterns, fetches up to 10 sub-pages (shop, items, gamepasses,
currency), extracts economy tables via stdlib html.parser (outermost
tables only — nested tables skipped to avoid nav pollution), detects
currency systems, and interprets economy structure through the RFY
algorithm lens.

New tool analyze_game_design() surfaces this as on-demand competitor
research. No cache needed (per-game, <5s). No new dependencies —
html.parser is stdlib.

Updates ARCHITECTURE.md, SPEC.md, and this plan file to document
the feature end-to-end."
```

---

## Self-Review Checklist

Run against the spec with fresh eyes:

- **Four tools from SPEC.md / CLAUDE.md** → defined in Task 4 server.py with matching docstrings. ✓
- **Signal proxies from CLAUDE.md signals table** (`engagement_ratio`, `like_ratio`, `favorites_rate`, `breakout_score`) → implemented in Task 2 `compute_signals`. ✓
- **Data pipeline (Rolimons → universeIds → game details) with top 300, concurrency 50, batch 100** → Task 3 `fetcher.py` constants `TOP_N`, `CONCURRENT`, `BATCH_SIZE`. ✓
- **Cache behavior (10-min TTL, cold/warm semantics)** → Task 4 `_cache` + `CACHE_TTL = 600`, smoke-tested in Task 4 Step 3. ✓
- **Gap criteria (avg_active > 1000, like_ratio < 0.80, engagement_ratio < 0.005)** → Task 2 `compute_gap_analysis`, verified in Task 2 Step 3 (Horror flagged, Survival not). ✓
- **Fuzzy genre matching (case-insensitive substring)** → Task 2 `compute_genre_stats`, error payload returned on miss. ✓
- **Metric validation (error + valid_metrics on unknown)** → Task 2 `compute_top_performers`, verified in Task 5 Step 3. ✓
- **Graceful degradation on RoTunnel failures** → Task 3 `enrich_universe_ids` and `enrich_game_details` swallow exceptions per game / per batch. ✓
- **Discovery-algorithm vocabulary baked into tool output** → Task 2 `ALGORITHM_SIGNALS` constant + `algorithm_context` strings returned with every payload; Task 4 tool docstrings. ✓
- **STDIO transport only, no HTTP server** → Task 4 `mcp.run()` default transport; no alternative wired. ✓
- **No tests, no DB, no auth, no rate-limiting middleware** → honored across all tasks, rationale stated up front. ✓
- **Demo script (2-min video path) runs end-to-end** → covered by Task 5 Step 2 prompt. ✓
- **Known limitations preserved** (unofficial RoTunnel proxy, coarse genre field, proxy signals not ground truth) → fetcher's silent-drop behavior, signals.py's "proxy for …" framing in ALGORITHM_SIGNALS and tool docstrings. ✓

Placeholder scan: no "TBD", no "TODO", no "implement later", no "add appropriate error handling", no "similar to Task N", no references to undefined identifiers. Type/name consistency: `get_market_snapshot`, `compute_signals`, `compute_genre_stats`, `compute_gap_analysis`, `compute_top_performers`, `get_cached_snapshot`, `_cache`, `CACHE_TTL` are named identically everywhere they appear.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-18-roblox-market-intelligence-mcp.md`.**

Two execution options:

1. **Subagent-Driven (recommended)** — Fresh subagent per task, two-stage review between tasks, fast iteration.
2. **Inline Execution** — Batch execution in this session with checkpoints for review.

Which approach do you want?

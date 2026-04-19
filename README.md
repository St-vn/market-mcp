# Roblox Market Intelligence MCP

> Give your coding agent market context before it builds. Live Roblox data interpreted through the lens of the discovery algorithm that drives organic growth.

Built for **MLH AI Hackfest** — 18-hour sprint.

---

## The Problem

Coding agents build Roblox games in a vacuum. They know how to write Luau, but not what the market rewards.

Roblox's **Recommended for You (RFY)** algorithm drives over 90% of organic discovery. It ranks games on six per-user signals:

| Signal | What it measures |
|--------|-----------------|
| QPTR | Qualified Play-Through Rate — impressions → intentional plays |
| Deep Engagement | Impressions → sustained sessions |
| 7-Day Playtime | Capped at 60 min/day — grind loops don't count |
| 7-Day Play Days | Return frequency |
| 7-Day Spend Days | Monetization signal |
| Co-Play Days | Friends playing together (added Dec 2025) |

Most developers don't optimize for these. Coding agents have no idea they exist.

---

## The Solution

An MCP server that delivers live market intelligence, framed around what actually drives algorithm distribution — directly into the agent's context window.

```
Rolimons gamelist (~6,600 games)
  → top 300 by active players
  → Roblox API: universe IDs, game details
  → signal proxies computed
  → cached for 10 minutes
```

The agent gets **market intelligence**, not raw numbers. Every output explains what signals are strong, where the gaps are, and why.

---

## Tools

### `get_trending_genres()`
Which genres is the algorithm currently favoring?

```json
{
  "genres": [
    {
      "genre": "Survival",
      "game_count": 18,
      "avg_engagement_ratio": 0.0091,
      "avg_like_ratio": 0.50,
      "avg_favorites_rate": 0.0038,
      "discovery_signal": "Strong — high engagement ratio suggests algorithm is actively distributing these games",
      "top_game": "The Survival Game"
    }
  ]
}
```

### `get_genre_analysis(genre)`
Deep breakdown of a genre through the discovery signal lens.

```json
{
  "genre": "Adventure",
  "game_count": 47,
  "signals": {
    "engagement_ratio": { "avg": 0.0072, "benchmark": "above" },
    "like_ratio": { "avg": 0.50, "benchmark": "average" },
    "favorites_rate": { "avg": 0.0031, "benchmark": "average" }
  },
  "breakout_games": ["Blox Fruits", "King Legacy"],
  "algorithm_read": "Adventure games show strong engagement proxies..."
}
```

### `get_gap_analysis()`
Where is demand strong but quality weak — room for a well-built entry?

```json
{
  "gaps": [
    {
      "genre": "Horror",
      "demand_signal": "high — 18 games in top 300, avg 4,200 active players",
      "quality_signal": "weak — avg like ratio 0.61, high variance",
      "opportunity": "Players want horror but current offerings don't retain them. Strong first-minute onboarding + social hooks would be algorithm-competitive.",
      "reference_games": ["Doors", "Piggy"]
    }
  ]
}
```

### `get_top_performers(metric)`
Top games ranked by a specific signal proxy. Metrics: `engagement`, `sentiment`, `breakout`, `favorites`.

```json
{
  "metric": "breakout",
  "description": "Games with highest engagement relative to their size — likely receiving current algorithm distribution",
  "games": [
    {
      "name": "The Survival Game",
      "genre": "Survival",
      "active_players": 38000,
      "engagement_ratio": 0.019,
      "breakout_score": 0.0048
    }
  ]
}
```

### `analyze_game_design(game_name, wiki_url?)`
Scrapes a competitor's public Fandom wiki to extract economy design, item costs, and progression patterns. Interprets through the algorithm lens.

```json
{
  "game": "Adopt Me",
  "wiki_source": "https://adoptme.fandom.com",
  "description": "Adopt Me! is a role-playing game where players can adopt and raise virtual pets...",
  "currencies_detected": [
    "Bucks (in-game currency)",
    "Robux (premium Roblox currency)"
  ],
  "economy_items_found": 340,
  "sample_items": [
    { "pet": "Dog", "rarity": "Common", "cost": "Free" },
    { "pet": "Neon Dragon", "rarity": "Legendary", "cost": "4x Dragon" }
  ],
  "algorithm_lens": "Dual-currency economy (Robux + Bucks grind): standard Roblox retention engine. In-game currency requires daily sessions (boosts 7-day play-days proxy). Rich item catalog (340+ items): depth of collectibles drives repeat-session motivation and favorites rate.",
  "pages_fetched": 7
}
```

---

## Signal Proxies

These are approximations derived from public data. The actual algorithm signals require Creator Dashboard access.

| Algorithm Signal | Public Proxy | Formula |
|-----------------|-------------|---------|
| QPTR | Like Ratio | upvotes / (upvotes + downvotes) |
| Deep Engagement | Favorites Rate | favorites / visits |
| Play Days / Playtime | Engagement Ratio | active_players / visits |
| New game growing | Breakout Score | engagement_ratio / log10(visits + 10) |

---

## Setup

**Requirements:** Python 3.11+

```bash
git clone https://github.com/St-vn/market-mcp
cd market-mcp
pip install fastmcp httpx
python server.py
```

**Claude Code** — drop `.mcp.json` in the repo root (already included):

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

Open the repo in Claude Code and the server registers automatically.

**First call is slow** (~30 seconds) — fetches 300 games and resolves universe IDs. All subsequent calls are instant (10-minute cache).

---

## Data Sources

- **[Rolimons](https://www.rolimons.com/)** — live game list with active player counts (~6,600 games)
- **Roblox APIs** — universe IDs, visits, favorites, genre metadata
- **Fandom wikis** — game economy data via MediaWiki API (no scraping, no Cloudflare)

No auth required. No paid APIs.

---

## Demo

```
User: Research the Roblox market and propose a game concept.

→ get_trending_genres()       # Adventure and Survival lead on engagement
→ get_gap_analysis()          # Horror: high demand, weak execution
→ get_genre_analysis("Horror") # Co-op mechanics correlate with top performers
→ analyze_game_design("Doors") # Dual-currency, 80+ items, heavy co-play design

Claude: "Build a co-op horror escape game. Dual-currency economy (daily grind +
        Robux cosmetics). Group-finding lobby to hit the Dec 2025 co-play signal.
        First-room onboarding under 90 seconds for QPTR. Here's the architecture..."
```

The agent makes informed decisions it couldn't make without the server.

---

## File Structure

```
market-mcp/
├── server.py          # FastMCP entry point, 5 tool definitions
├── data/
│   ├── fetcher.py     # Async HTTP pipeline: Rolimons → universeIds → game details
│   ├── signals.py     # Signal computation and genre aggregation
│   └── wiki.py        # Fandom wiki intelligence scraper
├── .mcp.json          # Claude Code auto-registration
└── docs/
    ├── SPEC.md        # Tool specifications and data pipeline docs
    └── ARCHITECTURE.md
```

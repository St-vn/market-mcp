# Roblox Market Intelligence MCP Server

> An MCP server that gives coding agents market intelligence about the Roblox platform — not just what's popular, but what the algorithm rewards and why.

## The Problem

Coding agents build Roblox games in a vacuum. They know how to write Luau but not what the market actually rewards. Without context, they optimize for code quality while missing the signals that determine whether a game ever gets seen by players.

Roblox's home page recommendation algorithm (Recommended for You, updated December 2025) determines organic growth. It surfaces games based on six per-user signals: qualified play-through rate, deep engagement, 7-day playtime, play days, spend, and intentional co-play. Games that satisfy these signals get distributed. Games that don't, plateau.

The problem is that most developers don't understand which genres and design patterns naturally satisfy those signals — and coding agents have no idea at all.

## The Solution

This MCP server bridges market reality into the agent's context window before it starts building. It combines:

- **Live market data** — active players, visits, like ratios, favorites (Rolimons + Roblox API)
- **Derived signals** — engagement ratio, like quality, breakout score, favorites rate
- **Discovery algorithm knowledge** — Roblox's documented algorithm signals baked into how data is interpreted and presented

The agent doesn't get raw numbers. It gets market intelligence framed around what actually drives organic growth on Roblox.

## Tools

| Tool | What it answers |
|------|----------------|
| `get_trending_genres()` | Which genres are the algorithm currently favoring based on engagement signals? |
| `get_genre_analysis(genre)` | What does this genre look like through the lens of discovery signals? |
| `get_gap_analysis()` | Where is there demand but weak execution — room for a well-built entry? |
| `get_top_performers(metric)` | Which games lead on a specific signal proxy? |

## Stack

- **Python 3.11+** with FastMCP (STDIO transport)
- **httpx** for async HTTP
- **Rolimons API** for live game list with player counts
- **Roblox game detail API** (via RoTunnel proxy) for visits, ratings, favorites
- No auth required, no paid APIs

## Setup

```bash
pip install fastmcp httpx
python server.py
```

Claude Code config (`claude_desktop_config.json`):
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

## Hackathon

Built for MLH AI Hackfest. 18-hour sprint. Public repo required for submission.

The vision extends beyond the MVP: a multi-platform context pipeline that gives any coding agent market intelligence before it builds — Roblox today, Steam and mobile tomorrow.

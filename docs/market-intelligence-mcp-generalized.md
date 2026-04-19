# Market Intelligence MCP Server — Generalized Idea

## The Core Pattern

Coding agents build software in a vacuum. They know how to write code but not what the market actually rewards. The missing piece is a data pipeline from marketplace reality into the agent's context window before it starts building.

```
Marketplace data (what works)
        ↓
MCP server (structured context)
        ↓
Coding agent (builds informed by market)
        ↓
Software that fits the market
```

This pattern applies to any domain with a marketplace and a coding agent building for it.

## Domain Examples

| Domain | Data Source | What Agent Learns |
|--------|-------------|-------------------|
| Roblox games | CreatorExchange, Rolimons, RoLearn | Trending genres, revenue per visit, breakout signals |
| Mobile apps | App Store rankings, review sentiment | What features users want, what's oversaturated |
| SaaS tools | Product Hunt, G2, AppSumo | Feature gaps, pricing patterns, unmet demand |
| Web games | itch.io, Steam, Newgrounds | Genre trends, jam themes, monetization patterns |
| Chrome extensions | Chrome Web Store | Category gaps, user pain points |
| VS Code extensions | Marketplace stats | Developer workflow gaps |

## Why This Is Different from Existing Market Data MCPs

Market data MCP servers already exist — Alpha Vantage, TradingView, Semrush, CryptoRank. But they all serve a different purpose: analysis and trading decisions, or marketing and SEO workflows.

None are positioned to inform *what software to build*. The use case is:

**Existing:** market data → investment or marketing decision  
**This idea:** market data → software product decision → coding agent builds it

The agent isn't trading or marketing. It's building. The market context tells it what to build, not how to trade.

## The Two Highest-Signal Data Categories

Not all external data is equally useful to a coding agent. Two categories stand out:

**Communication data** — what teams are deciding, discussing, and needing. Discord, Teams, Telegram. Tells the agent what humans want built.

**Market intelligence** — what's performing, trending, and selling in the relevant marketplace. Tells the agent what the market rewards.

Everything else (weather, financial data, sports scores) is useful for analysis or automation but doesn't close the loop on *what to build*.

## What an MCP Server in This Pattern Exposes

Generic tool shapes that apply across domains:

- `get_trending(category?)` — what's gaining momentum right now
- `get_saturated(category?)` — what's overcrowded and declining
- `get_top_performers(metric)` — what's performing best by a given metric
- `get_gap_analysis()` — underserved categories with demand but little supply
- `get_benchmarks(category)` — average performance metrics to calibrate expectations

## Building One

The pattern for building a market intelligence MCP server in any domain:

1. **Identify the marketplace** — where does the target software get discovered and used?
2. **Find accessible data** — public APIs, documented scraping-friendly sources, partnerships
3. **Define the signals that matter** — requires domain expertise; raw data is not insight
4. **Expose structured tools** — designed for agent consumption, not human dashboards
5. **Position in the workflow** — before the coding agent starts, not during

## The Moat

The data is often public. The moat is knowing which signals actually predict success in a specific domain. That requires domain expertise that generic data providers don't have. A Roblox game developer knows that revenue per visit matters more than raw player count. A mobile developer knows that Day 7 retention is the signal that predicts long-term success. That judgment is what makes the MCP server useful rather than noisy.

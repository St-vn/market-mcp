from fastmcp import FastMCP
from data.fetcher import get_market_snapshot
from data.signals import compute_genre_stats, compute_gap_analysis, compute_top_performers
from data.wiki import analyze_game_wiki

mcp = FastMCP("Roblox Market Intelligence")

# In-memory cache shared by all market-data tools
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


if __name__ == "__main__":
    mcp.run()  # STDIO transport, works directly with Claude Code

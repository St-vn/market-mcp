import os
import base64
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


@mcp.tool
async def analyze_thumbnail(universe_id: str) -> dict:
    """
    Fetches a Roblox game's thumbnail and uses Google Gemini Vision to score
    its click appeal and genre clarity — both strong proxies for QPTR (qualified
    play-through rate), since poor thumbnails suppress click-through before
    the algorithm can even measure session quality.

    Requires GOOGLE_AI_KEY environment variable.

    Args:
        universe_id: The Roblox universe ID of the game (not place ID).
                     Find it at: roblox.com/games/<universeId>
    """
    api_key = os.environ.get("GOOGLE_AI_KEY")
    if not api_key:
        return {
            "error": "GOOGLE_AI_KEY environment variable not set.",
            "hint": "Set it with: export GOOGLE_AI_KEY=your_key_here",
        }

    from data.fetcher import fetch_thumbnail
    image_bytes = await fetch_thumbnail(universe_id)
    if not image_bytes:
        return {
            "error": f"Could not fetch thumbnail for universe_id={universe_id}.",
            "hint": "Verify the universe_id is correct (not place_id).",
        }

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        image_part = {
            "inline_data": {
                "mime_type": "image/png",
                "data": base64.b64encode(image_bytes).decode("utf-8"),
            }
        }
        prompt = (
            "You are analyzing a Roblox game thumbnail for market intelligence.\n\n"
            "Score and explain the following (be specific and concise):\n"
            "1. QPTR likelihood (1-10): How likely is a player to click AND stay after seeing this thumbnail?\n"
            "2. Genre clarity (1-10): How clearly does the thumbnail signal what genre/gameplay this is?\n"
            "3. Visual appeal (1-10): Color contrast, composition, character readability at small size.\n"
            "4. Key strengths: What works (max 2 bullet points).\n"
            "5. Key weaknesses: What hurts click-through (max 2 bullet points).\n"
            "6. Algorithm lens: How does this thumbnail likely affect the game's QPTR signal in Roblox's discovery algorithm?\n\n"
            "Return a JSON object with keys: qptr_score, genre_clarity_score, visual_appeal_score, "
            "strengths (list), weaknesses (list), algorithm_lens (string)."
        )

        response = model.generate_content([prompt, image_part])
        raw = response.text.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        import json
        analysis = json.loads(raw)
        analysis["universe_id"] = universe_id
        analysis["thumbnail_analyzed"] = True
        return analysis

    except Exception as e:
        return {
            "error": f"Gemini analysis failed: {str(e)}",
            "universe_id": universe_id,
        }


if __name__ == "__main__":
    mcp.run()  # STDIO transport, works directly with Claude Code

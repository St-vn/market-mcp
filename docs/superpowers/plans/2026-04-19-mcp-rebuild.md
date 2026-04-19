# MCP Server Rebuild Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Roblox Market Intelligence MCP server with a fixed data pipeline (Rolimons Cloudflare bypass, native Roblox universe API), and add a new `analyze_thumbnail` tool using Google Gemini Vision.

**Architecture:** Rolimons (6,600 games, needs Referer header) → top 300 by active players → native Roblox universe API (place→universe) → Roblox games API (details) → signals.py (pure computation). New thumbnail tool fetches game icon from Roblox thumbnail API and passes to Gemini 2.0 Flash for click-appeal scoring. All five market tools share a 10-minute in-memory cache; thumbnail tool is on-demand.

**Tech Stack:** Python 3.13, FastMCP ≥3.2.0, httpx ≥0.27.0, beautifulsoup4 ≥4.12.0, google-generativeai ≥0.5.0

---

## Chunk 1: Dependencies + Fetcher Fix

### Task 1: Update requirements.txt

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Update requirements.txt**

Replace current contents with:
```
fastmcp>=3.2.0
httpx>=0.27.0
beautifulsoup4>=4.12.0
google-generativeai>=0.5.0
```

- [ ] **Step 2: Install and verify**

```bash
pip install -r requirements.txt
python -c "import fastmcp, httpx, bs4, google.generativeai; print('all imports OK')"
```
Expected: `all imports OK`

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add beautifulsoup4 and google-generativeai dependencies"
```

---

### Task 2: Fix fetcher.py — Rolimons Cloudflare bypass + rate-limit fix

**Problem:** Rolimons requires `Referer: https://www.rolimons.com/` header or returns 403. The existing fetcher has this missing. The universe enrichment also batches in groups of 50 with 6s sleep between batches — this is too slow for 300 games (~36 seconds just waiting). Replace with semaphore-based concurrency (limit 20 concurrent) which is faster and doesn't need sleep.

**Files:**
- Modify: `data/fetcher.py`

- [ ] **Step 1: Replace HEADERS constant**

In `data/fetcher.py`, replace:
```python
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}
```
With:
```python
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.rolimons.com/",
    "Origin": "https://www.rolimons.com",
}
```

- [ ] **Step 2: Replace enrich_universe_ids with semaphore-based version**

Replace the entire `enrich_universe_ids` function:
```python
async def enrich_universe_ids(client: httpx.AsyncClient, games: list[dict]) -> list[dict]:
    sem = asyncio.Semaphore(CONCURRENT)

    async def fetch_one(game):
        async with sem:
            try:
                url = ROBLOX_UNIVERSE.format(place_id=game["place_id"])
                resp = await client.get(url)
                if resp.status_code == 200:
                    game["universe_id"] = str(resp.json()["universeId"])
            except Exception:
                pass
        return game

    await asyncio.gather(*[fetch_one(g) for g in games])
    return games
```

- [ ] **Step 3: Smoke test fetcher end-to-end**

```bash
python -c "
import asyncio
from data.fetcher import get_market_snapshot
async def main():
    snap = await get_market_snapshot()
    print(f'Games returned: {len(snap)}')
    print(f'Sample: {snap[0]}')
asyncio.run(main())
"
```
Expected: `Games returned: <number between 150-300>`, sample has `name`, `active_players`, `visits`, `genre`, `universe_id` keys.

- [ ] **Step 4: Commit**

```bash
git add data/fetcher.py
git commit -m "fix: Rolimons Cloudflare bypass headers + semaphore-based universe enrichment"
```

---

## Chunk 2: Signals + Genre Monetization Flag

### Task 3: Add monetization_presence signal to signals.py

**Context:** The spec requires `get_trending_genres()` to include monetization presence (whether games in the genre show monetization signals). The current `signals.py` has no monetization flag. We add a simple heuristic: if a game has favorites > 10,000 AND visits > 1M, mark `has_strong_monetization_signal = True` (proxy: high favorites relative to visits correlates with game health/monetization).

**Files:**
- Modify: `data/signals.py`

- [ ] **Step 1: Add monetization flag to compute_signals**

In `compute_signals`, after the `breakout_score` line, add:
```python
    has_strong_monetization_signal = favorites > 10_000 and visits > 1_000_000
```

And in the return dict, add:
```python
        "has_strong_monetization_signal": has_strong_monetization_signal,
```

- [ ] **Step 2: Add monetization_presence to genre_summary**

In `genre_summary`, after the `top_game` line, add:
```python
    monetization_count = sum(1 for g in games if g.get("has_strong_monetization_signal", False))
    monetization_presence = f"{monetization_count}/{len(games)} games show strong monetization signals"
```

And add to the return dict:
```python
        "monetization_presence": monetization_presence,
```

- [ ] **Step 3: Verify signals compute correctly with mock data**

```bash
python -c "
from data.signals import compute_signals, genre_summary

mock_games = [
    {'name': 'A', 'active_players': 5000, 'visits': 1_500_000, 'favorites': 50_000, 'upvotes': 8000, 'downvotes': 1000, 'genre': 'RPG'},
    {'name': 'B', 'active_players': 800, 'visits': 200_000, 'favorites': 3000, 'upvotes': 500, 'downvotes': 200, 'genre': 'RPG'},
]
enriched = [compute_signals(g) for g in mock_games]
print('engagement_ratio A:', enriched[0]['engagement_ratio'])
print('monetization A:', enriched[0]['has_strong_monetization_signal'])
print('monetization B:', enriched[1]['has_strong_monetization_signal'])
summary = genre_summary('RPG', enriched)
print('monetization_presence:', summary['monetization_presence'])
"
```
Expected:
- `engagement_ratio A: 0.003333` (5000/1500000)
- `monetization A: True`
- `monetization B: False`
- `monetization_presence: 1/2 games show strong monetization signals`

- [ ] **Step 4: Commit**

```bash
git add data/signals.py
git commit -m "feat: add monetization_presence signal to genre summaries"
```

---

## Chunk 3: Thumbnail Tool

### Task 4: Add analyze_thumbnail tool to server.py

**Context:** New tool fetches a game's thumbnail from `https://thumbnails.roblox.com/v1/games/icons?universeIds={id}&size=512x512&format=Png`, downloads the image bytes, then passes them to Gemini 2.0 Flash Vision for click-appeal analysis. The `GOOGLE_AI_KEY` env var must be set. If it's missing, return a helpful error dict — never raise.

**Files:**
- Modify: `server.py`
- Modify: `data/fetcher.py` (add `fetch_thumbnail` helper)

- [ ] **Step 1: Add fetch_thumbnail helper to fetcher.py**

At the bottom of `data/fetcher.py`, add:
```python
ROBLOX_THUMBNAILS = "https://thumbnails.roblox.com/v1/games/icons"

async def fetch_thumbnail(universe_id: str) -> bytes | None:
    """Fetches the 512x512 PNG thumbnail for a universe. Returns raw bytes or None."""
    async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
        try:
            params = {"universeIds": universe_id, "size": "512x512", "format": "Png"}
            r = await client.get(ROBLOX_THUMBNAILS, params=params)
            if r.status_code != 200:
                return None
            data = r.json()
            image_url = data["data"][0].get("imageUrl")
            if not image_url:
                return None
            img_r = await client.get(image_url)
            return img_r.content if img_r.status_code == 200 else None
        except Exception:
            return None
```

- [ ] **Step 2: Add analyze_thumbnail tool to server.py**

Add this import at the top of `server.py`:
```python
import os
import base64
```

Add this tool after `analyze_game_design`:
```python
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
```

- [ ] **Step 3: Test thumbnail fetch (no Gemini key needed)**

```bash
python -c "
import asyncio
from data.fetcher import fetch_thumbnail
async def main():
    # universe_id for Blox Fruits
    img = await fetch_thumbnail('2753915549')
    print('Thumbnail bytes:', len(img) if img else 'FAILED')
asyncio.run(main())
"
```
Expected: `Thumbnail bytes: <number > 10000>`

- [ ] **Step 4: Test full tool (requires GOOGLE_AI_KEY)**

If `GOOGLE_AI_KEY` is set:
```bash
python -c "
import asyncio, os
# Verify key is present
print('Key set:', bool(os.environ.get('GOOGLE_AI_KEY')))
"
```
If key is present, run server and call tool via MCP client. Otherwise, verify the missing-key error path:
```bash
python -c "
import asyncio, os
os.environ.pop('GOOGLE_AI_KEY', None)
# Import server after unsetting key
import importlib, sys
# Run tool directly
from server import analyze_thumbnail
result = asyncio.run(analyze_thumbnail('2753915549'))
print(result)
"
```
Expected: `{'error': 'GOOGLE_AI_KEY environment variable not set.', 'hint': ...}`

- [ ] **Step 5: Commit**

```bash
git add data/fetcher.py server.py
git commit -m "feat: add analyze_thumbnail tool with Gemini Vision scoring"
```

---

## Chunk 4: Server Smoke Test + README

### Task 5: End-to-end server smoke test

**Files:**
- Read: `server.py`

- [ ] **Step 1: Verify server starts without error**

```bash
python -c "
import server
print('Server loaded OK, tools:', [t.name for t in server.mcp._tools.values()])
"
```
Expected output includes all 6 tool names: `get_trending_genres`, `get_genre_analysis`, `get_gap_analysis`, `get_top_performers`, `analyze_game_design`, `analyze_thumbnail`.

- [ ] **Step 2: Verify cache pipeline runs**

```bash
python -c "
import asyncio
from server import get_cached_snapshot
async def main():
    snap = await get_cached_snapshot()
    print(f'Snapshot size: {len(snap)}')
    print(f'Sample keys: {list(snap[0].keys())}')
asyncio.run(main())
"
```
Expected: `Snapshot size: >100`, sample has `name`, `visits`, `genre`, `engagement_ratio` etc.

- [ ] **Step 3: Verify all signal tools return non-empty data**

```bash
python -c "
import asyncio
from server import get_trending_genres, get_top_performers, get_gap_analysis

async def main():
    genres = await get_trending_genres()
    print('Trending genres count:', len(genres.get('genres', [])))
    top = await get_top_performers('breakout')
    print('Top breakout count:', len(top.get('games', [])))
    gaps = await get_gap_analysis()
    print('Gaps found:', len(gaps.get('gaps', [])))

asyncio.run(main())
"
```
Expected: all counts > 0.

- [ ] **Step 4: Commit**

```bash
git add .
git commit -m "chore: verified end-to-end server smoke test passes"
```

---

### Task 6: Update .mcp.json for new server path

**Files:**
- Modify: `.mcp.json`

- [ ] **Step 1: Check current .mcp.json**

```bash
cat .mcp.json
```

- [ ] **Step 2: Verify server command path is correct**

The `.mcp.json` should point to `server.py` in the project root with an absolute path. If the path is wrong, update it:
```json
{
  "mcpServers": {
    "roblox-market": {
      "command": "python",
      "args": ["C:/Users/megas/Documents/GitHub/market-mcp/server.py"],
      "env": {
        "GOOGLE_AI_KEY": ""
      }
    }
  }
}
```
Fill in `GOOGLE_AI_KEY` value if available.

- [ ] **Step 3: Commit**

```bash
git add .mcp.json
git commit -m "chore: update .mcp.json with GOOGLE_AI_KEY env placeholder"
```

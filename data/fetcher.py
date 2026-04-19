import httpx
import asyncio

ROLIMONS_GAMELIST = "https://api.rolimons.com/games/v1/gamelist"
ROBLOX_UNIVERSE = "https://apis.roblox.com/universes/v1/places/{place_id}/universe"
ROBLOX_GAMES = "https://games.roblox.com/v1/games"

TOP_N = 300          # Games to pull from Rolimons by player count
BATCH_SIZE = 50      # Roblox game detail API limit per request (max 50 universeIds)
CONCURRENT = 1       # Serial universe ID lookups — Roblox rate-limits at 60/60s

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.rolimons.com/",
    "Origin": "https://www.rolimons.com",
}

async def get_market_snapshot() -> list[dict]:
    """Full pipeline: Rolimons → universeIds → game details → merged records"""
    async with httpx.AsyncClient(timeout=30, headers=HEADERS) as client:
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
                url = ROBLOX_UNIVERSE.format(place_id=game["place_id"])
                resp = await client.get(url)
                if resp.status_code == 200:
                    game["universe_id"] = str(resp.json()["universeId"])
                elif resp.status_code == 429:
                    await asyncio.sleep(2)
                    resp2 = await client.get(url)
                    if resp2.status_code == 200:
                        game["universe_id"] = str(resp2.json()["universeId"])
            except Exception:
                pass
            await asyncio.sleep(1.0)
        return game

    await asyncio.gather(*[fetch_one(g) for g in games])
    return games

async def enrich_game_details(client: httpx.AsyncClient, games: list[dict]) -> list[dict]:
    with_ids = [g for g in games if "universe_id" in g]
    id_map = {g["universe_id"]: g for g in with_ids}

    universe_ids = list(id_map.keys())
    batches = [universe_ids[i:i+BATCH_SIZE] for i in range(0, len(universe_ids), BATCH_SIZE)]

    for batch in batches:
        try:
            params = {"universeIds": ",".join(batch)}
            resp = await client.get(ROBLOX_GAMES, params=params)
            if resp.status_code != 200:
                continue

            for detail in resp.json().get("data", []):
                uid = str(detail["id"])
                if uid in id_map:
                    # genre_l1 is the specific genre (e.g. "Adventure") vs. genre which
                    # is often "All". Fall back to genre if genre_l1 is unavailable.
                    genre = detail.get("genre_l1") or detail.get("genre", "Unknown")
                    id_map[uid].update({
                        "visits": detail.get("visits", 0),
                        "favorites": detail.get("favoritedCount", 0),
                        "genre": genre,
                        "created": detail.get("created", ""),
                        "updated": detail.get("updated", ""),
                        # Note: Roblox removed totalUpVotes/totalDownVotes from the public
                        # API. like_ratio will default to 0.5 (neutral) in signals.py.
                    })
        except Exception:
            continue

    return games

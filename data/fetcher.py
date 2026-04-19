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
                pass  # Skip games where conversion fails
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

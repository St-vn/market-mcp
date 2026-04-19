"""
Data source verification. Run this before building anything.
Tests: Roblox charts pages, games API, Rolimons fallback.
"""
import asyncio
import httpx

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/json,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

TEST_UNIVERSE_IDS = "606849621,4924922222"


async def test_roblox_chart(client: httpx.AsyncClient, path: str) -> dict:
    url = f"https://www.roblox.com{path}"
    try:
        r = await client.get(url, headers=HEADERS, follow_redirects=True, timeout=15)
        html = r.text
        # Check if JS-rendered (no useful data) or has real content
        has_game_data = "game-card" in html or "data-universe" in html or "universeId" in html or '"gameId"' in html
        has_react_root = "react-app" in html or "__NEXT_DATA__" in html or "window.RobloxGlobals" in html
        snippet = html[:500].replace("\n", " ").strip()
        return {
            "url": url,
            "status": r.status_code,
            "has_game_data": has_game_data,
            "is_js_rendered": has_react_root and not has_game_data,
            "content_length": len(html),
            "snippet": snippet,
        }
    except Exception as e:
        return {"url": url, "error": str(e)}


async def test_games_api(client: httpx.AsyncClient) -> dict:
    url = f"https://games.roblox.com/v1/games?universeIds={TEST_UNIVERSE_IDS}"
    try:
        r = await client.get(url, headers=HEADERS, timeout=15)
        data = r.json() if r.status_code == 200 else None
        return {
            "url": url,
            "status": r.status_code,
            "game_count": len(data.get("data", [])) if data else 0,
            "sample": data["data"][0] if data and data.get("data") else None,
        }
    except Exception as e:
        return {"url": url, "error": str(e)}


async def test_rolimons(client: httpx.AsyncClient) -> dict:
    url = "https://api.rolimons.com/games/v1/gamelist"
    try:
        r = await client.get(url, headers=HEADERS, timeout=20)
        data = r.json() if r.status_code == 200 else None
        game_count = 0
        sample = None
        if data and "games" in data:
            games = data["games"]
            game_count = len(games)
            # games is a dict: {place_id: [name, active_players, ...]}
            first_key = next(iter(games))
            sample = {first_key: games[first_key]}
        return {
            "url": url,
            "status": r.status_code,
            "game_count": game_count,
            "sample": sample,
        }
    except Exception as e:
        return {"url": url, "error": str(e)}


async def test_rotunnel_universe(client: httpx.AsyncClient) -> dict:
    # Test place -> universe conversion via rotunnel proxy
    url = "https://apis.rotunnel.com/universes/v1/places/606849621/universe"
    try:
        r = await client.get(url, headers=HEADERS, timeout=15)
        return {
            "url": url,
            "status": r.status_code,
            "body": r.text[:300],
        }
    except Exception as e:
        return {"url": url, "error": str(e)}


async def test_thumbnail_api(client: httpx.AsyncClient) -> dict:
    url = "https://thumbnails.roblox.com/v1/games/icons?universeIds=606849621&size=512x512&format=Png"
    try:
        r = await client.get(url, headers=HEADERS, timeout=15)
        data = r.json() if r.status_code == 200 else None
        return {
            "url": url,
            "status": r.status_code,
            "thumbnail_url": data["data"][0].get("imageUrl") if data and data.get("data") else None,
        }
    except Exception as e:
        return {"url": url, "error": str(e)}


def print_result(label: str, result: dict):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    for k, v in result.items():
        if k == "sample" and v:
            print(f"  {k}:")
            if isinstance(v, dict):
                for sk, sv in list(v.items())[:3]:
                    print(f"    {sk}: {sv}")
            else:
                print(f"    {str(v)[:300]}")
        elif k == "snippet":
            print(f"  {k}: {str(v)[:200]}")
        else:
            print(f"  {k}: {v}")


async def main():
    print("Testing all data sources...\n")
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            test_roblox_chart(client, "/charts/top-playing-now"),
            test_roblox_chart(client, "/charts/top-earning"),
            test_roblox_chart(client, "/charts/up-and-coming"),
            test_games_api(client),
            test_rolimons(client),
            test_rotunnel_universe(client),
            test_thumbnail_api(client),
        )

    labels = [
        "Roblox Charts: top-playing-now",
        "Roblox Charts: top-earning",
        "Roblox Charts: up-and-coming",
        "Roblox Games API",
        "Rolimons gamelist",
        "RoTunnel universe conversion",
        "Roblox Thumbnail API",
    ]

    for label, result in zip(labels, results):
        print_result(label, result)

    print("\n\n=== SUMMARY ===")
    chart_results = results[:3]
    js_rendered = [r for r in chart_results if r.get("is_js_rendered")]
    has_data = [r for r in chart_results if r.get("has_game_data")]
    print(f"Charts JS-rendered (no useful HTML): {len(js_rendered)}/3")
    print(f"Charts with game data in HTML:       {len(has_data)}/3")
    print(f"Games API works:    {'YES' if results[3].get('game_count', 0) > 0 else 'NO'}")
    print(f"Rolimons works:     {'YES' if results[4].get('game_count', 0) > 0 else 'NO'}")
    print(f"RoTunnel works:     {'YES' if results[5].get('status') == 200 else 'NO - status: ' + str(results[5].get('status', 'ERR'))}")
    print(f"Thumbnail API works:{'YES' if results[6].get('thumbnail_url') else 'NO'}")

    print("\n=== RECOMMENDATION ===")
    if js_rendered:
        print("Roblox charts are JS-rendered. Fall back to Rolimons for game list.")
    if results[4].get('game_count', 0) > 0:
        print(f"Rolimons has {results[4]['game_count']} games — use as primary source.")
    if results[3].get('game_count', 0) > 0:
        print("Roblox Games API confirmed working — use for game details.")


if __name__ == "__main__":
    asyncio.run(main())

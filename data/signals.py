import math
from collections import defaultdict

# Discovery algorithm context baked in as constants
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

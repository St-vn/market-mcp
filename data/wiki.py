"""
data/wiki.py — Roblox game wiki intelligence scraper

Fetches a game's public Fandom wiki and extracts design intelligence:
economy structure (currencies, item costs), progression depth, and
monetization patterns. Interprets findings through the RFY algorithm lens.

Data source: public Fandom wikis (e.g. bloxfruits.fandom.com).
No additional dependencies — uses stdlib html.parser for table extraction.
"""

import re
import httpx
from html.parser import HTMLParser

# Fandom is the dominant wiki platform for Roblox games
FANDOM_BASE = "https://{slug}.fandom.com"

# Sub-pages to probe per wiki — ordered from most to least likely to have economy data
WIKI_SUB_PAGES = [
    "/wiki/",
    "/wiki/Main_Page",
    "/wiki/Gamepasses",
    "/wiki/Game_Pass",
    "/wiki/Shop",
    "/wiki/Items",
    "/wiki/Currency",
    "/wiki/Currencies",
    "/wiki/Store",
    "/wiki/Products",
]

# Regex keywords that identify economy-relevant table content
ECONOMY_KEYWORDS = [
    r"cost", r"price", r"robux", r"\br\$", r"beli", r"\bcoin", r"\bgem",
    r"\bgold\b", r"\bcash\b", r"\btoken", r"\bbuck", r"credit",
]

# Currency detection patterns mapped to human-readable labels
CURRENCY_PATTERNS = [
    (r"robux|r\$",    "Robux (premium Roblox currency)"),
    (r"\bbeli\b",     "Beli (in-game currency)"),
    (r"\bcoin",       "Coins (in-game currency)"),
    (r"\bgem",        "Gems (premium in-game currency)"),
    (r"\bgold\b",     "Gold (in-game currency)"),
    (r"\bcash\b",     "Cash (in-game currency)"),
    (r"\btoken",      "Tokens (special currency)"),
    (r"\bbuck",       "Bucks (in-game currency)"),
    (r"\bcredit",     "Credits (in-game currency)"),
]


# ---------------------------------------------------------------------------
# HTML table extraction (stdlib only, no BeautifulSoup)
# ---------------------------------------------------------------------------

class _TableParser(HTMLParser):
    """Streaming HTML parser that extracts outermost tables as row lists.

    Nested tables are skipped — inner depth tracking prevents nav/infobox
    content from polluting item table rows.
    """

    def __init__(self):
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] = []
        self._row: list[str] = []
        self._cell: list[str] = []
        self._table_depth = 0
        self._in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._table_depth += 1
            if self._table_depth == 1:
                self._table = []
        elif tag == "tr" and self._table_depth == 1:
            self._row = []
        elif tag in ("td", "th") and self._table_depth == 1:
            self._in_cell = True
            self._cell = []

    def handle_endtag(self, tag):
        if tag == "table":
            if self._table_depth == 1 and self._table:
                self.tables.append([r for r in self._table if r])
            self._table_depth = max(0, self._table_depth - 1)
        elif tag == "tr" and self._table_depth == 1:
            if self._row:
                self._table.append(self._row[:])
        elif tag in ("td", "th") and self._table_depth == 1 and self._in_cell:
            self._row.append(" ".join(self._cell).strip())
            self._in_cell = False

    def handle_data(self, data):
        if self._in_cell and self._table_depth == 1:
            stripped = data.strip()
            if stripped:
                self._cell.append(stripped)


def _parse_tables(html: str) -> list[list[list[str]]]:
    """Return all outermost tables from an HTML string as nested lists of rows."""
    parser = _TableParser()
    try:
        parser.feed(html)
    except Exception:
        pass
    return parser.tables


def _table_to_records(table: list[list[str]]) -> list[dict]:
    """Convert a table (list of rows) into dicts using the first row as headers."""
    if len(table) < 2:
        return []
    headers = [h.lower().strip()[:50] for h in table[0]]
    if not any(headers):
        return []
    records = []
    for row in table[1:]:
        if not any(v.strip() for v in row):
            continue
        # Pad or trim row to match header count
        padded = (row + [""] * len(headers))[:len(headers)]
        records.append(dict(zip(headers, padded)))
    return records


def _is_economy_table(records: list[dict]) -> bool:
    """Return True if a table appears to contain item cost/price data."""
    if not records:
        return False
    # Sample first 3 rows of both keys and values for keyword matching
    sample = " ".join(
        f"{k} {v}" for r in records[:3] for k, v in r.items()
    ).lower()
    return any(re.search(kw, sample) for kw in ECONOMY_KEYWORDS)


# ---------------------------------------------------------------------------
# Wiki discovery + page fetching
# ---------------------------------------------------------------------------

def _slug_candidates(game_name: str) -> list[str]:
    """Generate Fandom subdomain slug candidates from a game name.

    Examples:
        "Blox Fruits"      → ["blox-fruits", "bloxfruits"]
        "Adopt Me!"        → ["adopt-me", "adoptme"]
        "Pet Simulator X"  → ["pet-simulator-x", "petsimulatorx"]
    """
    name = game_name.strip()
    candidates = [
        re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"),  # hyphenated
        re.sub(r"[^a-z0-9]", "", name.lower()),               # no separator
    ]
    # Deduplicate while preserving order
    seen: set[str] = set()
    return [s for s in candidates if s and not (s in seen or seen.add(s))]


async def _discover_fandom_wiki(client: httpx.AsyncClient, game_name: str) -> str | None:
    """Probe Fandom subdomain patterns to find a game's wiki base URL.

    Returns the base URL (e.g. "https://bloxfruits.fandom.com") on success,
    or None if no wiki is found. Failed probes are silently dropped.
    """
    for slug in _slug_candidates(game_name):
        url = FANDOM_BASE.format(slug=slug) + "/wiki/"
        try:
            resp = await client.get(url, timeout=8)
            # Fandom redirects non-existent wikis to www.fandom.com/search —
            # verify the slug is still present in the final URL
            if resp.status_code == 200 and slug in str(resp.url):
                return FANDOM_BASE.format(slug=slug)
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# Post-processing: currencies, insights
# ---------------------------------------------------------------------------

def _extract_lead_text(html: str) -> str:
    """Pull the first substantial paragraph from article HTML, tags stripped."""
    for match in re.finditer(r"<p[^>]*>(.*?)</p>", html, re.DOTALL | re.IGNORECASE):
        text = re.sub(r"<[^>]+>", "", match.group(1))
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > 60:
            return text[:600]
    return ""


def _detect_currencies(records: list[dict]) -> list[str]:
    """Scan economy table content for known Roblox currency keywords."""
    combined = " ".join(
        f"{k} {v}" for r in records for k, v in r.items()
    ).lower()
    found = []
    seen: set[str] = set()
    for pattern, label in CURRENCY_PATTERNS:
        if label not in seen and re.search(pattern, combined):
            found.append(label)
            seen.add(label)
    return found


def _build_algorithm_lens(currencies: list[str], item_count: int) -> str:
    """Map detected economy patterns to RFY algorithm signal proxies.

    Interprets what the economy structure implies for the six algorithm signals:
    QPTR, deep engagement, 7-day playtime, play days, spend days, co-play.
    """
    has_robux = any("Robux" in c for c in currencies)
    has_ingame = any("Robux" not in c for c in currencies)
    parts = []

    if has_robux and has_ingame:
        parts.append(
            "Dual-currency economy (Robux + in-game grind currency): standard Roblox retention engine. "
            "In-game currency requires daily play sessions (boosts 7-day play-days proxy). "
            "Robux provides skip/exclusive access (drives spend-days signal). "
            "This combination correlates strongly with high engagement ratio and favorites rate."
        )
    elif has_robux:
        parts.append(
            "Robux-only economy: direct monetization but no free progression loop. "
            "Risk: non-spending players have no retention hook, weakening the 7-day play-days proxy."
        )
    elif has_ingame:
        parts.append(
            "Free progression economy (no Robux items found): strong accessibility signal. "
            "Drives high QPTR (players aren't gated) but spend-days signal near zero — "
            "limits algorithm distribution to non-monetization signals."
        )

    if item_count > 30:
        parts.append(
            f"Rich item catalog ({item_count}+ items): depth of collectibles correlates with "
            "repeat-session motivation — players return to grind/collect, improving play-days proxy "
            "and favorites rate (bookmark-to-return behavior)."
        )
    elif item_count > 5:
        parts.append(
            f"Moderate item catalog ({item_count} items): sufficient for basic progression loops "
            "but may lack the long-term collection depth that sustains 30+ day retention."
        )

    if not parts:
        parts.append(
            "Insufficient economy data extracted from wiki. "
            "Provide wiki_url directly or check the game's Shop/Gamepasses pages manually."
        )

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def analyze_game_wiki(game_name: str, wiki_url: str | None = None) -> dict:
    """Fetch and analyze a Roblox game's public wiki for design intelligence.

    Discovers the Fandom wiki (or uses the provided URL), fetches main page
    plus common sub-pages (Shop, Items, Gamepasses, Currency), extracts
    economy/item tables, detects currencies, and interprets the economy
    through the RFY algorithm lens.

    Games that fail wiki discovery return an error dict — caller should surface
    the hint to the user. Individual page failures are silently dropped.
    """
    async with httpx.AsyncClient(
        timeout=15,
        headers={"User-Agent": "Mozilla/5.0 (compatible; market-research-bot/1.0)"},
        follow_redirects=True,
    ) as client:
        # Resolve wiki base URL
        base = wiki_url.rstrip("/") if wiki_url else None
        if not base:
            base = await _discover_fandom_wiki(client, game_name)
        if not base:
            return {
                "error": f"No Fandom wiki found for '{game_name}'.",
                "hint": (
                    "Provide wiki_url directly (e.g. 'https://bloxfruits.fandom.com'). "
                    "Most Roblox game wikis live at <gamename>.fandom.com."
                ),
            }

        # Fetch main page + common sub-pages; collect economy tables
        all_economy_records: list[dict] = []
        description = ""
        pages_fetched = 0
        seen_urls: set[str] = set()

        for sub in WIKI_SUB_PAGES:
            url = base + sub
            if url in seen_urls:
                continue
            seen_urls.add(url)
            try:
                resp = await client.get(url, timeout=8)
                if resp.status_code != 200:
                    continue
                html = resp.text
                pages_fetched += 1

                if not description:
                    description = _extract_lead_text(html)

                for table in _parse_tables(html):
                    records = _table_to_records(table)
                    if _is_economy_table(records):
                        all_economy_records.extend(records[:25])  # cap per table
            except Exception:
                continue

        if pages_fetched == 0:
            return {
                "error": f"Wiki resolved to '{base}' but all page requests failed.",
                "wiki_url": base,
                "hint": "The wiki may be offline or behind a login wall.",
            }

        # Deduplicate records by first two cell values
        seen_keys: set[str] = set()
        unique_records: list[dict] = []
        for r in all_economy_records:
            key = str(list(r.values())[:2])
            if key not in seen_keys:
                seen_keys.add(key)
                unique_records.append(r)

        currencies = _detect_currencies(unique_records)
        algorithm_lens = _build_algorithm_lens(currencies, len(unique_records))

        return {
            "game": game_name,
            "wiki_source": base,
            "description": description or "No description extracted.",
            "currencies_detected": currencies,
            "economy_items_found": len(unique_records),
            "sample_items": unique_records[:15],
            "algorithm_lens": algorithm_lens,
            "pages_fetched": pages_fetched,
            "data_note": (
                "Sourced from public wiki. Item costs reflect wiki accuracy, not live game state. "
                "Missing data means the wiki may be incomplete, not the game."
            ),
        }

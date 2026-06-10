"""USA location detection and parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass

# ── Data tables ──────────────────────────────────────────────────────────────

US_STATE_ABBREVIATIONS: frozenset[str] = frozenset({
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC",
})

US_STATE_NAMES: dict[str, str] = {
    "alabama":"AL","alaska":"AK","arizona":"AZ","arkansas":"AR","california":"CA",
    "colorado":"CO","connecticut":"CT","delaware":"DE","florida":"FL","georgia":"GA",
    "hawaii":"HI","idaho":"ID","illinois":"IL","indiana":"IN","iowa":"IA",
    "kansas":"KS","kentucky":"KY","louisiana":"LA","maine":"ME","maryland":"MD",
    "massachusetts":"MA","michigan":"MI","minnesota":"MN","mississippi":"MS",
    "missouri":"MO","montana":"MT","nebraska":"NE","nevada":"NV",
    "new hampshire":"NH","new jersey":"NJ","new mexico":"NM","new york":"NY",
    "north carolina":"NC","north dakota":"ND","ohio":"OH","oklahoma":"OK",
    "oregon":"OR","pennsylvania":"PA","rhode island":"RI","south carolina":"SC",
    "south dakota":"SD","tennessee":"TN","texas":"TX","utah":"UT","vermont":"VT",
    "virginia":"VA","washington":"WA","west virginia":"WV","wisconsin":"WI",
    "wyoming":"WY","district of columbia":"DC",
}

US_CITIES: list[tuple[str, str]] = [
    # (city_lower, state_abbr)
    ("santa clara","CA"),("san jose","CA"),("cupertino","CA"),("sunnyvale","CA"),
    ("mountain view","CA"),("menlo park","CA"),("palo alto","CA"),("san francisco","CA"),
    ("san diego","CA"),("irvine","CA"),("san mateo","CA"),("beaverton","CA"),  # Broadcom
    ("folsom","CA"),("rancho cordova","CA"),("campbell","CA"),("milpitas","CA"),
    ("beaverton","OR"),("hillsboro","OR"),("portland","OR"),
    ("austin","TX"),("dallas","TX"),("houston","TX"),("san antonio","TX"),
    ("fort worth","TX"),("plano","TX"),("chandler","AZ"),("phoenix","AZ"),
    ("tempe","AZ"),("scottsdale","AZ"),
    ("seattle","WA"),("redmond","WA"),("bellevue","WA"),("kirkland","WA"),
    ("raleigh","NC"),("research triangle","NC"),("durham","NC"),
    ("boston","MA"),("cambridge","MA"),("waltham","MA"),("lexington","MA"),
    ("wilmington","MA"),("chelmsford","MA"),
    ("new york","NY"),("new york city","NY"),("nyc","NY"),
    ("atlanta","GA"),("boca raton","FL"),("fort collins","CO"),("boulder","CO"),
    ("denver","CO"),("minneapolis","MN"),("detroit","MI"),("ann arbor","MI"),
    ("pittsburgh","PA"),("boise","ID"),("bloomington","MN"),
    ("poughkeepsie","NY"),("san ramon","CA"),("pleasanton","CA"),
    ("san bruno","CA"),("south san francisco","CA"),("fremont","CA"),
    ("santa barbara","CA"),("goleta","CA"),("thousand oaks","CA"),
    ("westlake village","CA"),
]

NON_USA_SIGNALS: frozenset[str] = frozenset({
    "india","bangalore","bengaluru","hyderabad","pune","noida","gurgaon","gurugram",
    "chennai","mumbai","delhi","kolkata","ahmedabad",
    "canada","toronto","vancouver","montreal","ottawa","calgary","waterloo","ontario",
    "uk","united kingdom","london","cambridge uk","bristol","edinburgh",
    "germany","munich","berlin","hamburg","frankfurt","stuttgart","munich",
    "israel","tel aviv","herzliya","haifa","beer sheva","petah tikva","netanya",
    "taiwan","hsinchu","taipei","taichung",
    "singapore","malaysia","kuala lumpur","penang",
    "china","beijing","shanghai","shenzhen","hong kong",
    "japan","tokyo","osaka","yokohama",
    "south korea","korea","seoul","suwon",
    "netherlands","amsterdam","eindhoven",
    "france","paris","grenoble","sophia antipolis",
    "sweden","stockholm","gothenburg","lund",
    "finland","helsinki","espoo",
    "switzerland","zurich","bern",
    "argentina","buenos aires","cordoba argentina",
    "brazil","sao paulo","campinas",
    "australia","sydney","melbourne",
})

USA_EXPLICIT: tuple[str, ...] = (
    "united states", "united states of america", "usa", "u.s.", "u.s.a.", "us ",
)

REMOTE_SIGNALS: tuple[str, ...] = (
    "remote", "work from home", "wfh", "fully remote", "remote-first",
    "remote usa", "remote us", "remote (usa)", "remote (us)",
)


@dataclass
class LocationResult:
    is_usa: bool = False
    is_remote_usa: bool = False
    country: str = ""
    state: str = ""
    city: str = ""
    confidence: float = 0.0
    reason: str = ""


def parse_location(location_raw: str, description: str = "") -> LocationResult:
    """Detect whether a job is in the USA and extract state/city."""
    if not location_raw and not description:
        return LocationResult(confidence=0.0, reason="no location data")

    loc = (location_raw or "").lower().strip()
    desc_snippet = (description or "")[:500].lower()
    combined = loc + " " + desc_snippet

    # 1. Check for explicit non-USA country first (highest priority)
    for signal in NON_USA_SIGNALS:
        if re.search(r"\b" + re.escape(signal) + r"\b", combined):
            return LocationResult(
                is_usa=False, country=signal.title(), confidence=0.95,
                reason=f"non-USA signal: '{signal}'"
            )

    # 2. Explicit USA strings
    for sig in USA_EXPLICIT:
        if sig in loc:
            result = LocationResult(is_usa=True, country="USA", confidence=0.95, reason=f"explicit USA: '{sig}'")
            _extract_state_city(loc, result)
            _check_remote(loc, result)
            return result

    # 3. US state abbreviations (word-boundary matched)
    for abbr in US_STATE_ABBREVIATIONS:
        # Match ", CA" or " CA " or "(CA)" or "CA " at start
        if re.search(r"(?:^|[\s,/(])(" + abbr + r")(?:[\s,/)$]|$)", loc, re.IGNORECASE):
            result = LocationResult(is_usa=True, country="USA", state=abbr, confidence=0.90, reason=f"US state abbr: {abbr}")
            _extract_city(loc, result)
            _check_remote(loc, result)
            return result

    # 4. US state full names
    for state_name, abbr in US_STATE_NAMES.items():
        if state_name in loc:
            result = LocationResult(is_usa=True, country="USA", state=abbr, confidence=0.88, reason=f"US state name: {state_name}")
            _extract_city(loc, result)
            _check_remote(loc, result)
            return result

    # 5. Known US city names
    for city_lower, state_abbr in US_CITIES:
        if city_lower in loc:
            result = LocationResult(
                is_usa=True, country="USA", state=state_abbr, city=city_lower.title(),
                confidence=0.85, reason=f"US city: {city_lower}"
            )
            _check_remote(loc, result)
            return result

    # 6. Remote signal without country — assume USA if company is US-based
    for sig in REMOTE_SIGNALS:
        if sig in loc or sig in desc_snippet:
            return LocationResult(
                is_usa=True, is_remote_usa=True, country="USA",
                confidence=0.65, reason="remote signal, assumed USA"
            )

    # 7. Unknown
    return LocationResult(confidence=0.0, reason="location unknown")


def _check_remote(loc: str, result: LocationResult) -> None:
    for sig in REMOTE_SIGNALS:
        if sig in loc:
            result.is_remote_usa = result.is_usa
            break


def _extract_state_city(loc: str, result: LocationResult) -> None:
    _extract_state(loc, result)
    _extract_city(loc, result)


def _extract_state(loc: str, result: LocationResult) -> None:
    if result.state:
        return
    for abbr in US_STATE_ABBREVIATIONS:
        if re.search(r"(?:^|[\s,/(])(" + abbr + r")(?:[\s,/)$]|$)", loc, re.IGNORECASE):
            result.state = abbr
            return
    for state_name, abbr in US_STATE_NAMES.items():
        if state_name in loc:
            result.state = abbr
            return


def _extract_city(loc: str, result: LocationResult) -> None:
    if result.city:
        return
    for city_lower, state_abbr in US_CITIES:
        if city_lower in loc:
            result.city = city_lower.title()
            if not result.state:
                result.state = state_abbr
            return

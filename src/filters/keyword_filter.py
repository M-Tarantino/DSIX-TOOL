"""Default Stage 1 filter: keyword matching, German + English.

No ML dependency, runs instantly, zero cost. This is the filter used
unless FILTER_BACKEND=smollm is set. It is intentionally over-inclusive
(favors false positives over false negatives) since Stage 2's LLM
extraction is the real precision layer -- this stage only needs to cut
the ~90% of feed volume that is obviously unrelated (sports, weather,
entertainment, etc.).
"""
from __future__ import annotations

from .base import FilterResult

# Keep these short and high-signal. Longer/rarer terms belong in Stage 2's
# extraction prompt, not here -- this list only needs to catch the topic,
# not classify it precisely.
KEYWORDS: dict[str, list[str]] = {
    "terrorism_extremism": [
        "anschlag", "terror", "attentat", "sprengsatz", "bombendrohung",
        "islamist", "extremis", "amoklauf",
        "attack", "terrorist", "bombing", "explosive device",
    ],
    "cyber_security": [
        "cyberangriff", "hacker", "ransomware", "datenleck", "datenabfluss",
        "phishing", "it-sicherheit", "cybersicherheit", "bsi warnt",
        "cyberattack", "data breach", "ransomware", "hacked",
    ],
    "critical_infrastructure": [
        "stromausfall", "blackout", "sabotage", "umspannwerk", "stromnetz",
        "bahnverkehr gestört", "brücke gesperrt", "infrastruktur",
        "power outage", "power grid", "substation", "infrastructure attack",
    ],
    "political_stability": [
        "regierungskrise", "rücktritt", "koalition", "misstrauensvotum",
        "wahlergebnis", "putschversuch",
        "government crisis", "resignation", "coalition collapse",
    ],
    "societal_safety": [
        "organisierte kriminalität", "clan-kriminalität", "bandenkrieg",
        "schießerei", "explosion", "mafia", "drogenkartell",
        "organized crime", "gang violence", "shooting",
    ],
}


def check(title: str, summary: str) -> FilterResult:
    text = f"{title} {summary}".lower()
    best_dim: str | None = None
    best_hits = 0
    for dimension, terms in KEYWORDS.items():
        hits = sum(1 for term in terms if term in text)
        if hits > best_hits:
            best_hits = hits
            best_dim = dimension
    if best_hits == 0:
        return FilterResult(is_relevant=False)
    confidence = min(1.0, best_hits / 3)
    return FilterResult(is_relevant=True, dimension_guess=best_dim, confidence=confidence)

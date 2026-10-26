"""Left card: Customer Profile (README §4.1, §5.6). Owner: Agent CARDS.

    infer_tone(state) -> Tone                  # Agent NBA imports this for content
    build_profile(state, pop) -> Profile       # pop = profile_population(states)
    build_timeline(state) -> list[TimelineItem]

Consent, channels and exclusions come from Agent KG's views (nba.kg.rules), so the card never
re-implements a rule.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd
import yaml

from nba.contracts import Profile, TimelineItem, Tone
from nba.kg.rules import channel_view, consent_view, exclusion_view
from nba.profile.fatigue import build_fatigue
from nba.profile.header import build_header
from nba.profile.highlights import build_highlights
from nba.profile.population import profile_population
from nba.profile.products import build_products
from nba.profile.timeline import build_timeline as _build_timeline
from nba.profile.tone import infer_tone, policy
from nba.profile.trends import build_trends
from nba.profile.value import build_value_risk

REPO = Path(__file__).resolve().parents[2]

__all__ = ["infer_tone", "build_profile", "build_timeline", "profile_population", "cards_config"]


@lru_cache(maxsize=1)
def cards_config() -> dict:
    return yaml.safe_load((REPO / "config" / "cards.yaml").read_text(encoding="utf-8"))


def build_profile(state, pop: pd.DataFrame, tone: Tone | None = None) -> Profile:
    """Header, value_risk, products, consent, channels, exclusions, highlights, trends, fatigue."""
    cfg = cards_config()
    pol = policy()
    return Profile(
        header=build_header(state, tone or infer_tone(state, min_newsletter_clicks=cfg["tone"]["min_newsletter_clicks"])),
        value_risk=build_value_risk(state, pop),
        products=build_products(state),
        consent=consent_view(state, pol),
        channels=channel_view(state, pol),
        exclusions=exclusion_view(state, pol),
        highlights=build_highlights(state, pop, cfg["highlights"]),
        trends=build_trends(state, cfg["trend_ranges"]),
        fatigue=build_fatigue(state),
    )


def build_timeline(state) -> list[TimelineItem]:
    return _build_timeline(state, months=cards_config()["timeline_months"])

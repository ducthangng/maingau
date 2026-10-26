"""Du/Sie inference (README §4.1 A1, §6.8). Agent NBA imports infer_tone for content."""

from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache

from nba.contracts import Tone
from nba.profile.facts import clean, day

# Customer-side cues (§6.8). Weak cues count half.
DU_CUES = [
    ("hi", re.compile(r"\bhi\b", re.I), 1.0),
    ("hey", re.compile(r"\bhey\b", re.I), 1.0),
    ("danke dir", re.compile(r"\bdanke dir\b", re.I), 1.0),
    ("tschüss", re.compile(r"\btschüss\b", re.I), 1.0),
    ("du", re.compile(r"\bdu\b", re.I), 1.0),
    ("dir", re.compile(r"\bdir\b", re.I), 1.0),
    ("dein…", re.compile(r"\bdein\w*", re.I), 1.0),
    ("lg", re.compile(r"\blg\b", re.I), 1.0),
    ("viele grüße", re.compile(r"\bviele grüße\b", re.I), 0.5),
]
SIE_CUES = [
    ("Sehr geehrte", re.compile(r"\bsehr geehrte", re.I), 1.0),
    ("Mit freundlichen Grüßen", re.compile(r"\bmit freundlichen grüßen\b", re.I), 1.0),
    ("Ihnen", re.compile(r"\bIhnen\b"), 1.0),
]
# Capitalised "Ihr/Ihre/…" only counts mid-sentence; at a sentence start it may just be "ihr" (plural du).
IHR = re.compile(r"\bIhr(e|en|em|er)?\b")
SENTENCE_END = re.compile(r"(^|[.!?:\n])\s*$")


def _ihr_mid_sentence(text: str) -> bool:
    return any(not SENTENCE_END.search(text[: m.start()]) for m in IHR.finditer(text))


def _score(text: str) -> tuple[float, float, list[str], list[str]]:
    du_hits = [(name, w) for name, rx, w in DU_CUES if rx.search(text)]
    sie_hits = [(name, w) for name, rx, w in SIE_CUES if rx.search(text)]
    if _ihr_mid_sentence(text):
        sie_hits.append(("Ihr", 1.0))
    return (sum(w for _, w in du_hits), sum(w for _, w in sie_hits),
            [n for n, _ in du_hits], [n for n, _ in sie_hits])


def _customer_texts(state) -> list[tuple[str, str, str]]:
    """(date, ref, text) for every customer-written message and the Kunde: lines of call transcripts."""
    out = []
    for r in state.rows.get("service_interactions", []):
        text = clean(r.get("message_text"))
        if text:
            out.append((day(r.get("created_at")) or "", f"ticket:{r['ticket_id']}", str(text)))
    for r in state.rows.get("call_transcripts", []):
        transcript = clean(r.get("transcript")) or ""
        lines = [ln.split(":", 1)[1].strip() for ln in str(transcript).splitlines() if ln.strip().startswith("Kunde:")]
        if lines:
            out.append((day(r.get("call_started_at")) or "", f"call:{r['transcript_id']}", "\n".join(lines)))
    return sorted(out)


@lru_cache(maxsize=1)
def _workbook_campaign_tonality() -> dict[str, str]:
    from nba.data import load_workbook

    camps = load_workbook()["newsletter_campaigns"]
    return {r["campaign_id"]: r["tonality"] for r in camps.to_dict("records") if clean(r.get("tonality"))}


@lru_cache(maxsize=1)
def policy():
    """Agent KG's policy, loaded once; the profile uses its consent and channel views."""
    from nba.kg.policy import load_policy

    return load_policy()


def infer_tone(state, campaign_tonality: dict[str, str] | None = None, min_newsletter_clicks: int = 2) -> Tone:
    """Du/Sie with method and evidence. Priority: customer text → newsletter clicks → default Sie."""
    from nba.kg.rules import is_profiled

    if not is_profiled(state, policy()):
        return Tone(value="sie", method="default", evidence="Sie (default) – no profiling consent, tone not inferred")

    labelled = []  # (date, ref, label, cues)
    for date, ref, text in _customer_texts(state):
        du, sie, du_names, sie_names = _score(text)
        if du > sie:
            labelled.append((date, ref, "du", du_names))
        elif sie > du:
            labelled.append((date, ref, "sie", sie_names))
    counts = Counter(label for _, _, label, _ in labelled)
    if counts["du"] != counts["sie"]:
        value = "du" if counts["du"] > counts["sie"] else "sie"
        winners = [x for x in labelled if x[2] == value]
        cue = Counter(c for _, _, _, cues in winners for c in cues).most_common(1)[0][0]
        evidence = f"{value.capitalize()} – {len(winners)}/{len(labelled)} messages use '{cue}', latest {winners[-1][0]}"
        return Tone(value=value, method="text", evidence=evidence, refs=[ref for _, ref, _, _ in winners])

    tonality = campaign_tonality if campaign_tonality is not None else _workbook_campaign_tonality()
    clicks = sorted(
        (day(r.get("clicked_at")) or "", r["campaign_id"], tonality.get(r["campaign_id"]))
        for r in state.rows.get("newsletter_performance", [])
        if clean(r.get("clicked_at")) is not None and tonality.get(r["campaign_id"]) in ("du", "sie")
    )
    by_tone = Counter(t for _, _, t in clicks)
    if len(clicks) >= min_newsletter_clicks:
        value, n = by_tone.most_common(1)[0]
        if n * 3 >= len(clicks) * 2 and by_tone["du"] != by_tone["sie"]:
            evidence = (f"{value.capitalize()} – {n}/{len(clicks)} human newsletter clicks on '{value}' campaigns "
                        f"(weak: every campaign went to all subscribers)")
            return Tone(value=value, method="newsletter", evidence=evidence,
                        refs=[f"campaign:{c}" for _, c, t in clicks if t == value])

    if labelled:
        reason = f"no clear majority in {len(labelled)} messages"
    else:
        reason = "no text or newsletter signal"
    return Tone(value="sie", method="default", evidence=f"Sie (default) – {reason}")

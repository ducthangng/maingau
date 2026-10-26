"""Profile header (README §4.1 A1): age band, city, household, tenure, digital level, tone."""

from __future__ import annotations

from nba.contracts import Header, Tone
from nba.profile.facts import clean, fact


def age_band(birth_year, eval_year: int) -> str | None:
    birth_year = clean(birth_year)
    if birth_year is None:
        return None
    lo = (eval_year - int(birth_year)) // 10 * 10
    return f"{lo}–{lo + 9}"


def build_header(state, tone: Tone) -> Header:
    cm = state.one("customer_master") or {}
    cid = state.customer_id
    since = clean(cm.get("customer_since"))
    tenure = round((state.eval_time - since).days / 365.25, 1) if since else None
    return Header(
        age_band=fact(age_band(cm.get("birth_year"), state.eval_time.year), "customer_master.birth_year", cm, row_key=cid),
        city=fact(cm.get("city"), "customer_master.city", cm, row_key=cid),
        household_size=fact(cm.get("household_size"), "customer_master.household_size", cm, row_key=cid),
        tenure_years=fact(tenure, "customer_master.customer_since", cm, row_key=cid),
        digital={
            "portal_account": fact(cm.get("portal_account"), "customer_master.portal_account", cm, row_key=cid),
            "app_installed": fact(cm.get("app_installed"), "customer_master.app_installed", cm, row_key=cid),
            "language": fact(cm.get("preferred_contact_language"), "customer_master.preferred_contact_language", cm, row_key=cid),
        },
        tone=tone,
    )

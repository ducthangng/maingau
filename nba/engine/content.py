"""Approved German templates, rendered locally with no model at decision time."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from nba.contracts import Content
from nba.data import REPO


@lru_cache(maxsize=64)
def _template(path: str, mtime_ns: int):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def render_content(chosen, tone, personalised: bool, *, state=None, template_dir=None) -> Content:
    tone = getattr(tone, "value", tone)
    path = Path(template_dir or REPO / "templates" / "de") / f"{chosen.offer_id}.yaml"
    template = _template(str(path), path.stat().st_mtime_ns)
    variant = "personalised" if personalised else "generic"
    text = template[tone][variant]
    body = text["body"]
    if personalised and chosen.offer_id == "P-EN-02" and state is not None:
        dates = sorted(r["price_guarantee_until"] for r in state.rows.get("energy_contracts", [])
                       if r.get("status") == "active" and r.get("price_guarantee_until")
                       and 0 <= (r["price_guarantee_until"].date() - state.eval_time.date()).days < 90)
        if dates:
            intro = "Deine Preisgarantie endet am" if tone == "du" else "Ihre Preisgarantie endet am"
            body = f"{intro} {dates[0]:%d.%m.%Y}. {text['dated_body']}"
    return Content(tone=tone, personalised=personalised,
                   template_id=f"{chosen.offer_id}.{tone}.{'p' if personalised else 'g'}",
                   subject=text["subject"], body=body)


def agent_script(tone: str, template_dir=None) -> str:
    path = Path(template_dir or REPO / "templates" / "de") / "P-SV-01.yaml"
    return _template(str(path), path.stat().st_mtime_ns)[tone]["agent_script"]

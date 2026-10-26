"""Load model inputs once; never copy workbook parameters into code."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

from nba.contracts import SourceInfo, Versions
from nba.data import REPO, load_workbook
from nba.kg.bundle import source_info


class MissingDataError(ValueError):
    """A required input is absent or not numeric."""


def number(value: Any, source: str) -> float:
    if value is None or isinstance(value, bool):
        raise MissingDataError(f"Not enough data: {source}")
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise MissingDataError(f"Not enough data: {source}") from exc
    if not math.isfinite(result):
        raise MissingDataError(f"Not enough data: {source}")
    return result


def fingerprint(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


@dataclass
class EngineConfig:
    settings: dict[str, Any]
    assumptions: dict[str, Any]
    offers: dict[str, dict]
    history: list[dict]
    sources: dict[str, SourceInfo]
    value_date: str | None
    template_dir: Path = REPO / "templates" / "de"
    _history_index: Any = field(default=None, repr=False)
    lookalike: Any = field(default=None, repr=False)  # nba.learn.lookalike.Lookalike, attached by Runtime.load
    _versions: Any = field(default=None, repr=False)

    @property
    def p_mode(self) -> str:
        return self.settings["p_mode"]

    def parameter(self, name: str) -> float:
        return number(self.assumptions.get(name), f"value_assumptions.{name}")

    def with_mode(self, mode: str) -> EngineConfig:
        if mode not in {"rate", "uplift"}:
            raise ValueError("p_mode must be rate or uplift")
        return replace(self, settings={**self.settings, "p_mode": mode}, _history_index=self._history_index, _versions=None)

    def versions(self, policy) -> Versions:
        if self._versions is None:
            self._versions = Versions(
                policy=f"{policy.version}:{fingerprint(asdict(policy))}",
                value_model=f"{self.settings['value_model']}:{fingerprint([self.assumptions, self.offers])}",
                propensity=f"{self.settings['propensity_version']}:{self.p_mode}:{fingerprint([self.settings, self.history, self.lookalike and self.lookalike.version])}",
                templates=f"{self.settings['templates_version']}:{fingerprint([(p.name, p.read_text(encoding='utf-8')) for p in sorted(self.template_dir.glob('*.yaml'))])}",
            )
        return self._versions.model_copy(deep=True)


def load_config(tables=None, path: str | Path = REPO / "config" / "nba.yaml", *, p_mode=None) -> EngineConfig:
    tables = load_workbook() if tables is None else tables
    settings = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if settings.get("p_mode") not in {"rate", "uplift"}:
        raise ValueError("p_mode must be rate or uplift")
    for key in ("n_min", "rate_prior_strength"):
        if number(settings.get(key), f"config.nba.{key}") <= 0:
            raise ValueError(f"{key} must be positive")
    for key in ("p_service_success", "rate_prior_mean"):
        if not 0 <= number(settings.get(key), f"config.nba.{key}") <= 1:
            raise ValueError(f"{key} must be in [0, 1]")
    for key, o in (settings.get("p_overrides") or {}).items():
        if not isinstance(o, dict) or not 0 <= number(o.get("p"), f"config.nba.p_overrides.{key}.p") <= 1:
            raise ValueError(f"p_overrides.{key}.p must be in [0, 1]")
        if not o.get("case") or not o.get("approved_by"):
            raise ValueError(f"p_overrides.{key} needs the fix case and the reviewer (approved_by)")
    dates = sorted({r["clv_calc_date"].date().isoformat()
                    for r in tables["customer_value"].to_dict("records") if r.get("clv_calc_date")})
    cfg = EngineConfig(
        settings=settings,
        assumptions={r["parameter"]: r["value"] for r in tables["value_assumptions"].to_dict("records")},
        offers={r["product_id"]: r for r in tables["product_catalog"].to_dict("records")},
        history=tables["nba_action_history"].to_dict("records"),
        sources=source_info(tables),
        value_date=dates[0] if len(dates) == 1 else None,
    )
    return cfg.with_mode(p_mode) if p_mode is not None else cfg

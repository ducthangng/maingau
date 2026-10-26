"""Import CARDS' builders when available; otherwise expose missing profile sections honestly."""
from __future__ import annotations

import importlib

from nba.contracts import Fact, Header, Products, ProductLine, Profile, Tone, ValueRisk
from nba.kg.rules import channel_view, consent_view, exclusion_view, is_profiled


def _builder(name, modules):
    for module_name in modules:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            # Missing optional CARDS module is allowed; broken dependencies in an existing one are not.
            if exc.name and (exc.name == module_name or module_name.startswith(exc.name + ".")):
                continue
            raise
        if hasattr(module, name):
            return getattr(module, name)
    return None


def infer_tone(state, policy) -> Tone:
    if not is_profiled(state, policy):
        return Tone(value="sie", method="default", evidence="Sie (Standard; keine Profiling-Einwilligung)")
    builder = _builder("infer_tone", ("nba.profile", "nba.profile.tone"))
    if builder:
        return Tone.model_validate(builder(state))
    return Tone(value="sie", method="default", evidence="Sie (Standard; Tonanalyse noch nicht verfügbar)")


def build_sections(state, pop, policy, tone, *, bundle=None):
    builder = _builder("build_profile", ("nba.profile", "nba.profile.builder"))
    timeline_builder = _builder("build_timeline", ("nba.profile", "nba.profile.timeline"))
    consent = bundle.consent if bundle else consent_view(state, policy)
    channels = bundle.channels if bundle else channel_view(state, policy)
    exclusions = bundle.exclusions if bundle else exclusion_view(state, policy)
    if builder:
        profile = Profile.model_validate(builder(state, pop))
        profile.header.tone = tone
        # The gate views remain authoritative if a profile builder uses an older policy.
        profile.consent = consent
        profile.channels = channels
        profile.exclusions = exclusions
    else:
        def missing(src):
            return Fact(v=None, src=src)
        header = Header(age_band=missing("customer_master.birth_year"), city=missing("customer_master.city"),
                        household_size=missing("customer_master.household_size"),
                        tenure_years=missing("customer_master.customer_since"), tone=tone,
                        digital={k: missing("customer_master." + col) for k, col in
                                 (("portal_account", "portal_account"), ("app_installed", "app_installed"),
                                  ("language", "preferred_contact_language"))})
        risk = ValueRisk(**{k: missing("customer_value." + k) for k in
                            ("clv_eur", "annual_margin_eur", "cost_to_serve_12m_eur", "active_business_lines",
                             "churn_prob_12m", "clv_service_impact_eur")})
        products = Products(**{k: ProductLine(held=None, note="Nicht genug Daten: Profil noch nicht verfügbar")
                               for k in ("energy", "autostrom", "mobile", "shop", "smart_living", "internet")})
        profile = Profile(header=header, value_risk=risk, products=products,
                          consent=consent, channels=channels, exclusions=exclusions)
    timeline = timeline_builder(state) if timeline_builder else []
    return profile, timeline, builder is not None and timeline_builder is not None

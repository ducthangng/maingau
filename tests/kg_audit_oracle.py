"""Independent oracle for the KG audit (Agent KG audit session).

Recomputes the README definitions (§3, §5.1, §5.2, §6.1–§6.4, §6.12, §6.13) straight from the raw
workbook and event stream with pandas. It must never import `nba.kg` (nor `nba.data` / `nba.state`),
so a bug in the code under test cannot leak into the expected values.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta
from functools import cached_property, lru_cache
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
WORKBOOK = REPO / "data" / "maingau_nba_mockdata.xlsx"
EVENTS = REPO / "data" / "event_stream_2026-10-01.jsonl"
EVAL = datetime(2026, 9, 30, 23, 59, 59)

# ---------------------------------------------------------------- README constants

# §5.5
RULE_IDS = {"CONSENT-CHANNEL", "CONSENT-PROFILING", "CHANNEL-AVAILABLE", "EXCL-DUNNING", "EXCL-CANCELLATION",
            "EXCL-OPEN-TICKET", "EXCL-AUTOSTROM-CANCELLED", "HOLDING-PRECONDITION", "CONTACT-CAP",
            "ECON-NONPOSITIVE", "DATA-MISSING"}
CONSENT_TYPES = ["newsletter_email", "marketing_email", "marketing_phone", "marketing_sms",
                 "portal_app_personalisation", "profiling_analytics"]
SALES_TYPES = {"sales", "upsell", "retention", "one_off"}

# §6.1: channel -> (consent, extra customer_master field)
CHANNELS = {
    "newsletter_email": ("newsletter_email", None),
    "email": ("marketing_email", None),
    "outbound_call": ("marketing_phone", None),
    "sms": ("marketing_sms", None),
    "portal_popup": ("portal_app_personalisation", "portal_account"),
    "app_push": ("portal_app_personalisation", "app_installed"),
}
SERVICE_CHANNEL = "service_agent"
# §6.7
CONTACT_COST = {"newsletter_email": 0.01, "email": 0.01, "sms": 0.08, "portal_popup": 0.0, "app_push": 0.0,
                "service_agent": 0.0, "outbound_call": 6.0}
CAP_MAX, CAP_DAYS = 2, 30

# §6.2, in table order
EXCLUSIONS = ["EXCL-DUNNING", "EXCL-CANCELLATION", "EXCL-OPEN-TICKET", "EXCL-AUTOSTROM-CANCELLED"]

# §6.3: strength, purpose, needs, offers (S10 reinforces only)
SIGNAL_TABLE = {
    "S1": ("strong", "contract", ["N-HEAT-PUMP"], ["P-EN-03", "P-SL-01"]),
    "S2": ("strong", "service", ["N-SERVICE-FIX"], ["P-SV-01"]),
    "S3": ("strong", "behavioural", ["N-EV-CHARGING"], ["P-AS-01", "P-SL-03"]),
    "S4": ("strong", "contract", ["N-PRICE-SECURITY"], ["P-EN-02"]),
    "S5": ("medium", "behavioural", ["N-MORE-DATA"], ["P-MO-02"]),
    "S6": ("weak", "contract", ["N-EXTRA-SIM"], ["P-MO-03"]),
    "S7": ("medium", "device", ["N-ENERGY-MANAGEMENT"], ["P-SL-01"]),
    "S8": ("medium", "device", ["N-STORAGE-OPT", "N-WALLBOX-INTEGRATION"], ["P-SL-02", "P-SL-03"]),
    "S9": ("medium", "device", ["N-DYNAMIC-TARIFF"], ["P-EN-05"]),
    "S10": ("weak", "behavioural", ["N-HEAT-PUMP", "N-ENERGY-MANAGEMENT"], []),
    "S11": ("medium", "contract", ["N-HOME-ELECTRICITY"], ["P-EN-01"]),
    "S12": ("strong", "service", ["N-SERVICE-FIX"], ["P-SV-01"]),
    "S13": ("strong", "service", ["N-SERVICE-FIX"], ["P-SV-01"]),
}
SIGNAL_COUNTS = {"S1": 12, "S2": 2, "S3": 16, "S4": 143, "S5": 11, "S6": 80, "S7": 66, "S8": 33,
                 "S9": 48, "S10": 33, "S11": 161, "S12": 29, "S13": 39}
SERVICE_SIGNALS = {"S2", "S12", "S13"}
MARKETING_SIGNALS = {f"S{i}" for i in [1, 3, 4, 5, 6, 7, 8, 9, 10, 11]}

NEEDS = ["N-HEAT-PUMP", "N-SERVICE-FIX", "N-EV-CHARGING", "N-PRICE-SECURITY", "N-MORE-DATA", "N-EXTRA-SIM",
         "N-ENERGY-MANAGEMENT", "N-STORAGE-OPT", "N-WALLBOX-INTEGRATION", "N-DYNAMIC-TARIFF", "N-HOME-ELECTRICITY"]

# §6.4 preconditions, as plain-language keys evaluated by `Oracle.holds`
REQUIRES = {
    "P-EN-02": ["active_electricity", "price_guarantee_driver"],
    "P-EN-05": ["smart_meter_on_active_electricity"],
    # P-MO-01 has no requirement: generic offers only drop owned products (D1; README §6.4, Q-KG-21).
    "P-MO-02": ["active_mobile"],
    "P-MO-03": ["active_mobile"],
    "P-SL-02": ["hems_gateway", "home_battery"],
    "P-SL-03": ["hems_gateway", "wallbox_or_active_autostrom"],
}
NOT_HELD = {
    "P-EN-01": ["active_electricity"],
    "P-EN-03": ["tariff_stromwaerme"],
    "P-MO-01": ["active_mobile"],
    "P-SL-01": ["hems_gateway"],
    "P-SH-01": ["balkonkraftwerk_or_pv"],
    "P-SH-02": ["wallbox_device_or_delivered"],
    "P-SH-03": ["delivered_thermostats"],
    "P-SH-04": ["smart_plug_device_or_delivered"],
    "P-AS-01": ["active_autostrom"],
}
GENERIC_OFFERS = ["P-EN-01", "P-MO-01", "P-SL-01", "P-SH-01", "P-SH-03", "P-SH-04"]
DATA_MISSING_OFFERS = {"P-EN-04", "P-IN-01"}

# §4.3 + §6.11 (policy layer, extension edges; Campaign is the S10 EVIDENCED_BY target)
NODE_TYPES = {"Customer", "Contract", "Device", "Order", "Ticket", "Session", "Signal", "Need", "Offer", "Channel",
              "Consent", "Exclusion", "Action", "SignalType", "ConsentType", "ExclusionRule", "Campaign",
              "Archetype"}  # README §6.11 (Q-KG-22)
EDGE_TYPES = {"HOLDS", "OWNS_DEVICE", "PLACED", "RAISED", "EMITTED", "INDICATES", "ADDRESSED_BY", "DELIVERED_VIA",
              "REQUIRES", "BLOCKS", "RECEIVED", "RESPONDED", "EVIDENCED_BY", "HAS_SESSION", "HELD_OUT", "REINFORCES",
              "INSTANCE_OF", "IN_ARCHETYPE", "GENERIC_OFFER"}  # README §6.11 (Q-KG-22)

# §6.13
ARCHETYPE_COUNTS = {"A4": 75, "A1": 33, "A3": 201, "A5": 50, "A2": 342, "A0": 49}
TIER_COUNTS = {"P1": 53, "P2": 62, "P3": 95, "P4": 261, "P5": 279}
FLAG_COUNTS = {"service_critical": 53, "no_marketing_channel": 51, "no_profiling": 289, "negative_clv": 31,
               "top_clv": 75, "contact_fatigue": 188, "annoyed_before": 32, "prefers_en": 7, "data_inconsistent": 71}
OUTLIER_FLAGS = {"service_critical", "no_marketing_channel", "negative_clv", "annoyed_before", "prefers_en"}
OUTLIER_COUNT = 154
INCONSISTENT_TICKETS = {"TK-200565", "TK-200640"}

# §5.4 ui_ref grammar
UI_REF_PREFIXES = ("product:", "consent:", "exclusion:", "signal:", "timeline:", "trend:")
PRODUCT_LINES = {"energy", "autostrom", "mobile", "shop", "smart_living", "internet"}


# ---------------------------------------------------------------- raw data


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.apply(lambda s: s.str.strip() if s.dtype == object else s)
    return df.astype(object).where(df.notna() & (df != ""), None)


@lru_cache(maxsize=1)
def raw() -> dict[str, pd.DataFrame]:
    """Every sheet with dtype=str and empty strings as None; nothing else is parsed here."""
    return {n: _clean(df) for n, df in pd.read_excel(WORKBOOK, sheet_name=None, dtype=str).items()}


def _ts(v) -> datetime | None:
    return None if v is None else pd.Timestamp(v).to_pydatetime()


def _num(v) -> float:
    return 0.0 if v is None else float(v)


def _flag(v) -> bool:
    return str(v).strip().lower() in {"1", "1.0", "true"}


def _by_customer(sheet: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for r in raw()[sheet].to_dict("records"):
        if r.get("customer_id"):
            out[r["customer_id"]].append(r)
    return out


def raw_event_lines() -> list[dict]:
    with EVENTS.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def expected_events() -> list[tuple[str, str]]:
    """(event_id, ingested_at) after dedup on (event_id, occurred_at), sorted by ingested_at then event_id."""
    df = pd.DataFrame(raw_event_lines())
    df = df.drop_duplicates(subset=["event_id", "occurred_at"], keep="first")
    df["ing"] = pd.to_datetime(df["ingested_at"])
    df = df.sort_values(["ing", "event_id"], kind="mergesort")
    return list(zip(df["event_id"], df["ingested_at"]))


# ---------------------------------------------------------------- the oracle


class Oracle:
    """Per-customer facts, signals, gates and triage, from the README definitions only."""

    def __init__(self):
        t = raw()
        self.customers: list[str] = list(t["customer_master"]["customer_id"])
        self.master = {r["customer_id"]: r for r in t["customer_master"].to_dict("records")}
        self.value = {r["customer_id"]: r for r in t["customer_value"].to_dict("records")}
        self.energy = _by_customer("energy_contracts")
        self.mobile = _by_customer("mobile_contracts")
        self.autostrom = _by_customer("autostrom_contracts")
        self.charges = _by_customer("charge_sessions")
        self.devices_rows = _by_customer("hems_devices")
        self.orders = _by_customer("shop_orders")
        self.tickets = _by_customer("service_interactions")
        self.feedback = _by_customer("service_nba_feedback")
        self.consent_rows = _by_customer("consent_status")
        self.history = _by_customer("nba_action_history")
        self.newsletter = _by_customer("newsletter_performance")
        self.catalog = {r["product_id"]: r for r in t["product_catalog"].to_dict("records")}

    # ---- holdings (§5.2, §6.4)

    def active_energy(self, c: str, commodity: str | None = None) -> list[dict]:
        return [r for r in self.energy[c] if r["status"] == "active" and (commodity is None or r["commodity"] == commodity)]

    def active_mobile(self, c: str) -> list[dict]:
        return [r for r in self.mobile[c] if r["status"] == "active"]

    def has_active_autostrom(self, c: str) -> bool:
        return any(r["status"] == "active" for r in self.autostrom[c])

    def device_types(self, c: str) -> set[str]:
        return {r["device_type"] for r in self.devices_rows[c] if r.get("device_type")}

    def delivered(self, c: str) -> set[str]:
        return {r["product_name"] for r in self.orders[c] if r.get("order_status") == "delivered"}

    def holds(self, c: str, key: str) -> bool:
        devs, bought, elec = self.device_types(c), self.delivered(c), self.active_energy(c, "electricity")
        drivers = self.value[c].get("churn_drivers") or ""
        return {
            "active_electricity": bool(elec),
            "active_energy": bool(self.active_energy(c)),
            "active_mobile": bool(self.active_mobile(c)),
            "active_autostrom": self.has_active_autostrom(c),
            "price_guarantee_driver": "price guarantee ends <90d" in drivers,
            "smart_meter_on_active_electricity": any(r["meter_type"] == "smart_meter_imsys" for r in elec),
            "tariff_stromwaerme": any(r["tariff"] == "StromWärme" for r in self.active_energy(c)),
            "hems_gateway": "hems_gateway" in devs,
            "home_battery": "home_battery" in devs,
            "wallbox_or_active_autostrom": "wallbox" in devs or self.has_active_autostrom(c),
            "balkonkraftwerk_or_pv": ("Balkonkraftwerk 800 W" in bought or "pv_inverter" in devs
                                      or any(_flag(r["feed_in_meter"]) for r in elec)),
            "wallbox_device_or_delivered": "wallbox" in devs or "Wallbox 11 kW" in bought,
            "delivered_thermostats": "Smarte Thermostate 3er" in bought,
            "smart_plug_device_or_delivered": "smart_plug" in devs or "Smart Plug 4er-Set" in bought,
        }[key]

    def owns(self, c: str, offer: str) -> bool:
        return any(self.holds(c, k) for k in NOT_HELD.get(offer, []))

    def requirements_met(self, c: str, offer: str) -> bool:
        return all(self.holds(c, k) for k in REQUIRES.get(offer, []))

    # ---- consent and channels (§6.1)

    def consent(self, c: str) -> dict[str, dict]:
        rows = {r["consent_type"]: r for r in self.consent_rows[c]}
        unsub = any(_flag(r.get("unsubscribed")) for r in self.newsletter[c])
        out = {}
        for ct in CONSENT_TYPES:
            r = rows.get(ct) or {}
            status = r.get("status") or "unknown"
            effective = "withdrawn" if (ct == "newsletter_email" and unsub and status == "granted") else status
            out[ct] = {"status": status, "effective": effective, "doi": bool(r.get("double_opt_in_confirmed_at"))}
        return out

    def profiled(self, c: str) -> bool:
        return self.consent(c)["profiling_analytics"]["effective"] == "granted"

    def channels(self, c: str) -> dict[str, tuple[bool, str | None]]:
        """channel -> (allowed, blocking rule id)."""
        cons, m = self.consent(c), self.master[c]
        out = {}
        for ch, (ct, field) in CHANNELS.items():
            ci = cons[ct]
            if ci["effective"] != "granted" or (ch == "newsletter_email" and not ci["doi"]):
                out[ch] = (False, "CONSENT-CHANNEL")
            elif field and not _flag(m.get(field)):
                out[ch] = (False, "CHANNEL-AVAILABLE")
            else:
                out[ch] = (True, None)
        return out

    def allowed_channels(self, c: str) -> set[str]:
        return {ch for ch, (ok, _) in self.channels(c).items() if ok}

    # ---- exclusions (§6.2) and contacts (§5.2)

    def exclusions(self, c: str) -> list[str]:
        out = []
        if any(_num(r.get("dunning_level")) >= 1 for r in self.energy[c]):
            out.append("EXCL-DUNNING")
        if any(r["status"] == "cancellation_pending" for r in self.energy[c]):
            out.append("EXCL-CANCELLATION")
        if any(r["status"] == "open" for r in self.tickets[c]):
            out.append("EXCL-OPEN-TICKET")
        if any(r["status"] == "cancelled" for r in self.autostrom[c]):
            out.append("EXCL-AUTOSTROM-CANCELLED")
        return out

    def contacts(self, c: str, days: int, at: datetime = EVAL) -> set[str]:
        start = at - timedelta(days=days)
        return {r["action_id"] for r in self.history[c]
                if r["delivery_status"] == "delivered" and not _flag(r["control_group"])
                and r.get("decided_at") and start < _ts(r["decided_at"]) <= at}

    def capped(self, c: str) -> bool:
        # B-02 (docs/rule-center.md §4, config/kg.yaml contact_cap.sources): delivered NBA actions plus
        # offers a service agent mentioned to the customer (service_nba_feedback), one per channel + time.
        start = EVAL - timedelta(days=CAP_DAYS)
        seen = {(r["channel"], _ts(r["decided_at"])) for r in self.history[c]
                if r["delivery_status"] == "delivered" and not _flag(r["control_group"])
                and r.get("decided_at") and start < _ts(r["decided_at"]) <= EVAL}
        seen |= {("outbound_call", _ts(r["shown_at"])) for r in self.feedback[c]
                 if _flag(r.get("offer_mentioned_to_customer")) and r.get("shown_at")
                 and start < _ts(r["shown_at"]) <= EVAL}
        return len(seen) >= CAP_MAX

    # ---- signals (§6.3)

    def pg_days(self, c: str) -> int | None:
        """Smallest 0 <= days < 90 to price_guarantee_until over active energy contracts (S4)."""
        days = [(_ts(r["price_guarantee_until"]).date() - EVAL.date()).days
                for r in self.active_energy(c) if r.get("price_guarantee_until")]
        days = [d for d in days if 0 <= d < 90]
        return min(days) if days else None

    def gas_deregistered_at(self, c: str) -> datetime | None:
        ds = [_ts(r["meter_deregistered_at"]) for r in self.energy[c] if r["commodity"] == "gas" and r.get("meter_deregistered_at")]
        return max(ds) if ds else None

    def failed_charges_30d(self, c: str) -> list[dict]:
        start = EVAL - timedelta(days=30)
        return [r for r in self.charges[c] if r["session_status"] == "failed" and r.get("started_at")
                and start < _ts(r["started_at"]) <= EVAL]

    def signal_offers(self, c: str, sid: str) -> list[str]:
        if sid != "S8":
            return SIGNAL_TABLE[sid][3]
        devs = self.device_types(c)
        out = []
        if "home_battery" in devs:
            out.append("P-SL-02")
        if "wallbox" in devs or self.has_active_autostrom(c):
            out.append("P-SL-03")
        return out

    def signals(self, c: str) -> set[str]:
        devs, m = self.device_types(c), self.master[c]
        elec, mob = self.active_energy(c, "electricity"), self.active_mobile(c)
        out = set()
        if self.gas_deregistered_at(c):
            out.add("S1")
        if len(self.failed_charges_30d(c)) >= 3:
            out.add("S2")
        if "Wallbox 11 kW" in self.delivered(c) and not self.has_active_autostrom(c):
            out.add("S3")
        if self.pg_days(c) is not None:
            out.add("S4")
        if any(_num(r.get("data_limit_reached_3m")) >= 2 for r in mob):
            out.add("S5")
        if any(_num(m.get("household_size")) > _num(r.get("sim_count")) for r in mob):
            out.add("S6")
        if (any(_flag(r["feed_in_meter"]) for r in elec) or "pv_inverter" in devs) and "hems_gateway" not in devs:
            out.add("S7")
        if "hems_gateway" in devs and ("home_battery" in devs or "wallbox" in devs or self.has_active_autostrom(c)):
            out.add("S8")
        if any(r["meter_type"] == "smart_meter_imsys" and ("hems_gateway" in devs or self.has_active_autostrom(c)
                                                           or "heat_pump" in devs or r["tariff"] == "StromWärme")
               for r in elec):
            out.add("S9")
        if any(r.get("clicked_at") and r.get("click_target") in ("heat_pump_article", "smart_living_landingpage")
               and _ts(r["clicked_at"]) <= EVAL for r in self.newsletter[c]):
            out.add("S10")
        if self.has_active_autostrom(c) and not elec:
            out.add("S11")
        if any(r["status"] == "open" for r in self.tickets[c]):
            out.add("S12")
        if {"EXCL-DUNNING", "EXCL-CANCELLATION"} & set(self.exclusions(c)):
            out.add("S13")
        return out

    @cached_property
    def signal_sets(self) -> dict[str, set[str]]:
        out = {s: set() for s in SIGNAL_TABLE}
        for c in self.customers:
            for s in self.signals(c):
                out[s].add(c)
        return out

    # ---- tuples (§6.12): set of (offer, channel, origin)

    def expected_tuples(self, c: str) -> set[tuple[str, str, str]]:
        sigs = self.signals(c)
        out = set()
        if sigs & SERVICE_SIGNALS:
            out.add(("P-SV-01", SERVICE_CHANNEL, "service"))
        if self.exclusions(c) or self.capped(c):
            return out
        chans = self.allowed_channels(c)
        signal_offers = set()
        if self.profiled(c):
            for s in sigs & (MARKETING_SIGNALS - {"S10"}):
                for o in self.signal_offers(c, s):
                    if self.requirements_met(c, o) and not self.owns(c, o):
                        signal_offers.add(o)
            out |= {(o, ch, "signal") for o in signal_offers for ch in chans}
        for o in GENERIC_OFFERS:
            if o not in signal_offers and not self.owns(c, o):
                out |= {(o, ch, "generic") for ch in chans}
        return out

    # ---- triage (§6.13)

    def churn(self, c: str) -> float:
        return _num(self.value[c].get("churn_prob_12m"))

    def clv(self, c: str) -> float:
        return _num(self.value[c].get("clv_eur"))

    def archetype(self, c: str) -> str:
        lines = {r["commodity"] for r in self.active_energy(c)}
        mob = self.active_mobile(c)
        if self.exclusions(c) or self.churn(c) >= 0.35:
            return "A4"
        if "hems_gateway" in self.device_types(c):
            return "A1"
        if self.has_active_autostrom(c):
            return "A3"
        hh = _num(self.master[c].get("household_size"))
        if any(hh > _num(r.get("sim_count")) or _num(r.get("data_limit_reached_3m")) >= 1 for r in mob):
            return "A5"
        if lines and not mob:
            return "A2"
        return "A0"

    def tier(self, c: str) -> str:
        sigs, ex = self.signals(c), self.exclusions(c)
        dunning = max([_num(r.get("dunning_level")) for r in self.energy[c]] or [0])
        open_t = [r for r in self.tickets[c] if r["status"] == "open"]
        complaint = [r for r in open_t if r.get("category") == "complaint"]
        pg = self.pg_days(c)
        dereg = self.gas_deregistered_at(c)
        if "EXCL-CANCELLATION" in ex or complaint or dunning >= 2 or "S2" in sigs:
            return "P1"
        if open_t or dunning == 1 or (pg is not None and pg <= 30) or self.churn(c) >= 0.35:
            return "P2"
        if pg is not None or (dereg and EVAL - dereg <= timedelta(days=90)) or "S5" in sigs:
            return "P3"
        if sigs - {"S10"}:
            return "P4"
        return "P5"

    def urgency_score(self, c: str) -> float:
        n = int(self.tier(c)[1])
        return 100 * (5 - n) + min(99.0, max(0.0, self.clv(c)) * self.churn(c) / 10)

    @cached_property
    def clv_p90(self) -> float:
        vals = sorted(self.clv(c) for c in self.customers)
        return vals[int(0.9 * len(vals))]  # README: p90 = 1,023 €

    def late_cdr(self, c: str) -> bool:
        return any(r.get("cdr_received_at") and _ts(r["cdr_received_at"]) > EVAL for r in self.charges[c])

    def odd_ticket(self, c: str) -> bool:
        return any(r["ticket_id"] in INCONSISTENT_TICKETS for r in self.tickets[c])

    def flags(self, c: str) -> set[str]:
        out = set()
        if self.tier(c) == "P1":
            out.add("service_critical")
        if not self.allowed_channels(c):
            out.add("no_marketing_channel")
        if not self.profiled(c):
            out.add("no_profiling")
        if self.clv(c) < 0:
            out.add("negative_clv")
        if self.clv(c) >= self.clv_p90:
            out.add("top_clv")
        c90 = self.contacts(c, 90)
        ignored = sum(1 for r in self.history[c] if r["action_id"] in c90 and r.get("response") in ("ignored", "dismissed"))
        if len(self.contacts(c, 30)) >= 2 or ignored >= 3:
            out.add("contact_fatigue")
        if any(r.get("customer_reaction") == "annoyed" or r.get("dismiss_reason") == "customer_upset" for r in self.feedback[c]):
            out.add("annoyed_before")
        if self.master[c].get("preferred_contact_language") == "en":
            out.add("prefers_en")
        if self.late_cdr(c) or self.odd_ticket(c):
            out.add("data_inconsistent")
        return out

    # ---- README §3 / K4 and Q-KG-06

    def autostrom_counts(self) -> tuple[int, int, int]:
        any_a = {c for c in self.customers if self.autostrom[c]}
        any_e = {c for c in self.customers if self.energy[c]}
        any_m = {c for c in self.customers if self.mobile[c]}
        act = {c for c in self.customers if self.has_active_autostrom(c) and not self.active_energy(c, "electricity")}
        return len(any_a - any_e), len(act), len(any_a - any_e - any_m)

    def price_driver_without_s4(self) -> dict[str, str]:
        out = {}
        for c in self.customers:
            if self.holds(c, "price_guarantee_driver") and "S4" not in self.signals(c):
                why = []
                for r in self.energy[c]:
                    if r.get("price_guarantee_until"):
                        d = (_ts(r["price_guarantee_until"]).date() - EVAL.date()).days
                        why.append(f"{r['contract_id']} {r['commodity']} status={r['status']} "
                                   f"price_guarantee_until={r['price_guarantee_until'][:10]} ({d} days)")
                out[c] = "; ".join(why)
        return out


@lru_cache(maxsize=1)
def oracle() -> Oracle:
    return Oracle()

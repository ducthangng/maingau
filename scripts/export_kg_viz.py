"""Export the knowledge graph for the ontology viewer (Agent KG): the ontology, the policy layer, and the
decision graph of a few demo customers, all taken from the running engine (nothing is drawn by hand).

  .venv/bin/python scripts/export_kg_viz.py                       # default demo customers -> out/kg_viz.json
  .venv/bin/python scripts/export_kg_viz.py --customers MG-100023,MG-100112 --out out/kg_viz.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from nba.contracts import NO_ACTION  # noqa: E402
from nba.engine.runtime import Runtime  # noqa: E402
from nba.kg.rules import consents  # noqa: E402

DEMO = {  # customer -> the case it demonstrates
    "MG-100023": "Wallbox, no Autostrom → Autostrom",
    "MG-100068": "three signals compete",
    "MG-100112": "no profiling consent → catalog call",
    "MG-100096": "dunning → service only",
    "MG-100186": "open complaint → service only",
    "MG-100026": "over the e-mail limit → waits",
    "MG-100001": "no app → portal instead",
    "MG-100009": "failed charging → service",
}
STATUS_ORDER = {"chosen": 0, "alternative": 1, "waiting": 2, "blocked": 3}
HIDDEN_FACTS = ("payment", "dunning", "iban", "customer_id", "message_text", "call_note")  # C-09: payment data never shown
RELATION = {"contract": "holds", "order": "placed", "device": "owns", "ticket": "raised", "session": "charged"}


def _ref(ref: str) -> tuple[str, str]:
    kind, _, rid = ref.partition(":")
    return kind, rid


def evidence_nodes(state, refs: set[str]) -> list[dict]:
    """The workbook rows a signal cites: contracts, orders, devices, tickets, sessions, campaigns."""
    rows = {
        "contract": [(r, "energy_contracts") for r in state.rows["energy_contracts"]]
        + [(r, "mobile_contracts") for r in state.rows["mobile_contracts"]]
        + [(r, "autostrom_contracts") for r in state.rows["autostrom_contracts"]],
        "order": [(r, "shop_orders") for r in state.rows["shop_orders"]],
        "device": [(r, "hems_devices") for r in state.rows["hems_devices"]],
        "ticket": [(r, "service_interactions") for r in state.rows["service_interactions"]],
        "session": [(r, "charge_sessions") for r in state.rows["charge_sessions"]],
    }
    keys = {"contract": "contract_id", "order": "order_id", "device": "device_id", "ticket": "ticket_id", "session": "session_id"}
    out = []
    for ref in sorted(refs):
        kind, rid = _ref(ref)
        row, sheet = next(((r, s) for r, s in rows.get(kind, []) if str(r.get(keys.get(kind, ""))) == rid), (None, None))
        if kind == "contract" and row:
            label = f"{row.get('commodity') or sheet.split('_')[0]} · {row.get('tariff') or row.get('plan') or row.get('status')}"
        elif kind == "order" and row:
            label = f"{row.get('product_name')} · {row.get('order_status')}"
        elif kind == "device" and row:
            label = f"{row.get('device_type')} · {row.get('connection_status')}"
        elif kind == "ticket" and row:
            label = f"{row.get('category')} · {row.get('status')}"
        elif kind == "session" and row:
            label = f"charging · {row.get('session_status')}"
        else:
            label = kind
        facts = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in (row or {}).items()
                 if not any(h in k for h in HIDDEN_FACTS) and v is not None}
        out.append({"id": ref, "kind": kind, "label": label, "src": sheet or kind, "facts": dict(list(facts.items())[:10])})
    return out


def _node(nodes, nid, col, kind, label, sub="", status=None, detail=None):
    if nid not in nodes:
        nodes[nid] = {"id": nid, "col": col, "kind": kind, "label": label, "sub": sub, "status": status, "detail": detail or {}}
    return nodes[nid]


def customer_graph(view: dict, policy) -> dict:
    """Columns: customer | data rows | signals | needs | offers | channels | consent; edges carry the decision state."""
    nodes, edges = {}, []
    cid = view["id"]

    def edge(a, b, label, status="plain", path=False):
        edges.append({"from": a, "to": b, "label": label, "status": status, "path": path})

    h = view["headline"]
    _node(nodes, cid, 0, "customer", cid, h["archetype"], detail={"urgency": h["urgency"], "churn 12m": h["churn"],
                                                                  "CLV €": h["clv"], "business lines": h["lines"],
                                                                  "profiling consent": h["profiled"], "tone": h["tone"]})
    path_ids = {p.get("id") for p in view["path"] if p.get("kind") == "node"}
    for e in view["evidence"]:
        _node(nodes, e["id"], 1, "data", e["id"].split(":", 1)[1], e["label"], detail={"source": e["src"], **e["facts"]})
        edge(cid, e["id"], RELATION.get(e["kind"], "has"))
    offers_seen = {}
    for s in view["signals"]:
        sid = f"sig:{s['id']}"
        _node(nodes, sid, 2, "signal", s["id"], s["label"], detail={"detail": s["detail"], "date": s["date"],
                                                                    "strength": s["strength"], "source": s["src"]})
        refs = [r for r in s["evidence"] if r in nodes]
        for r in refs:
            edge(r, sid, "evidence for", path=s["id"] in path_ids)
        if not refs:
            edge(cid, sid, "emitted", path=s["id"] in path_ids)
        for n in s["needs"]:
            nid = f"need:{n}"
            _node(nodes, nid, 3, "need", n.removeprefix("N-").replace("-", " ").lower(), policy.needs[n]["label_en"])
            reinforces = n in policy.signals[s["id"]].reinforces
            edge(sid, nid, "reinforces" if reinforces else "indicates", path=s["id"] in path_ids and n in path_ids)
            for o in s["offers"]:
                if n in policy.offers[o].addresses:
                    offers_seen.setdefault(o, set()).add(n)
    tuples = view["tuples"]
    offer_status = {}
    for t in tuples:
        cur = offer_status.get(t["offer"])
        if cur is None or STATUS_ORDER[t["status"]] < STATUS_ORDER[cur]:
            offer_status[t["offer"]] = t["status"]
    offer_rows = {b["offer"]: b for b in view.get("offer_blocks", [])}
    for oid in sorted(set(offers_seen) | set(offer_status) | set(offer_rows), key=lambda o: (STATUS_ORDER.get(offer_status.get(o, "blocked")), o)):
        o = policy.offers[oid]
        status = offer_status.get(oid, "blocked")
        block = offer_rows.get(oid)
        sub = o.name if status != "blocked" or not block else f"{o.name} · {block.get('rc') or block['rule']}"
        _node(nodes, f"offer:{oid}", 4, "offer", oid, sub, status,
              detail={"name": o.name, "type": o.action_type, "line": o.business_line,
                      **({"blocked by": block.get("rc") or block["rule"], "reason": block["reason"]} if block and status == "blocked" else {})})
        on_path = oid in path_ids
        for n in sorted(offers_seen.get(oid, ())):
            edge(f"need:{n}", f"offer:{oid}", "addressed by", "blocked" if status == "blocked" else "plain", path=on_path)
        if oid not in offers_seen and any(t["offer"] == oid and t.get("origin") == "generic" for t in tuples):
            edge(cid, f"offer:{oid}", "catalog offer", path=on_path)
    chans = {c["channel"]: c for c in view["channels"]}
    cons = {c["type"]: c for c in view["consents"]}
    used_by_tuples = {t["channel"] for t in tuples if t.get("channel")}
    used = [c for c in chans if c != policy.service_channel or c in used_by_tuples]  # every marketing channel + service if used
    for ch in used:
        info = chans.get(ch, {})
        _node(nodes, f"ch:{ch}", 5, "channel", ch.replace("_", " "), "allowed" if info.get("allowed", True) else "not allowed",
              None if info.get("allowed", True) else "blocked", detail={"reason": info.get("reason")})
        consent = info.get("consent")
        if consent:
            c = cons.get(consent, {})
            ok = c.get("effective") == "granted"
            _node(nodes, f"consent:{consent}", 6, "consent", consent.replace("_", " "), c.get("effective", "not given"),
                  None if ok else "blocked", detail={"status": c.get("status"), "effective": c.get("effective"),
                                                     "updated": c.get("updated_at"), "double opt-in": c.get("doi"),
                                                     "override": c.get("override")})
            edge(f"ch:{ch}", f"consent:{consent}", "requires", "plain" if ok else "blocked", path=consent in path_ids)
    for t in tuples:
        if not t.get("channel"):
            continue
        label = {"chosen": f"ΔCLV +€{t['dclv']:.2f}", "alternative": f"€{t['dclv']:.2f}" if t.get("dclv") is not None else "",
                 "waiting": f"waits → {(t.get('until') or '')[:10]}", "blocked": t.get("rule") or "blocked"}[t["status"]]
        if t["status"] == "waiting" and t.get("rule"):
            label = f"{t['rule']} · waits → {(t.get('until') or '')[:10]}"
        edge(f"offer:{t['offer']}", f"ch:{t['channel']}", label, t["status"], path=t["status"] == "chosen")
    for w in view["wide"]:
        if w["channel"] is None and w["rule"] not in ("CONSENT-CHANNEL", "DATA-MISSING"):
            rid = f"rule:{w['rule']}"
            _node(nodes, rid, 3, "rule", w.get("rc") or w["rule"], w["rule"].replace("EXCL-", "").replace("-", " ").lower(),
                  "waiting" if w.get("until") else "blocked", detail={"reason": w["reason"], "until": w.get("until")})
            for oid, st in offer_status.items():
                if policy.offers[oid].action_type != "service":
                    edge(rid, f"offer:{oid}", "holds back" if w.get("until") else "blocks", "waiting" if w.get("until") else "blocked")
            for oid in offer_rows:
                if offer_rows[oid]["rule"] == w["rule"]:
                    edge(rid, f"offer:{oid}", "blocks", "blocked")
    for n in nodes.values():
        n["path"] = n["id"] == cid or any(e["path"] and n["id"] in (e["from"], e["to"]) for e in edges)
    return {"columns": ["Customer", "Data", "Signals", "Needs & rules", "Offers", "Channels", "Consent"],
            "nodes": list(nodes.values()), "edges": edges}


ONTOLOGY_COLUMNS = ["Customer", "Data rows", "Instances", "Types & rules", "Needs", "Offers", "Channels"]
ONTOLOGY_COL = {"Customer": 0, "Contract": 1, "Device": 1, "Order": 1, "Ticket": 1, "Session": 1, "Action": 1, "Campaign": 1,
                "Signal": 2, "Consent": 2, "Exclusion": 2, "Feedback": 2, "SignalType": 3, "ConsentType": 3, "ExclusionRule": 3,
                "Archetype": 3, "Need": 4, "Offer": 5, "Channel": 6}


def ontology_graph(onto: dict, edges: list[dict]) -> dict:
    nodes = [{"id": k, "col": ONTOLOGY_COL.get(k, 2), "kind": "type" if v["layer"] == "policy" else "instance", "label": k,
              "sub": f"{v['layer']} layer" + (f" · {v['source']}" if isinstance(v.get("source"), str) else ""),
              "status": None, "detail": {"layer": v["layer"], "id pattern": v.get("id"), "source": v.get("source"),
                                         "properties": v.get("props"), "note": v.get("note")}}
             for k, v in onto["node_types"].items()]
    order = {n["id"]: i for i, n in enumerate(nodes)}
    nodes.sort(key=lambda n: (n["col"], order[n["id"]]))
    return {"columns": ONTOLOGY_COLUMNS, "nodes": nodes,
            "edges": [{"from": e["from"], "to": e["to"], "label": e["type"], "status": "plain", "path": False} for e in edges]}


def policy_graph(policy) -> dict:
    nodes, edges = [], []
    for sg in policy.signals.values():
        nodes.append({"id": f"sig:{sg.id}", "col": 0, "kind": "signal", "label": sg.id, "sub": sg.label, "status": None,
                      "detail": {"label": sg.label, "strength": sg.strength, "purpose": sg.purpose, "predicate": sg.predicate}})
        edges += [{"from": f"sig:{sg.id}", "to": f"need:{n}", "label": "indicates", "status": "plain", "path": False} for n in sg.indicates]
        edges += [{"from": f"sig:{sg.id}", "to": f"need:{n}", "label": "reinforces", "status": "alternative", "path": False}
                  for n in sg.reinforces]
    for nid, n in policy.needs.items():
        nodes.append({"id": f"need:{nid}", "col": 1, "kind": "need", "label": nid.removeprefix("N-").replace("-", " ").lower(),
                      "sub": n["label_en"], "status": None, "detail": {"need": nid, "label": n["label_en"], "German": n.get("label_de")}})
    generic = {o.id for o in policy.generic_offers}
    for o in policy.offers.values():
        tag = "not enough data" if o.data_missing else ("catalog + signal" if o.id in generic and o.addresses
                                                         else "catalog offer" if o.id in generic else o.action_type)
        nodes.append({"id": f"offer:{o.id}", "col": 2, "kind": "offer", "label": o.id, "sub": f"{o.name} · {tag}",
                      "status": "blocked" if o.data_missing else None,
                      "detail": {"name": o.name, "type": o.action_type, "line": o.business_line, "generic": o.id in generic,
                                 "requires": list(o.requires), "must not hold": list(o.not_held), "data missing": o.data_missing}})
        edges += [{"from": f"need:{n}", "to": f"offer:{o.id}", "label": "addressed by", "status": "plain", "path": False}
                  for n in o.addresses]
    for c in policy.channels.values():
        nodes.append({"id": f"ch:{c.id}", "col": 3, "kind": "channel", "label": c.id.replace("_", " "),
                      "sub": "needs " + c.consent.replace("_", " ") + (" + DOI" if c.needs_doi else "")
                      + (f" + {c.requires_field.replace('_', ' ')}" if c.requires_field else ""), "status": None,
                      "detail": {"consent": c.consent, "double opt-in": c.needs_doi, "also needs": c.requires_field}})
        edges.append({"from": f"ch:{c.id}", "to": f"consent:{c.consent}", "label": "requires", "status": "plain", "path": False})
    nodes.append({"id": f"ch:{policy.service_channel}", "col": 3, "kind": "channel", "label": "service agent",
                  "sub": "no marketing consent needed", "status": None, "detail": {"note": "service only, never sales content"}})
    edges.append({"from": "offer:P-SV-01", "to": f"ch:{policy.service_channel}", "label": "delivered via", "status": "plain", "path": False})
    for ctype in sorted({c.consent for c in policy.channels.values()} | {"profiling_analytics"}):
        nodes.append({"id": f"consent:{ctype}", "col": 4, "kind": "consent", "label": ctype.replace("_", " "),
                      "sub": "needed for personalised offers" if ctype == "profiling_analytics" else "consent_status",
                      "status": None, "detail": {"consent type": ctype}})
    return {"columns": ["Signals", "Needs", "Offers", "Channels", "Consent"], "nodes": nodes, "edges": edges}


def customer_view(rt, cid: str) -> dict:
    card, state, policy = rt.card(cid), rt.states[cid], rt.policy
    cons = consents(state, policy)
    tuples = []
    for c in card.candidates:
        v = c.valuation
        status = "chosen" if c.tuple_id == card.chosen.tuple_id else "waiting" if c.deferred_until else "alternative"
        tuples.append({"offer": c.offer_id, "channel": c.channel, "tone": c.tone, "status": status, "origin": c.origin,
                       "action_type": c.action_type, "need": c.need, "signals": c.signals,
                       "dclv": v.delta_clv, "p": v.p_accept, "confidence": v.confidence, "p_level": v.p_source.level,
                       "p_mode": v.p_source.mode, "n": v.p_source.n_treated, "conv": v.p_source.conv_treated,
                       "clv_now": v.clv_now_model, "clv_accept": v.clv_after_accept, "clv_reject": v.clv_after_reject,
                       "cost": v.contact_cost, "until": c.deferred_until, "why": c.why[:2], "notes": c.notes[:3]})
    blocked, wide, offer_blocks = [], [], []
    for b in card.blocked:
        row = {"offer": b.offer_id, "channel": b.channel, "rule": b.rule_id, "rc": b.rule_center_id, "reason": b.reason,
               "until": b.until, "dclv": b.counterfactual_delta_clv}
        if b.offer_id == "*":
            wide.append(row)
        elif b.channel is None and b.rule_id != "DATA-MISSING":
            offer_blocks.append(row)
        else:
            blocked.append(row)
    for b in blocked:  # offer x channel rows that the card shows as blocked or waiting
        if b["channel"] and not any(t["offer"] == b["offer"] and t["channel"] == b["channel"] for t in tuples):
            tuples.append({"offer": b["offer"], "channel": b["channel"], "status": "waiting" if b["until"] else "blocked",
                           "rule": b["rc"] or b["rule"], "reason": b["reason"], "until": b["until"], "dclv": b["dclv"]})
    tuples.sort(key=lambda t: (STATUS_ORDER[t["status"]], -(t.get("dclv") or 0), t["offer"], t["channel"] or ""))
    refs = {e for s in card.signals for e in s.evidence if not e.startswith("click:")}
    value, tri = card.profile.value_risk, card.triage
    chosen = next((t for t in tuples if t["status"] == "chosen"), None)
    return {
        "id": cid,
        "headline": {"archetype": f"{tri.archetype.id} {tri.archetype.name}", "urgency": tri.urgency_tier,
                     "urgency_reasons": tri.urgency_reasons[:3], "flags": [f.id for f in tri.flags],
                     "clv": value.clv_eur.v, "churn": value.churn_prob_12m.v, "lines": value.active_business_lines.v,
                     "tone": card.profile.header.tone.value, "profiled": cons["profiling_analytics"].effective_status == "granted"},
        "evidence": evidence_nodes(state, refs),
        "signals": [{"id": s.id, "label": s.label, "detail": s.detail, "date": s.date, "strength": s.strength,
                     "purpose": s.purpose, "needs": s.needs, "offers": s.offers, "evidence": s.evidence, "src": s.src}
                    for s in card.signals],
        "consents": [{"type": t, "status": c.status, "effective": c.effective_status, "doi": c.doi,
                      "updated_at": c.updated_at, "override": c.override_reason} for t, c in cons.items()],
        "channels": [{"channel": ch.channel, "allowed": ch.allowed, "reason": ch.reason, "consent": (ch.requires or [None])[0]}
                     for ch in card.profile.channels],
        "tuples": tuples, "wide": wide, "offer_blocks": offer_blocks,
        "chosen": {"tuple": card.chosen.tuple_id, "reason": card.chosen.reason_line, "send_at": card.chosen.send_at,
                   "until": card.chosen.deferred_until, "service": card.chosen.service_mode,
                   "subject": card.chosen.content.subject if card.chosen.content else None,
                   "template": card.chosen.content.template_id if card.chosen.content else None, "valuation": chosen},
        "path": [p.model_dump(exclude_none=True) for p in card.explanation_path],
        "rules": [r.model_dump(mode="json") for r in card.rules.results if r.result != "pass" or r.tier != "compliance"],
        "counter_line": card.rules.counter_line,
        "checklist": [{"item": k.item, "passed": k.passed, "detail": k.detail} for k in card.checklist],
    }


def export(rt, customer_ids) -> dict:
    policy, onto = rt.policy, yaml.safe_load((REPO / "kg" / "ontology.yaml").read_text(encoding="utf-8"))
    edges = []
    for etype, e in onto["edge_types"].items():
        srcs, dsts = e["from"] if isinstance(e["from"], list) else [e["from"]], e["to"] if isinstance(e["to"], list) else [e["to"]]
        edges += [{"type": etype, "from": a, "to": b, "note": e.get("note")} for a in srcs for b in dsts]
    business = [{"id": r.id, "name": r.name, "kind": r.kind, "effect": r.effect} for r in rt.cfg.rules]
    cards = rt.cards()
    return {
        "meta": {"eval_time": next(iter(rt.states.values())).eval_time.isoformat(), "customers": len(rt.states),
                 "rule_set_version": rt.cfg.versions(policy).rules, "workbook": "data/maingau_nba_mockdata.xlsx",
                 "act_now": sum(1 for c in cards if c.chosen.tuple_id != NO_ACTION and not c.chosen.deferred_until),
                 "waiting": sum(1 for c in cards if c.chosen.deferred_until),
                 "no_action": sum(1 for c in cards if c.chosen.tuple_id == NO_ACTION)},
        "ontology": ontology_graph(onto, edges),
        "policy_graph": policy_graph(policy),
        "policy": {
            "signals": [{"id": s.id, "label": s.label, "strength": s.strength, "purpose": s.purpose,
                         "indicates": list(s.indicates), "reinforces": list(s.reinforces)} for s in policy.signals.values()],
            "needs": [{"id": nid, "label": n["label_en"]} for nid, n in policy.needs.items()],
            "offers": [{"id": o.id, "name": o.name, "line": o.business_line, "action_type": o.action_type,
                        "generic": o.generic, "data_missing": o.data_missing, "addresses": list(o.addresses),
                        "requires": list(o.requires), "not_held": list(o.not_held)} for o in policy.offers.values()],
            "channels": [{"id": c.id, "consent": c.consent, "doi": c.needs_doi, "requires_field": c.requires_field}
                         for c in policy.channels.values()] + [{"id": policy.service_channel, "consent": None}],
            "exclusions": [{"id": e.id, "label": e.label, "blocks": list(e.blocks)} for e in policy.exclusions.values()],
            "compliance": [{"id": cid, **c} for cid, c in sorted(policy.compliance.items())],
            "business": business,
        },
        "customers": {cid: {**(v := customer_view(rt, cid)), "case": DEMO.get(cid, ""), "graph": customer_graph(v, policy)}
                      for cid in customer_ids},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--customers", default=",".join(DEMO))
    ap.add_argument("--out", type=Path, default=REPO / "out" / "kg_viz.json")
    args = ap.parse_args()
    rt = Runtime.load()
    ids = [c.strip() for c in args.customers.split(",") if c.strip()]
    unknown = [c for c in ids if c not in rt.states]
    if unknown:
        ap.error(f"unknown customers: {', '.join(unknown)}")
    data = export(rt, ids)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, default=str, separators=(",", ":")), encoding="utf-8")
    print(f"{len(ids)} customers -> {args.out} ({args.out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

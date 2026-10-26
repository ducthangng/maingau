import json
from pathlib import Path

from nba.build import build
from nba.contracts import CustomerCard, DecisionRequest, IndexRow, Summary
from nba.engine.config import load_config
from nba.engine.runtime import Runtime
from nba.profile import profile_population


def test_all_exports_validate_and_are_byte_identical(tmp_path, tables, states, policy):
    pop = profile_population(states)
    runtime = Runtime(tables, states, pop, policy, load_config(tables))
    first, second, export = tmp_path / 'first', tmp_path / 'second', tmp_path / 'static'
    export.mkdir()
    (export / 'manifest.json').write_text('{"mock":true}')
    cards, rows, totals = build(runtime, first, export_dir=export)
    assert len(cards) == len(rows) == totals.n_customers == 750
    assert (first / 'test_report.md').exists()
    assert (first / 'impact_report.md').exists()
    report = (first / 'test_report.md').read_text()
    assert '## Mode: rate' in report and '## Mode: uplift' in report and 'Sensitivity' in report
    # A fresh runtime, including fresh empirical aggregates, must produce the same bytes.
    fresh = Runtime(tables, states, pop, policy, load_config(tables))
    build(fresh, second, report=False)
    for file in first.rglob('*.json'):
        rel = file.relative_to(first)
        assert file.read_bytes() == (second / rel).read_bytes() == (export / rel).read_bytes()
        if rel.parts[0] == 'customers':
            CustomerCard.model_validate_json(file.read_text())
    assert len(list((export / 'customers').glob('*.json'))) == 750
    assert not (export / 'manifest.json').exists()
    assert sum(p.stat().st_size for p in export.rglob('*.json')) <= 20_000_000
    for card in cards:
        raw = runtime.card(card.customer_id)
        assert card.chosen == raw.chosen
        assert card.explanation_path == raw.explanation_path
        assert len({c.offer_id for c in card.candidates}) == len(card.candidates)
        detail_ids = {card.chosen.tuple_id, *(a.tuple_id for a in card.alternatives)}
        for candidate in card.candidates:
            original = next(c for c in raw.candidates if c.tuple_id == candidate.tuple_id)
            assert candidate.valuation == original.valuation
            if candidate.tuple_id in detail_ids:
                assert candidate.checks == original.checks and candidate.path == original.path
            else:
                assert candidate.checks == [] and candidate.path == []
    assert all(len(p.read_text().splitlines()) == 1 for p in export.rglob('*.json'))
    for row in json.loads((first / 'index.json').read_text()):
        IndexRow.model_validate(row)
    summary = Summary.model_validate_json((first / 'summary.json').read_text())
    assert summary.sources and summary.column_src and summary.value_date == '2026-09-30'
    assert summary.n_customers == sum(summary.archetype_counts.values())
    assert rows[0].urgency_tier == 'P1'
    for row in rows:
        if row.chosen_offer == 'NO_ACTION':
            assert row.delta_clv is None and row.p_accept is None


def test_all_four_schema_files_match_the_models():
    root = Path(__file__).resolve().parents[1] / 'docs' / 'schema'
    from nba.contracts import RuleChange, RuleCreate, RulesFile

    for name, model in [('customer_card', CustomerCard), ('index_row', IndexRow), ('summary', Summary), ('decision_request', DecisionRequest),
                        ('rules', RulesFile), ('rule_change', RuleChange), ('rule_create', RuleCreate)]:
        assert json.loads((root / f'{name}.schema.json').read_text()) == model.model_json_schema()

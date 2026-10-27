import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from nba.engine.config import load_config
from nba.engine.runtime import Runtime


@pytest.fixture
def client(tmp_path, tables, states, policy, pop):
    runtime = Runtime(tables, dict(states), pop, policy, load_config(tables))
    app = create_app(runtime=runtime, out_dir=tmp_path, kb_file=tmp_path / 'kg_viz.json')
    with TestClient(app) as client:
        yield client, runtime, tmp_path


def test_read_endpoints_and_filters(client):
    api, _, _ = client
    assert api.get('/api/customers/MG-100068').status_code == 200
    assert api.get('/api/customers/unknown').status_code == 404
    assert api.get('/api/summary').json()['n_customers'] == 750
    rows = api.get('/api/customers', params={'q': 'MG-100009', 'service_mode': True}).json()
    assert len(rows) == 1 and rows[0]['chosen_offer'] == 'P-SV-01'


def test_approve_override_reject_are_append_only(client):
    api, _, directory = client
    cid = 'MG-100068'
    approved = api.post(f'/api/customers/{cid}/decision', json={'action': 'approve', 'user': 'reviewer'})
    assert approved.status_code == 200 and approved.json()['action'] == 'approved'
    assert approved.json()['scores']['delta_clv'] > 0
    assert api.get(f'/api/customers/{cid}').json()['chosen']['status'] == 'approved'
    changed = api.post(f'/api/customers/{cid}/decision', json={'action': 'override', 'user': 'reviewer', 'reason': 'Channel choice',
                      'tuple': {'offer_id': 'P-EN-03', 'channel': 'email', 'tone': 'du'}})
    assert changed.status_code == 200
    shown = api.get(f'/api/customers/{cid}').json()
    assert shown['chosen']['tuple_id'] == 'P-EN-03|email|du' and shown['chosen']['content']['tone'] == 'du'
    assert api.post(f'/api/customers/{cid}/decision', json={'action': 'reject', 'user': 'reviewer'}).status_code == 422
    assert api.post(f'/api/customers/{cid}/decision', json={'action': 'reject', 'user': 'reviewer', 'reason': 'Not now'}).status_code == 200
    records = [json.loads(x) for x in (directory / 'decision_log.jsonl').read_text().splitlines()]
    assert len(records) == 3 and all(r['customer_id'] == cid for r in records)
    assert [r['entry']['action'] for r in records] == ['approved', 'overridden', 'rejected']
    assert api.get(f'/api/customers/{cid}').json()['chosen']['status'] == 'rejected'


@pytest.mark.parametrize('cid,ref,rule', [
    ('MG-100051', {'offer_id': 'P-EN-03', 'channel': 'email', 'tone': 'sie'}, 'CONSENT-CHANNEL'),
    ('MG-100096', {'offer_id': 'P-EN-03', 'channel': 'newsletter_email', 'tone': 'sie'}, 'EXCL-DUNNING'),
    ('MG-100112', {'offer_id': 'P-AS-01', 'channel': 'outbound_call', 'tone': 'sie'}, 'CONSENT-PROFILING'),
    ('MG-100112', {'offer_id': 'P-EN-01', 'channel': 'outbound_call', 'tone': 'du'}, 'CONSENT-PROFILING'),
    ('MG-100035', {'offer_id': 'P-SV-01', 'channel': 'service_agent', 'tone': 'sie'}, 'ECON-NONPOSITIVE'),
    ('MG-100023', {'offer_id': 'P-MO-01', 'channel': 'portal_popup', 'tone': 'sie'}, 'HOLDING-PRECONDITION'),
])
def test_overrides_cannot_bypass_gates(client, cid, ref, rule):
    api, _, directory = client
    response = api.post(f'/api/customers/{cid}/decision', json={'action': 'override', 'user': 'reviewer', 'tuple': ref})
    assert response.status_code == 409
    assert rule in response.json()['detail']['rule_ids']
    assert not (directory / 'decision_log.jsonl').exists()


def test_explicit_approval_does_not_silently_change_the_tuple(client):
    api, _, directory = client
    response = api.post('/api/customers/MG-100068/decision', json={'action': 'approve', 'user': 'reviewer',
                        'tuple': {'offer_id': 'P-EN-03', 'channel': 'email', 'tone': 'sie'}})
    current = api.get('/api/customers/MG-100068').json()['chosen']['tuple_id']
    assert current != 'P-EN-03|email|sie'
    assert response.status_code == 409
    assert not (directory / 'decision_log.jsonl').exists()


def test_cancellation_no_action_cannot_be_approved(client):
    api, _, directory = client
    response = api.post('/api/customers/MG-100035/decision', json={'action': 'approve', 'user': 'reviewer'})
    assert response.status_code == 409
    assert not (directory / 'decision_log.jsonl').exists()


def test_current_consent_is_rechecked_after_a_card_was_cached(client):
    api, runtime, directory = client
    cid = 'MG-100068'
    api.get(f'/api/customers/{cid}')
    state = runtime.states[cid]
    rows = {**state.rows, 'consent_status': [{**r, 'status': 'withdrawn'} if r['consent_type'] == 'marketing_email' else r
                                           for r in state.rows['consent_status']]}
    runtime.states[cid] = replace(state, rows=rows, revision='sha256:consent-withdrawn')
    response = api.post(f'/api/customers/{cid}/decision', json={'action': 'override', 'user': 'reviewer',
                        'tuple': {'offer_id': 'P-EN-03', 'channel': 'email', 'tone': 'sie'}})
    assert response.status_code == 409 and 'CONSENT-CHANNEL' in response.json()['detail']['rule_ids']
    assert not (directory / 'decision_log.jsonl').exists()


def test_replay_preview_redecides_affected_customers_without_mutating_snapshot(client):
    api, runtime, directory = client
    revisions = {cid: state.revision for cid, state in runtime.states.items()}
    response = api.post('/api/replay', params={'until': '2026-10-03T19:27:39'})
    assert response.status_code == 200
    result = response.json()
    assert result['preview_only'] is True and len(result['affected']) == 118
    assert result['pending_revocations']
    assert {card['customer_id'] for card in result['customers']} == set(result['affected'])
    assert all(card['meta']['events_applied_until'] == result['eval_time'] for card in result['customers'])
    assert any('EXCL-OPEN-TICKET' in row['revoked_by'] for row in result['pending_revocations'].values())
    # Cards deferred for the contact cap already wait for it; on this stream the cap alone revokes none of them.
    assert not any('CONTACT-CAP' in row['revoked_by'] for row in result['pending_revocations'].values())
    assert revisions == {cid: state.revision for cid, state in runtime.states.items()}
    assert not (directory / 'decision_log.jsonl').exists()
    assert api.post('/api/replay', params={'until': '2026-09-01T00:00:00'}).status_code == 422


def test_campaign_fast_forward_simulates_contacted_only_and_feeds_learning(client):
    api, runtime, directory = client
    rows = [r for r in api.get('/api/customers').json() if r['chosen_offer'] != 'NO_ACTION' and not r['service_mode']][:30]
    members = [{'customer_id': r['customer_id'], 'tuple_id': r['chosen_tuple'], 'holdout': i % 5 == 0} for i, r in enumerate(rows)]
    body = {'user': 'reviewer', 'members': members}
    assert api.get('/api/campaigns/CMP-1/outcomes').status_code == 404
    first = api.post('/api/campaigns/CMP-1/fast-forward', json=body).json()
    assert not first['already'] and first['totals']['control'] == 6 and first['totals']['simulated'] == 24
    for o in first['outcomes']:
        if o['status'] == 'control':
            assert 'actual_delta_clv' not in o
        else:
            assert o['status'] in {'bought', 'not_bought'}
            assert o['actual_delta_clv'] > o['expected_delta_clv'] if o['status'] == 'bought' else o['actual_delta_clv'] < o['expected_delta_clv']
    assert first['learned'] and all(x['k_after'] is not None for x in first['learned'])
    # Once per campaign; the same draw on every call, and the outcomes are in the history the engine learns from
    again = api.post('/api/campaigns/CMP-1/fast-forward', json=body).json()
    assert again['already'] and again['outcomes'] == first['outcomes']
    assert api.get('/api/campaigns/CMP-1/outcomes').json()['totals'] == first['totals']
    history = api.app.state.runtime.cfg.history
    assert sum(r['decision_source'] == 'campaign_fast_forward' for r in history) == 24
    assert len(history) == len(runtime.cfg.history) + 24
    assert len((directory / 'campaign_outcomes.jsonl').read_text().splitlines()) == 1
    # Every sent customer's outcome is remembered for that customer, so the next decision moves on; control is left alone
    memory = [json.loads(x) for x in (directory / 'customer_memory.jsonl').read_text().splitlines()]
    sent = {o['customer_id'] for o in first['outcomes'] if o['status'] != 'control'}
    assert {m['customer_id'] for m in memory} == sent and all(m['source'] == 'campaign_outcome' for m in memory)
    for m in members:
        now = api.get(f"/api/customers/{m['customer_id']}").json()['chosen']
        moved = (now['tuple_id'], now.get('deferred_until')) != (m['tuple_id'], None)
        assert moved == (m['customer_id'] in sent), m
    assert {x['customer_id'] for x in first['impact']} == sent


def test_knowledge_base_is_live(client):
    """GET /api/kb follows the API's state: after MG-100133 was sent their offer, the graph shows the new decision."""
    api, _, _ = client
    cid = 'MG-100133'
    before = api.get('/api/kb').json()['customers'][cid]['chosen']['tuple']
    assert before == api.get(f'/api/customers/{cid}').json()['chosen']['tuple_id']
    api.post('/api/campaigns/CMP-KB/fast-forward', json={'user': 'reviewer', 'members': [{'customer_id': cid, 'tuple_id': before}]})
    now = api.get(f'/api/customers/{cid}').json()['chosen']['tuple_id']
    assert now != before and api.get('/api/kb').json()['customers'][cid]['chosen']['tuple'] == now


def test_generate_knowledge_base_writes_the_static_file(client):
    api, _, directory = client
    assert not (directory / 'kg_viz.json').exists()
    made = api.post('/api/kb/generate').json()
    assert 'MG-100133' in made['customers']
    assert json.loads((directory / 'kg_viz.json').read_text())['customers'].keys() == made['customers'].keys()

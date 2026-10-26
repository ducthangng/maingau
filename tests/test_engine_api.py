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
    app = create_app(runtime=runtime, out_dir=tmp_path)
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
    assert revisions == {cid: state.revision for cid, state in runtime.states.items()}
    assert not (directory / 'decision_log.jsonl').exists()
    assert api.post('/api/replay', params={'until': '2026-09-01T00:00:00'}).status_code == 422

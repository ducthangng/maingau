from datetime import datetime
from dataclasses import replace

from nba.contracts import Candidate
from nba.engine.config import load_config
from nba.engine.content import render_content
from nba.engine.schedule import suggested_send_time


def test_every_offer_has_all_four_german_variants(tables):
    cfg = load_config(tables)
    for oid, offer in cfg.offers.items():
        for tone in ['du', 'sie']:
            c = Candidate(tuple_id=f'{oid}|email|{tone}', offer_id=oid, offer_name=offer['product_name'],
                          action_type=offer['action_type'], channel='email', tone=tone)
            for personalised in [True, False]:
                content = render_content(c, tone, personalised, template_dir=cfg.template_dir)
                assert content.language == 'de' and content.subject and content.body
                assert content.personalised == personalised
                assert not any(s in content.body.casefold() for s in ['nur heute', 'letzte chance', '€'])
                if not personalised:
                    assert 'Nicht personalisiert' in content.body
                if oid == 'P-SV-01':
                    assert 'leid' in content.body and not any(s in content.body for s in ['StromAktiv', 'Mobil', 'Autostrom', 'HEMS'])
                if tone == 'sie':
                    assert ' du ' not in content.body and ' dir' not in content.body


def test_dates_are_only_added_to_personalised_retention(states, tables):
    cfg = load_config(tables)
    c = Candidate(tuple_id='P-EN-02|email|sie', offer_id='P-EN-02', offer_name='StromGarant',
                  action_type='retention', channel='email', tone='sie')
    assert '08.10.2026' in render_content(c, 'sie', True, state=states['MG-100068'], template_dir=cfg.template_dir).body
    assert '08.10.2026' not in render_content(c, 'sie', False, state=states['MG-100068'], template_dir=cfg.template_dir).body


def test_send_times_skip_weekends(states, tables):
    cfg = load_config(tables)
    state = replace(states['MG-100068'], eval_time=datetime(2026, 10, 2, 10, 0))
    c = Candidate(tuple_id='P-EN-02|email|sie', offer_id='P-EN-02', offer_name='StromGarant', action_type='retention', channel='email', tone='sie')
    assert suggested_send_time(c, state, cfg) == '2026-10-05T10:00:00'
    assert suggested_send_time(c.model_copy(update={'channel': 'sms'}), state, cfg) == '2026-10-05T18:00:00'
    assert suggested_send_time(c.model_copy(update={'channel': 'app_push'}), state, cfg) == 'next login'

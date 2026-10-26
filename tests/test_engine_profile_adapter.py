import sys
import importlib
from types import ModuleType

from nba.contracts import Fact, TimelineItem, Tone
from nba.engine.assemble import assemble
from nba.engine.config import load_config
from nba.engine.profile_adapter import build_sections


def test_cards_builders_are_used_when_available(monkeypatch, states, tables, pop, policy):
    state, cfg = states['MG-100068'], load_config(tables)
    tone = Tone(value='du', method='text', evidence='Test customer-side text', refs=['ticket:test'])
    profile, _, _ = build_sections(state, pop, policy, tone)
    profile.header.city = Fact(v='Test city', src='customer_master.city')
    module = ModuleType('nba.profile')
    module.infer_tone = lambda state: tone
    module.build_profile = lambda state, pop: profile.model_copy(deep=True)
    module.build_timeline = lambda state: [TimelineItem(id='test', date='2026-09-30', kind='event', title='Test', src='customer_master.record_updated_at')]
    monkeypatch.setitem(sys.modules, 'nba.profile', module)
    card = assemble(state, pop, policy, cfg)
    assert card.profile.header.city.v == 'Test city'
    assert card.profile.header.tone.value == 'du'
    assert card.timeline[0].id == 'test'
    assert not any(q.code == 'PROFILE-PENDING' for q in card.data_quality)


def test_no_profiling_never_calls_the_tone_inference(monkeypatch, states, tables, pop, policy):
    state, cfg = states['MG-100112'], load_config(tables)
    module = ModuleType('nba.profile')
    def forbidden(state):
        raise AssertionError('Tone inference must not run without profiling consent')
    module.infer_tone = forbidden
    monkeypatch.setitem(sys.modules, 'nba.profile', module)
    card = assemble(state, pop, policy, cfg)
    assert card.profile.header.tone.value == 'sie'
    assert card.profile.header.tone.method == 'default'


def test_assemble_calls_the_public_kg_bundle_once(monkeypatch, states, tables, pop, policy):
    module = importlib.import_module('nba.engine.assemble')
    original, calls = module.kg_bundle, []
    def counted(*args, **kwargs):
        calls.append(args[0].customer_id)
        return original(*args, **kwargs)
    monkeypatch.setattr(module, 'kg_bundle', counted)
    card = assemble(states['MG-100068'], pop, policy, load_config(tables))
    assert calls == ['MG-100068']
    assert card.signals and card.candidates and card.legacy_comparison

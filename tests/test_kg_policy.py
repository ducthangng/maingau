"""Policy integrity (README §7.1 "Done when")."""

from nba.kg.policy import validate


def test_policy_is_valid(policy, tables):
    assert validate(policy, set(tables["product_catalog"]["product_id"])) == []


def test_policy_covers_catalog_and_spec(policy):
    assert len(policy.offers) == 18
    assert [s.id for s in policy.enabled_signals] == [f"S{i}" for i in range(1, 14)]
    assert policy.signals["S10"].reinforces and not policy.signals["S10"].indicates
    assert {o.id for o in policy.generic_offers} == {"P-EN-01", "P-MO-01", "P-SL-01", "P-SH-01", "P-SH-03", "P-SH-04"}
    assert policy.offers["P-EN-04"].data_missing and policy.offers["P-IN-01"].data_missing


def test_channel_consent_map(policy):
    assert {c.id: c.consent for c in policy.channels.values()} == {
        "newsletter_email": "newsletter_email", "email": "marketing_email", "outbound_call": "marketing_phone",
        "sms": "marketing_sms", "portal_popup": "portal_app_personalisation", "app_push": "portal_app_personalisation",
    }

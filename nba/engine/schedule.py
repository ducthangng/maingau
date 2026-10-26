"""Suggested contact times, relative to the supplied snapshot rather than wall time."""
from datetime import timedelta


def suggested_send_time(candidate, state, cfg):
    if candidate.channel in {"portal_popup", "app_push"}:
        return "next login"
    if candidate.channel == "service_agent":
        return "immediately, with the open ticket"
    day = state.eval_time.date() + timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    settings = cfg.settings["send_time"]
    hour = settings["sms_hour"] if candidate.channel == "sms" else int(settings["call_window"].split(":")[0]) if candidate.channel == "outbound_call" else settings["email_hour"]
    return f"{day.isoformat()}T{hour:02d}:00:00"

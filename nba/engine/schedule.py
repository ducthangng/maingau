"""Suggested contact times, relative to the supplied snapshot rather than wall time."""
from datetime import datetime, timedelta


def suggested_send_time(candidate, state, cfg, after: datetime | None = None):
    """`after`: a deferred action may not go out before this time (DEFER_UNTIL)."""
    if candidate.channel in {"portal_popup", "app_push"}:
        return f"next login after {after:%Y-%m-%d %H:%M}" if after else "next login"
    if candidate.channel == "service_agent":
        return "immediately, with the open ticket"
    settings = cfg.settings["send_time"]
    hour = settings["sms_hour"] if candidate.channel == "sms" else int(settings["call_window"].split(":")[0]) if candidate.channel == "outbound_call" else settings["email_hour"]
    day = after.date() if after else state.eval_time.date() + timedelta(days=1)
    while day.weekday() >= 5 or (after and datetime.combine(day, datetime.min.time()).replace(hour=hour) < after):
        day += timedelta(days=1)
    return f"{day.isoformat()}T{hour:02d}:00:00"

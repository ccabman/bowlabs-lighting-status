"""Bounded lighting-only scalar projection; no I/O or controller imports."""


class Refused(ValueError):
    pass


def integer(value, maximum=1000000000):
    if type(value) is not int or not 0 <= value <= maximum:
        raise Refused()
    return value


def boolean(value):
    if type(value) is not bool:
        raise Refused()
    return value


def obj(value):
    if type(value) is not dict:
        raise Refused()
    return value


def failure(value):
    if value is None:
        return False
    if type(value) is not str or len(value) > 1024:
        raise Refused()
    return bool(value)


def lighting(payload):
    data = obj(payload)
    zones = data.get("zones")
    if type(zones) is not list or len(zones) > 32:
        raise Refused()
    alerts = obj(data.get("alerts")).get("state")
    # HA sensor states are strings; accept only canonical bounded decimal counts.
    if type(alerts) is str and alerts.isascii() and alerts.isdecimal():
        if len(alerts) > 2 or str(int(alerts)) != alerts:
            raise Refused()
        alerts = int(alerts)
    alerts = integer(alerts, 32)
    held = overrides = errors = unavailable = adapting = 0
    allowed = {
        "Adapting",
        "Disabled",
        "Manual hold",
        "Scene/helper pause",
        "Membership error",
        "Curve error",
        "unavailable",
        "unknown",
    }
    for raw in zones:
        zone = obj(raw)
        state = zone.get("state")
        if type(state) is not str or state not in allowed:
            raise Refused()
        if state in {"unavailable", "unknown"}:
            unavailable += 1
            continue
        attrs = obj(zone.get("attributes"))
        holds = obj(attrs.get("holds"))
        if len(holds) > 128:
            raise Refused()
        held += len(holds)  # Never traverse or export hold keys/values.
        overrides += boolean(attrs.get("brightness_override"))
        errors += failure(attrs.get("error")) or state in {
            "Membership error",
            "Curve error",
        }
        adapting += state == "Adapting"
    details = {
        "zones": len(zones),
        "held_count": held,
        "active_alerts": alerts,
        "override_zones": overrides,
        "unavailable_zones": unavailable,
        "error_zones": errors,
    }
    if not zones:
        return "not_configured", "off", "not_checked", "none", details
    if unavailable == len(zones):
        return "unavailable", "unknown", "blocked", "source_unavailable", {}
    if errors or unavailable:
        return "available", "degraded", "limited", "lighting_issue", details
    return "available", "active" if adapting else "idle", "ready", "none", details

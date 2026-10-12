from django import template
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
register = template.Library()

@register.filter
def attr(obj, name):
    try:
        return getattr(obj, name)
    except (AttributeError, TypeError):
        return ""

@register.filter
def money(value):
    try:
        amount = Decimal(str(value if value is not None else 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sign = "-" if amount < 0 else ""
        whole, fraction = f"{abs(amount):.2f}".split(".")
        if len(whole) > 3:
            whole = f"{whole[:-3]},{whole[-3:]}"
            prefix, suffix = whole.rsplit(",", 1)
            while len(prefix) > 2:
                prefix, group = prefix[:-2], prefix[-2:]
                suffix = f"{group},{suffix}"
            whole = f"{prefix},{suffix}"
        return f"{sign}₹{whole}.{fraction}"
    except (InvalidOperation, ValueError, TypeError):
        return value

@register.filter
def status_class(value):
    val = str(value).lower().replace(" ", "_")
    return {"won": "green", "complete": "green", "resolved": "green", "done": "green", "qualified": "blue", "proposal": "purple", "contacted": "violet", "urgent": "red", "high": "orange", "lost": "red", "open": "blue", "active": "green", "in_progress": "violet", "waiting": "orange", "todo": "blue"}.get(val, "slate")

@register.filter
def humanize(value):
    return str(value).replace("_", " ").title()

@register.filter
def display_value(obj, name):
    method = getattr(obj, f"get_{name}_display", None)
    return method() if callable(method) else getattr(obj, name, "")

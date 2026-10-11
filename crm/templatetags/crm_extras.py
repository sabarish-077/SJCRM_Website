from django import template
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
        return f"${float(value):,.2f}" if value is not None else "$0.00"
    except (ValueError, TypeError):
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

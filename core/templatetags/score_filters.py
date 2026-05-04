from django import template

register = template.Library()


@register.filter
def score_display(value):
    """
    Display a score without unnecessary decimals.
    - None / empty  → '—'
    - Whole number  → integer string  e.g. 2.00 → '2'
    - Has decimals  → decimal string  e.g. 2.50 → '2.5'
    Does NOT touch the database value — display only.
    """
    if value is None:
        return '—'
    try:
        f = float(value)
    except (TypeError, ValueError):
        return '—'
    # Whole number check
    if f == int(f):
        return str(int(f))
    # Has a fractional part — strip trailing zeros
    return f'{f:g}'

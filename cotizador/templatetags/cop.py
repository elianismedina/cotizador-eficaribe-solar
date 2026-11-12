from django import template

register = template.Library()


@register.filter
def cop(valor):
    """1234567 → $1.234.567"""
    if valor in (None, ""):
        return ""
    n = round(float(valor))
    return ("-" if n < 0 else "") + "$" + f"{abs(n):,}".replace(",", ".")


@register.filter
def miles(valor):
    """1234567 → 1.234.567"""
    if valor in (None, ""):
        return ""
    return f"{round(float(valor)):,}".replace(",", ".")


@register.filter
def porcentaje(valor):
    """0.4258 → 43 %"""
    if valor in (None, ""):
        return ""
    return f"{round(float(valor) * 100)} %"

from django import template

register = template.Library()

@register.filter
def rupiah(value):
    try:
        return f"Rp {int(value):,}".replace(',', '.')
    except (ValueError, TypeError):
        return "-"
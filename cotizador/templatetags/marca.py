"""Colores de la marca como variables CSS, para que se cambien desde el panel sin recompilar estilos."""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


def _rgb(hex_color: str, defecto: str) -> str:
    valor = (hex_color or defecto).lstrip("#")
    if len(valor) != 6:
        valor = defecto.lstrip("#")
    return " ".join(str(int(valor[i:i + 2], 16)) for i in (0, 2, 4))


def _oscurecer(hex_color: str, defecto: str, factor: float = 0.82) -> str:
    return " ".join(str(int(int(c) * factor)) for c in _rgb(hex_color, defecto).split())


@register.simple_tag
def variables_marca(empresa) -> str:
    primario = getattr(empresa, "color_primario", "") or "#225816"
    secundario = getattr(empresa, "color_secundario", "") or "#FFC302"
    return mark_safe(
        f"<style>:root{{--marca:{_rgb(primario, '#225816')};--marca-oscuro:{_oscurecer(primario, '#225816')};"
        f"--marca-sol:{_rgb(secundario, '#FFC302')}}}</style>"
    )

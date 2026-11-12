"""Importa o actualiza productos desde el CSV que exporta Tiendanube (Productos > Exportar).

El CSV viene en Latin-1, separado por punto y coma, con precios como "199,900.00".
Cada producto se identifica por su "Identificador de URL": volver a importar actualiza
precio, nombre, marca y visibilidad, y conserva lo que se editó a mano en el panel
(categoría, IVA, potencia, costo, garantía).
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import transaction

from .models import Producto

C = Producto.Categoria
URL_TIENDA = "https://eficaribesolar.com/productos/{slug}/"

CATEGORIAS = [  # (texto en la categoría de Tiendanube, categoría del cotizador)
    ("panel", C.PANEL),
    ("inversor", C.INVERSOR),
    ("bater", C.BATERIA),
    ("estructura", C.ESTRUCTURA),
    ("cable", C.CABLEADO),
    ("protecci", C.PROTECCION_DC),
]
EXCLUIDOS_IVA = {C.PANEL, C.INVERSOR}


@dataclass
class Resumen:
    creados: list[str] = field(default_factory=list)
    actualizados: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)

    def __str__(self):
        return f"{len(self.creados)} creados, {len(self.actualizados)} actualizados, {len(self.errores)} con error"


def leer_csv(contenido: bytes) -> list[dict]:
    for codificacion in ("utf-8-sig", "latin-1"):
        try:
            texto = contenido.decode(codificacion)
            break
        except UnicodeDecodeError:
            continue
    return list(csv.DictReader(io.StringIO(texto), delimiter=";"))


def a_decimal(valor: str) -> Decimal | None:
    valor = (valor or "").strip().replace(",", "")
    if not valor:
        return None
    try:
        return Decimal(valor)
    except InvalidOperation:
        return None


def categoria_desde(texto: str) -> str:
    t = (texto or "").lower()
    for clave, cat in CATEGORIAS:
        if clave in t:
            return cat
    return C.OTRO


def potencia_w(nombre: str) -> Decimal | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(kW|W)\b", nombre, re.I)
    if not m:
        return None
    valor = Decimal(m.group(1).replace(",", "."))
    return valor * 1000 if m.group(2).lower() == "kw" else valor


def capacidad_kwh(nombre: str) -> Decimal | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*kWh", nombre, re.I)
    return Decimal(m.group(1).replace(",", ".")) if m else None


def precio_sin_iva(precio: Decimal, iva: str, precios_con_iva: bool) -> Decimal:
    if precios_con_iva and iva == Producto.Iva.GRAVADO:
        precio = precio / Decimal("1.19")
    return precio.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


@transaction.atomic
def importar(contenido: bytes, precios_con_iva: bool = True) -> Resumen:
    resumen = Resumen()
    for n, fila in enumerate(leer_csv(contenido), start=2):
        slug = (fila.get("Identificador de URL") or "").strip()
        nombre = (fila.get("Nombre") or "").strip()
        precio = a_decimal(fila.get("Precio"))
        if not slug or not nombre:
            continue  # filas de variantes sin nombre propio
        if precio is None:
            resumen.errores.append(f"Fila {n} ({nombre}): sin precio")
            continue

        visible = (fila.get("Mostrar en mi tienda en línea") or "").strip().upper() in {"SÍ", "SI"}
        visible = visible and "oculto" not in (fila.get("Visibilidad") or "").lower()
        costo = a_decimal(fila.get("Costo"))

        producto = Producto.objects.filter(slug_tiendanube=slug).first()
        nuevo = producto is None
        if nuevo:
            categoria = categoria_desde(fila.get("Categorías"))
            producto = Producto(
                slug_tiendanube=slug,
                categoria=categoria,
                iva=Producto.Iva.EXCLUIDO if categoria in EXCLUIDOS_IVA else Producto.Iva.GRAVADO,
                potencia_w=potencia_w(nombre) if categoria in {C.PANEL, C.INVERSOR} else None,
                capacidad_kwh=capacidad_kwh(nombre) if categoria == C.BATERIA else None,
            )
        producto.nombre = nombre[:200]
        producto.marca = (fila.get("Marca") or "").strip()[:80] or producto.marca
        producto.modelo = (fila.get("SKU") or "").strip()[:120] or producto.modelo
        producto.precio = precio_sin_iva(precio, producto.iva, precios_con_iva)
        if costo:
            producto.costo = precio_sin_iva(costo, producto.iva, precios_con_iva)
        producto.url_tienda = URL_TIENDA.format(slug=slug)
        producto.activo = visible
        producto.save()
        (resumen.creados if nuevo else resumen.actualizados).append(nombre)
    return resumen

"""Arma los datos de la propuesta formal (estructura de COT-2026-1987) y genera el PDF."""
from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import timedelta
from itertools import groupby

from django.template.loader import render_to_string

from catalogo.models import Producto
from configuracion.models import Empresa, ParametrosFinancieros, PlantillaCondiciones
from cotizador.motor.dimensionamiento import generacion_anual
from cotizador.motor.financiero import ResultadoFinanciero, Supuestos, analizar, deduccion_renta

from .models import Cotizacion, ItemCotizacion

ANIOS_FLUJO = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 15, 20, 25]
TARIFAS_SENSIBILIDAD = [900, 1000, 1150, 1300]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_larga(fecha) -> str:
    return f"{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"


@dataclass
class Escenario:
    nombre: str
    corto: str
    resultado: ResultadoFinanciero


def _parametro(cot: Cotizacion, clave: str, defecto: float) -> float:
    """Un supuesto guardado en la cotización tiene prioridad sobre el parámetro general."""
    valor = (cot.supuestos or {}).get(clave)
    return float(valor) if valor not in (None, "") else float(defecto)


def construir_contexto(cot: Cotizacion) -> dict:
    empresa = Empresa.actual()
    p = ParametrosFinancieros.vigentes()
    plantilla = PlantillaCondiciones.objects.filter(por_defecto=True).first()
    items = list(cot.items.select_related("producto"))

    grupos = [
        {"nombre": dict(ItemCotizacion.Grupo.choices).get(clave, clave), "items": list(lista)}
        for clave, lista in groupby(
            sorted(items, key=lambda i: (list(ItemCotizacion.Grupo.values).index(i.grupo), i.orden, i.pk)),
            key=lambda i: i.grupo,
        )
    ]

    rendimiento = _parametro(cot, "rendimiento", p.rendimiento_sistema)
    autoconsumo = _parametro(cot, "autoconsumo", p.autoconsumo)
    pct_instalacion = _parametro(cot, "porcentaje_instalacion", p.porcentaje_instalacion_estimada)
    kwp = float(cot.potencia_kwp)
    energia = generacion_anual(kwp, float(cot.hsp), rendimiento) if kwp else 0.0

    def total_categoria(cat):
        return float(sum(i.total for i in items if i.producto.categoria == cat))

    reposiciones = {}
    if total_categoria(Producto.Categoria.INVERSOR):
        reposiciones[p.anio_reposicion_inversor] = total_categoria(Producto.Categoria.INVERSOR)
    if total_categoria(Producto.Categoria.BATERIA):
        anio = p.anio_reposicion_baterias
        reposiciones[anio] = reposiciones.get(anio, 0) + total_categoria(Producto.Categoria.BATERIA)

    def supuestos(tarifa=None, auto=None):
        return Supuestos(
            tarifa_kwh=float(tarifa or cot.tarifa_kwh),
            autoconsumo=auto if auto is not None else autoconsumo,
            incremento_tarifa=float(p.incremento_tarifa),
            degradacion=float(p.degradacion_paneles),
            om_porcentaje=float(p.om_porcentaje),
            om_incremento=float(p.om_incremento),
            tasa_descuento=float(p.tasa_descuento),
            horizonte_anios=p.horizonte_anios,
            reposiciones=reposiciones,
        )

    valor_total = float(cot.valor_total)
    total_equipos = float(cot.total_equipos)
    incluye_instalacion = cot.alcance != Cotizacion.Alcance.SUMINISTRO
    inversiones = [("Propuesta" if incluye_instalacion else "Propuesta (equipos + flete)", "propuesta", valor_total)]
    if not incluye_instalacion:
        inversiones.append(("Equipos + flete + instalación (est.)", "con instalación",
                            valor_total + total_equipos * pct_instalacion))

    escenarios, sensibilidad, flujo = [], [], []
    if energia and valor_total:
        escenarios = [Escenario(n, c, analizar(inv, energia, supuestos())) for n, c, inv in inversiones]
        flujo = [f for f in escenarios[0].resultado.flujo if f.anio in ANIOS_FLUJO]
        tarifa_base = float(cot.tarifa_kwh)
        filas = sorted(set(TARIFAS_SENSIBILIDAD + [round(tarifa_base)]))
        for t in filas:
            sensibilidad.append({
                "etiqueta": f"${t:,.0f}/kWh".replace(",", ".") + (" (base)" if t == round(tarifa_base) else ""),
                "base": t == round(tarifa_base),
                "valores": [analizar(inv, energia, supuestos(tarifa=t)).recuperacion_texto for _, _, inv in inversiones],
            })
        auto_bajo = round(autoconsumo - 0.10, 2)
        sensibilidad.append({
            "etiqueta": f"${tarifa_base:,.0f}/kWh con {auto_bajo * 100:.0f} % de autoconsumo".replace(",", "."),
            "base": False,
            "valores": [analizar(inv, energia, supuestos(auto=auto_bajo)).recuperacion_texto for _, _, inv in inversiones],
        })

    paneles = [i for i in items if i.producto.categoria == Producto.Categoria.PANEL]
    inversores = [i for i in items if i.producto.categoria == Producto.Categoria.INVERSOR]
    baterias = [i for i in items if i.producto.categoria == Producto.Categoria.BATERIA]
    hay_excluidos = any(i.tasa_iva == 0 for i in items)

    return {
        "empresa": empresa,
        "cot": cot,
        "cliente": cot.prospecto.cliente,
        "fecha": fecha_larga(cot.fecha),
        "vence": fecha_larga(cot.fecha + timedelta(days=cot.validez_dias)),
        "grupos": grupos,
        "paneles": paneles,
        "inversores": inversores,
        "baterias": baterias,
        "kwp": kwp,
        "kwh_baterias": float(cot.capacidad_baterias_kwh),
        "energia_anual": energia,
        "energia_mensual": energia / 12,
        "hay_excluidos": hay_excluidos,
        "incluye_instalacion": incluye_instalacion,
        "escenarios": escenarios,
        "flujo": flujo,
        "anio_recuperacion": next((f.anio for f in flujo if f.anio and f.flujo_acumulado >= 0), None),
        "sensibilidad": sensibilidad,
        "supuestos": {
            "tarifa": float(cot.tarifa_kwh),
            "hsp": float(cot.hsp),
            "rendimiento": rendimiento,
            "autoconsumo": autoconsumo,
            "incremento_tarifa": float(p.incremento_tarifa),
            "degradacion": float(p.degradacion_paneles),
            "degradacion_texto": f"{float(p.degradacion_paneles) * 100:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " %",
            "om": float(p.om_porcentaje),
            "om_incremento": float(p.om_incremento),
            "tasa_descuento": float(p.tasa_descuento),
            "horizonte": p.horizonte_anios,
            "reposiciones": sorted(reposiciones),
            "anio_inversor": p.anio_reposicion_inversor if inversores else None,
            "anio_baterias": p.anio_reposicion_baterias if baterias else None,
            "pct_instalacion": pct_instalacion,
        },
        "deduccion_renta": deduccion_renta(total_equipos, float(p.tarifa_renta)),
        "tarifa_renta": float(p.tarifa_renta),
        "co2_ton_anio": energia * float(p.factor_emision_kg_kwh) / 1000,
        "condiciones": {
            "forma_pago": cot.forma_pago or (plantilla.forma_pago if plantilla else PlantillaCondiciones._meta.get_field("forma_pago").default),
            "tiempo_entrega": cot.tiempo_entrega or (plantilla.tiempo_entrega if plantilla else PlantillaCondiciones._meta.get_field("tiempo_entrega").default),
            "financiacion": plantilla.opciones_financiacion if plantilla else PlantillaCondiciones._meta.get_field("opciones_financiacion").default,
            "garantias": cot.garantias or garantias_desde_productos(items),
            "nota": plantilla.nota_estimaciones if plantilla else PlantillaCondiciones._meta.get_field("nota_estimaciones").default,
        },
    }


def garantias_desde_productos(items) -> str:
    partes = [f"{i.producto.nombre}: {i.producto.garantia_anios} años"
              for i in items if i.producto.garantia_anios]
    resto = "demás equipos según las condiciones de cada fabricante"
    return "; ".join(partes + [resto]) + "." if partes else resto[0].upper() + resto[1:] + "."


def generar_pdf(cot: Cotizacion) -> bytes:
    from xhtml2pdf import pisa

    html = render_to_string("ventas/propuesta.html", construir_contexto(cot))
    salida = io.BytesIO()
    resultado = pisa.CreatePDF(html, dest=salida, encoding="utf-8")
    if resultado.err:
        raise RuntimeError("No se pudo generar el PDF de la propuesta")
    return salida.getvalue()

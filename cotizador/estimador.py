"""Estimado en línea para el cotizador público.

Une el motor de cálculo (Python puro) con los parámetros guardados en la base de datos.
El resultado es un diccionario serializable para guardarlo en la sesión y en la cotización.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal

from configuracion.models import Irradiacion, ParametrosFinancieros, PrecioReferencia
from cotizador.motor.dimensionamiento import dimensionar
from cotizador.motor.financiero import Supuestos, analizar


@dataclass(frozen=True)
class Solicitud:
    segmento: str  # "residencial" | "comercial"
    tipo_sistema: str  # "on_grid" | "hibrido"
    zona_id: int
    consumo_kwh: float
    valor_factura: float | None = None


def estimar(sol: Solicitud) -> dict:
    p = ParametrosFinancieros.vigentes()
    zona = Irradiacion.objects.get(pk=sol.zona_id)
    hsp = float(zona.hsp)
    rendimiento = float(p.rendimiento_sistema)

    if sol.valor_factura:
        tarifa = sol.valor_factura / sol.consumo_kwh
        tarifa_origen = "factura"
    else:
        ref = p.tarifa_referencia_comercial if sol.segmento == "comercial" else p.tarifa_referencia_residencial
        tarifa = float(ref)
        tarifa_origen = "referencia"

    dim = dimensionar(
        consumo_mensual_kwh=sol.consumo_kwh,
        hsp=hsp,
        rendimiento=rendimiento,
        potencia_panel_w=p.potencia_panel_referencia_w,
    )

    precio_ref = PrecioReferencia.para(sol.tipo_sistema, Decimal(str(dim.potencia_real_kwp)))
    precio = precio_min = precio_max = None
    recuperacion = tir = None
    if precio_ref:
        wp = dim.potencia_real_kwp * 1000
        precio = wp * float(precio_ref.precio_por_wp)
        precio_min, precio_max = wp * float(precio_ref.precio_min_wp), wp * float(precio_ref.precio_max_wp)
        fin = analizar(
            precio,
            dim.generacion_anual_kwh,
            Supuestos(
                tarifa_kwh=tarifa,
                autoconsumo=float(p.autoconsumo),
                incremento_tarifa=float(p.incremento_tarifa),
                degradacion=float(p.degradacion_paneles),
                om_porcentaje=float(p.om_porcentaje),
                om_incremento=float(p.om_incremento),
                tasa_descuento=float(p.tasa_descuento),
                horizonte_anios=p.horizonte_anios,
                consumo_anual_kwh=sol.consumo_kwh * 12,
            ),
        )
        recuperacion = fin.recuperacion_texto
        tir = fin.tir

    energia_ahorrada = min(dim.generacion_anual_kwh * float(p.autoconsumo), sol.consumo_kwh * 12)
    ahorro_anual = energia_ahorrada * tarifa
    return {
        "solicitud": asdict(sol),
        "zona": str(zona.zona),
        "departamento": str(zona.departamento),
        "hsp": hsp,
        "rendimiento": rendimiento,
        "tarifa_kwh": round(tarifa, 2),
        "tarifa_origen": tarifa_origen,
        "potencia_kwp": round(dim.potencia_real_kwp, 2),
        "num_paneles": dim.num_paneles,
        "potencia_panel_w": p.potencia_panel_referencia_w,
        "area_m2": round(dim.area_m2, 1),
        "generacion_mensual_kwh": round(dim.generacion_mensual_kwh),
        "cobertura": round(min(dim.generacion_mensual_kwh / sol.consumo_kwh, 9.99), 3),
        "ahorro_mensual": round(ahorro_anual / 12),
        "ahorro_anual": round(ahorro_anual),
        "precio_estimado": round(precio) if precio else None,
        "precio_min": round(precio_min) if precio_min else None,
        "precio_max": round(precio_max) if precio_max else None,
        "recuperacion": recuperacion,
        "tir": round(tir, 4) if tir is not None else None,
        "co2_ton_anio": round(dim.generacion_anual_kwh * float(p.factor_emision_kg_kwh) / 1000, 1),
    }

"""Dimensionamiento de sistemas fotovoltaicos."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ResultadoDimensionamiento:
    potencia_kwp: float
    num_paneles: int
    potencia_real_kwp: float
    generacion_anual_kwh: float
    generacion_mensual_kwh: float
    area_m2: float


def generacion_anual(potencia_kwp: float, hsp: float, rendimiento: float) -> float:
    """Energía generada en el año 1 (kWh): P × HSP × 365 × PR."""
    return potencia_kwp * hsp * 365 * rendimiento


def dimensionar(
    consumo_mensual_kwh: float,
    hsp: float,
    rendimiento: float = 0.78,
    cobertura: float = 1.0,
    potencia_panel_w: float = 630,
    area_panel_m2: float = 2.6,
) -> ResultadoDimensionamiento:
    """Calcula la potencia necesaria para cubrir `cobertura` del consumo."""
    if consumo_mensual_kwh <= 0 or hsp <= 0 or rendimiento <= 0:
        raise ValueError("Consumo, HSP y rendimiento deben ser positivos")
    potencia = consumo_mensual_kwh * 12 * cobertura / (hsp * 365 * rendimiento)
    paneles = math.ceil(round(potencia * 1000 / potencia_panel_w, 6))
    potencia_real = paneles * potencia_panel_w / 1000
    anual = generacion_anual(potencia_real, hsp, rendimiento)
    return ResultadoDimensionamiento(
        potencia_kwp=potencia,
        num_paneles=paneles,
        potencia_real_kwp=potencia_real,
        generacion_anual_kwh=anual,
        generacion_mensual_kwh=anual / 12,
        area_m2=paneles * area_panel_m2,
    )

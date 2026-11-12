"""Análisis financiero: flujo de caja, recuperación, TIR, VPN y beneficios tributarios.

Reproduce la metodología de la cotización COT-2026-1987:
- Ahorro = energía × autoconsumo × tarifa; la energía no autoconsumida no se valora.
- La tarifa sube un % anual y los paneles se degradan un % anual.
- O&M = % de la inversión en el año 1, con incremento anual.
- Reposiciones (inversor, baterías) en años configurables, a precios actuales.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Supuestos:
    tarifa_kwh: float
    autoconsumo: float = 0.90
    incremento_tarifa: float = 0.05
    degradacion: float = 0.004
    om_porcentaje: float = 0.01
    om_incremento: float = 0.03
    tasa_descuento: float = 0.10
    horizonte_anios: int = 25
    # {año: valor} de reposiciones a precios actuales
    reposiciones: dict[int, float] = field(default_factory=dict)
    # Si se indica, el ahorro anual no supera este consumo (no se promete más que la factura).
    consumo_anual_kwh: float | None = None


@dataclass(frozen=True)
class FilaFlujo:
    anio: int
    energia_kwh: float
    ahorro: float
    om_y_reposiciones: float
    flujo_neto: float
    flujo_acumulado: float


@dataclass(frozen=True)
class ResultadoFinanciero:
    inversion: float
    flujo: list[FilaFlujo]
    ahorro_anio1: float
    recuperacion_anios: float | None
    tir: float | None
    vpn: float
    beneficio_acumulado: float

    @property
    def recuperacion_texto(self) -> str:
        return formatear_recuperacion(self.recuperacion_anios)


def flujo_de_caja(inversion: float, energia_anio1_kwh: float, s: Supuestos) -> list[FilaFlujo]:
    filas = [FilaFlujo(0, 0.0, 0.0, 0.0, -inversion, -inversion)]
    acumulado = -inversion
    om_base = inversion * s.om_porcentaje
    for anio in range(1, s.horizonte_anios + 1):
        energia = energia_anio1_kwh * (1 - s.degradacion) ** (anio - 1)
        tarifa = s.tarifa_kwh * (1 + s.incremento_tarifa) ** (anio - 1)
        energia_ahorrada = energia * s.autoconsumo
        if s.consumo_anual_kwh is not None:
            energia_ahorrada = min(energia_ahorrada, s.consumo_anual_kwh)
        ahorro = energia_ahorrada * tarifa
        costos = om_base * (1 + s.om_incremento) ** (anio - 1) + s.reposiciones.get(anio, 0.0)
        neto = ahorro - costos
        acumulado += neto
        filas.append(FilaFlujo(anio, energia, ahorro, -costos, neto, acumulado))
    return filas


def periodo_recuperacion(flujo: list[FilaFlujo]) -> float | None:
    """Años (con fracción lineal) hasta que el flujo acumulado deja de ser negativo."""
    for previa, fila in zip(flujo, flujo[1:]):
        if previa.flujo_acumulado < 0 <= fila.flujo_acumulado:
            return previa.anio + (-previa.flujo_acumulado / fila.flujo_neto)
    return None


def vpn(flujos: list[float], tasa: float) -> float:
    return sum(f / (1 + tasa) ** t for t, f in enumerate(flujos))


def tir(flujos: list[float], bajo: float = -0.99, alto: float = 10.0, iteraciones: int = 200) -> float | None:
    """TIR por bisección; None si no hay cambio de signo."""
    f_bajo, f_alto = vpn(flujos, bajo), vpn(flujos, alto)
    if f_bajo * f_alto > 0:
        return None
    for _ in range(iteraciones):
        medio = (bajo + alto) / 2
        f_medio = vpn(flujos, medio)
        if f_bajo * f_medio <= 0:
            alto = medio
        else:
            bajo, f_bajo = medio, f_medio
    return (bajo + alto) / 2


def analizar(inversion: float, energia_anio1_kwh: float, s: Supuestos) -> ResultadoFinanciero:
    flujo = flujo_de_caja(inversion, energia_anio1_kwh, s)
    netos = [f.flujo_neto for f in flujo]
    return ResultadoFinanciero(
        inversion=inversion,
        flujo=flujo,
        ahorro_anio1=flujo[1].ahorro,
        recuperacion_anios=periodo_recuperacion(flujo),
        tir=tir(netos),
        vpn=vpn(netos, s.tasa_descuento),
        beneficio_acumulado=flujo[-1].flujo_acumulado,
    )


def formatear_recuperacion(anios: float | None) -> str:
    """'2 años y 6 meses'. Los meses se redondean al más cercano, como en COT-2026-1987."""
    if anios is None:
        return "No se recupera en el horizonte analizado"
    total_meses = round(anios * 12)
    a, m = divmod(total_meses, 12)
    partes = []
    if a:
        partes.append(f"{a} año" + ("s" if a != 1 else ""))
    if m:
        partes.append(f"{m} mes" + ("es" if m != 1 else ""))
    return " y ".join(partes) or "Menos de 1 mes"


def deduccion_renta(valor_inversion: float, tarifa_renta: float = 0.35, porcentaje: float = 0.50) -> float:
    """Ahorro máximo en impuestos por la deducción de la Ley 1715 de 2014 (art. 11)."""
    return valor_inversion * porcentaje * tarifa_renta

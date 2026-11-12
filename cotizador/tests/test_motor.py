"""El motor debe reproducir la cotización COT-2026-1987 (Timbiquí, 23,94 kWp híbrido)."""
from unittest import TestCase

from cotizador.motor.dimensionamiento import dimensionar, generacion_anual
from cotizador.motor.financiero import Supuestos, analizar, deduccion_renta, formatear_recuperacion

INVERSION = 63_101_523  # equipos con IVA + flete hasta Buenaventura
TOTAL_EQUIPOS = 59_301_523
INVERSION_CON_INSTALACION = 74_961_828  # + 20 % de los equipos
REPOSICIONES = {13: 18_285_000, 15: 14_202_293}  # inversor y baterías, precios actuales


def supuestos(tarifa=1150, autoconsumo=0.90):
    return Supuestos(tarifa_kwh=tarifa, autoconsumo=autoconsumo, reposiciones=REPOSICIONES)


class DimensionamientoTests(TestCase):
    def test_generacion_cot_2026_1987(self):
        energia = generacion_anual(23.94, hsp=3.5, rendimiento=0.78)
        self.assertEqual(round(energia), 23_855)
        self.assertEqual(round(energia / 12), 1_988)

    def test_dimensionar_redondea_paneles_hacia_arriba(self):
        r = dimensionar(consumo_mensual_kwh=1_980, hsp=3.5, rendimiento=0.78, potencia_panel_w=630)
        self.assertEqual(r.num_paneles, 38)
        self.assertAlmostEqual(r.potencia_real_kwp, 23.94)

    def test_dimensionar_rechaza_valores_invalidos(self):
        with self.assertRaises(ValueError):
            dimensionar(consumo_mensual_kwh=0, hsp=4)


class FinancieroTests(TestCase):
    def setUp(self):
        self.energia = generacion_anual(23.94, 3.5, 0.78)

    def test_resultados_escenario_propuesta(self):
        r = analizar(INVERSION, self.energia, supuestos())
        self.assertEqual(round(r.ahorro_anio1), 24_689_938)
        self.assertEqual(r.recuperacion_texto, "2 años y 6 meses")
        self.assertEqual(round(r.tir * 100), 43)
        self.assertAlmostEqual(r.vpn, 247_662_405, delta=2)
        self.assertEqual(round(r.beneficio_acumulado), 993_792_362)

    def test_resultados_escenario_con_instalacion(self):
        r = analizar(INVERSION_CON_INSTALACION, self.energia, supuestos())
        self.assertEqual(r.recuperacion_texto, "3 años")
        self.assertEqual(round(r.tir * 100), 36)
        self.assertAlmostEqual(r.vpn, 234_435_196, delta=2)
        self.assertEqual(round(r.beneficio_acumulado), 977_607_878)

    def test_flujo_de_caja(self):
        flujo = analizar(INVERSION, self.energia, supuestos()).flujo
        esperado = {  # año: (energía, ahorro, O&M y reposiciones, acumulado)
            1: (23_855, 24_689_938, -631_015, -39_042_600),
            2: (23_760, 25_820_738, -649_946, -13_871_808),
            3: (23_665, 27_003_327, -669_444, 12_462_076),
            13: (22_735, 42_257_486, -19_184_677, 334_586_809),
            15: (22_553, 46_216_913, -15_156_760, 408_913_173),
            25: (21_667, 72_324_811, -1_282_724, 993_792_362),
        }
        for anio, (energia, ahorro, costos, acumulado) in esperado.items():
            fila = flujo[anio]
            with self.subTest(anio=anio):
                self.assertEqual(round(fila.energia_kwh), energia)
                self.assertAlmostEqual(fila.ahorro, ahorro, delta=1)
                self.assertAlmostEqual(fila.om_y_reposiciones, costos, delta=1)
                self.assertAlmostEqual(fila.flujo_acumulado, acumulado, delta=2)

    def test_sensibilidad(self):
        casos = [  # (tarifa, autoconsumo, propuesta, con instalación)
            (900, 0.90, "3 años y 2 meses", "3 años y 9 meses"),
            (1000, 0.90, "2 años y 11 meses", "3 años y 5 meses"),
            (1150, 0.90, "2 años y 6 meses", "3 años"),
            (1300, 0.90, "2 años y 3 meses", "2 años y 8 meses"),
            (1150, 0.80, "2 años y 10 meses", "3 años y 4 meses"),
        ]
        for tarifa, auto, prop, inst in casos:
            with self.subTest(tarifa=tarifa, autoconsumo=auto):
                s = supuestos(tarifa, auto)
                self.assertEqual(analizar(INVERSION, self.energia, s).recuperacion_texto, prop)
                self.assertEqual(analizar(INVERSION_CON_INSTALACION, self.energia, s).recuperacion_texto, inst)

    def test_deduccion_renta(self):
        self.assertEqual(round(deduccion_renta(TOTAL_EQUIPOS)), 10_377_767)

    def test_formato_recuperacion(self):
        self.assertEqual(formatear_recuperacion(1.0), "1 año")
        self.assertEqual(formatear_recuperacion(1 + 1 / 12), "1 año y 1 mes")
        self.assertEqual(formatear_recuperacion(None), "No se recupera en el horizonte analizado")

"""La propuesta generada debe reproducir las cifras de COT-2026-1987."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalogo.models import Producto
from ventas.models import Cliente, Cotizacion, ItemCotizacion, Prospecto
from ventas.propuesta import construir_contexto, generar_pdf

from .test_cotizacion import ITEMS_COT_2026_1987


class PropuestaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cliente = Cliente.objects.create(nombre="Leyder Balanta", tipo=Cliente.Tipo.COMERCIAL)
        cls.cot = Cotizacion.objects.create(
            prospecto=Prospecto.objects.create(cliente=cliente),
            hsp=Decimal("3.5"), tarifa_kwh=Decimal("1150"), ubicacion="Timbiquí, Cauca",
            tipo_sistema=Cotizacion.TipoSistema.HIBRIDO, alcance=Cotizacion.Alcance.SUMINISTRO,
            flete=Decimal("3800000"), descripcion_flete="Flete de los equipos hasta Buenaventura",
            configuracion_strings="MPPT1: 2 × 7 paneles · MPPT2: 2 × 6 paneles · MPPT3: 2 × 6 paneles",
        )
        for orden, (nombre, cat, unidad, iva, cant, precio, w, kwh) in enumerate(ITEMS_COT_2026_1987):
            producto = Producto.objects.create(
                nombre=nombre, categoria=cat, unidad=unidad, iva=iva, precio=precio, potencia_w=w, capacidad_kwh=kwh,
            )
            ItemCotizacion.objects.create(cotizacion=cls.cot, producto=producto, cantidad=cant, orden=orden)

    def test_escenarios_coinciden_con_cot_2026_1987(self):
        ctx = construir_contexto(self.cot)
        propuesta, instalada = (e.resultado for e in ctx["escenarios"])
        self.assertEqual(round(propuesta.inversion), 63_101_523)
        self.assertEqual(round(instalada.inversion), 74_961_828)
        self.assertEqual(round(propuesta.ahorro_anio1), 24_689_938)
        self.assertEqual(propuesta.recuperacion_texto, "2 años y 6 meses")
        self.assertEqual(instalada.recuperacion_texto, "3 años")
        self.assertEqual(round(propuesta.tir * 100), 43)
        self.assertEqual(round(propuesta.beneficio_acumulado), 993_792_362)
        self.assertEqual(round(ctx["deduccion_renta"]), 10_377_767)
        self.assertEqual(round(ctx["energia_anual"]), 23_855)
        self.assertEqual(ctx["anio_recuperacion"], 3)
        self.assertEqual([f.anio for f in ctx["flujo"]], [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 15, 20, 25])

    def test_sensibilidad(self):
        filas = {s["etiqueta"]: s["valores"] for s in construir_contexto(self.cot)["sensibilidad"]}
        self.assertEqual(filas["$1.000/kWh"], ["2 años y 11 meses", "3 años y 5 meses"])
        self.assertEqual(filas["$1.150/kWh (base)"], ["2 años y 6 meses", "3 años"])
        self.assertEqual(filas["$1.150/kWh con 80 % de autoconsumo"], ["2 años y 10 meses", "3 años y 4 meses"])

    def test_grupos_en_orden(self):
        nombres = [g["nombre"] for g in construir_contexto(self.cot)["grupos"]]
        self.assertEqual(nombres, [
            "Equipos principales", "Estructura, cableado y canalización",
            "Protecciones DC", "Protecciones AC y puesta a tierra",
        ])

    def test_genera_pdf(self):
        pdf = generar_pdf(self.cot)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 5_000)

    def test_llave_en_mano_tiene_un_escenario(self):
        self.cot.alcance = Cotizacion.Alcance.LLAVE_EN_MANO
        self.assertEqual(len(construir_contexto(self.cot)["escenarios"]), 1)

    def test_vista_solo_para_el_equipo(self):
        url = reverse("ventas:propuesta_pdf", args=[self.cot.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        staff = get_user_model().objects.create_user("eli", password="x", is_staff=True)
        self.client.force_login(staff)
        r = self.client.get(url)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertIn(self.cot.numero, r["Content-Disposition"])

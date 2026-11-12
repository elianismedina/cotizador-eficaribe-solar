from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from configuracion.models import Irradiacion, PrecioReferencia
from ventas.models import Cotizacion, Prospecto


class EstimadorTests(TestCase):
    def setUp(self):
        self.zona = Irradiacion.objects.get(zona__startswith="Costa pacífica del Cauca")

    def test_estimado_con_factura(self):
        from cotizador.estimador import Solicitud, estimar

        e = estimar(Solicitud("comercial", "hibrido", self.zona.pk, consumo_kwh=1980, valor_factura=2_277_000))
        self.assertEqual(e["num_paneles"], 38)
        self.assertEqual(e["potencia_kwp"], 23.94)
        self.assertEqual(e["tarifa_kwh"], 1150)
        self.assertEqual(e["tarifa_origen"], "factura")
        self.assertEqual(e["generacion_mensual_kwh"], 1988)
        self.assertEqual(e["precio_estimado"], round(23_940 * 2970))
        self.assertLess(e["precio_min"], e["precio_estimado"])
        self.assertGreater(e["precio_max"], e["precio_estimado"])
        self.assertIsNotNone(e["recuperacion"])

    def test_ahorro_no_supera_la_factura(self):
        from cotizador.estimador import Solicitud, estimar

        barranquilla = Irradiacion.objects.get(zona__startswith="Barranquilla")
        e = estimar(Solicitud("residencial", "on_grid", barranquilla.pk, consumo_kwh=350, valor_factura=315_000))
        self.assertGreater(e["generacion_mensual_kwh"] * 0.9, 350)  # el sistema genera más de lo que se consume
        self.assertEqual(e["ahorro_mensual"], 315_000)

    def test_sin_precio_de_referencia(self):
        from cotizador.estimador import Solicitud, estimar

        PrecioReferencia.objects.all().delete()
        e = estimar(Solicitud("residencial", "on_grid", self.zona.pk, consumo_kwh=300))
        self.assertIsNone(e["precio_estimado"])
        self.assertEqual(e["tarifa_origen"], "referencia")


@override_settings(EMAIL_NOTIFICACIONES=["equipo@example.com"])
class FlujoPublicoTests(TestCase):
    def setUp(self):
        self.zona = Irradiacion.objects.get(zona__startswith="Barranquilla")

    def calcular(self, **extra):
        datos = {"segmento": "residencial", "tipo_sistema": "on_grid", "zona": self.zona.pk, "consumo_kwh": 350}
        datos.update(extra)
        return self.client.post(reverse("cotizador:inicio") + "?utm_source=tiendanube", datos)

    def test_formulario_carga(self):
        r = self.client.get(reverse("cotizador:inicio"))
        self.assertContains(r, "Calcular mi sistema")

    def test_resultado_sin_estimado_redirige(self):
        r = self.client.get(reverse("cotizador:resultado"))
        self.assertRedirects(r, reverse("cotizador:inicio"))

    def test_flujo_completo_crea_prospecto_y_avisa(self):
        self.client.get(reverse("cotizador:inicio") + "?utm_source=tiendanube&utm_campaign=banner")
        r = self.calcular(valor_factura=315_000)
        self.assertRedirects(r, reverse("cotizador:resultado"))
        r = self.client.get(reverse("cotizador:resultado"))
        self.assertContains(r, "kWp")
        self.assertContains(r, "calculada con tu factura")

        r = self.client.post(reverse("cotizador:resultado"), {
            "nombre": "Ana Pérez", "telefono": "3001234567", "correo": "ana@example.com",
            "ciudad": "Barranquilla", "acepta": "on", "sitio_web": "",
        })
        self.assertRedirects(r, reverse("cotizador:gracias"))
        cot = Cotizacion.objects.get()
        self.assertEqual(cot.prospecto.origen, Prospecto.Origen.COTIZADOR_WEB)
        self.assertEqual(cot.prospecto.utm_source, "tiendanube")
        self.assertEqual(cot.prospecto.utm_campaign, "banner")
        self.assertEqual(cot.prospecto.cliente.nombre, "Ana Pérez")
        self.assertTrue(cot.prospecto.cliente.acepta_tratamiento_datos)
        self.assertIn("potencia_kwp", cot.resultados)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(cot.numero, mail.outbox[0].subject)
        r = self.client.get(reverse("cotizador:gracias"))
        self.assertContains(r, cot.numero)

    def test_factura_incoherente(self):
        r = self.calcular(consumo_kwh=350, valor_factura=10_000_000)
        self.assertContains(r, "no parecen coincidir")

    def test_sin_autorizacion_no_crea(self):
        self.calcular()
        r = self.client.post(reverse("cotizador:resultado"), {
            "nombre": "X", "telefono": "1", "correo": "x@example.com", "ciudad": "Y",
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Cotizacion.objects.exists())

    def test_campo_trampa_bloquea_bots(self):
        self.calcular()
        self.client.post(reverse("cotizador:resultado"), {
            "nombre": "Bot", "telefono": "1", "correo": "b@example.com", "ciudad": "Y",
            "acepta": "on", "sitio_web": "http://spam",
        })
        self.assertFalse(Cotizacion.objects.exists())

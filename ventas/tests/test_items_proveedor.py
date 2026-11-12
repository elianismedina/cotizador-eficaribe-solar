"""Ítems de proveedor que no están en el catálogo: costo en COP o USD, margen e IVA por categoría."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from catalogo.models import Producto
from configuracion.models import ParametrosFinancieros
from ventas.models import Cliente, Cotizacion, ItemCotizacion, Prospecto

C = Producto.Categoria


def crear_cotizacion(tipo=Cliente.Tipo.RESIDENCIAL, **kwargs):
    cliente = Cliente.objects.create(nombre="Cliente", tipo=tipo)
    return Cotizacion.objects.create(prospecto=Prospecto.objects.create(cliente=cliente), hsp=Decimal("4.5"),
                                     tarifa_kwh=Decimal("900"), **kwargs)


class ItemsDeProveedorTests(TestCase):
    def test_costo_en_pesos_con_margen_residencial_por_defecto(self):
        cot = crear_cotizacion()
        item = ItemCotizacion.objects.create(
            cotizacion=cot, descripcion="Inversor Growatt 5 kW", categoria=C.INVERSOR, cantidad=1,
            proveedor="Proveedor A", costo_unitario=Decimal("3000000"),
        )
        self.assertEqual(item.margen, Decimal("0.25"))
        self.assertEqual(item.precio_unitario, Decimal("3750000"))
        self.assertEqual(item.tasa_iva, Decimal("0"))  # inversores excluidos
        self.assertEqual(item.grupo, ItemCotizacion.Grupo.EQUIPOS)

    def test_margen_comercial_y_iva_gravado(self):
        cot = crear_cotizacion(tipo=Cliente.Tipo.COMERCIAL)
        item = ItemCotizacion.objects.create(
            cotizacion=cot, descripcion="Estructura coplanar", categoria=C.ESTRUCTURA, cantidad=4,
            costo_unitario=Decimal("200000"),
        )
        self.assertEqual(item.precio_unitario, Decimal("230000"))
        self.assertEqual(item.tasa_iva, Decimal("0.19"))
        self.assertEqual(item.iva, Decimal("174800"))

    def test_margen_por_defecto_editable_en_parametros(self):
        ParametrosFinancieros.objects.create(margen_residencial=Decimal("0.30"))
        cot = crear_cotizacion()
        item = ItemCotizacion.objects.create(cotizacion=cot, descripcion="Breaker", categoria=C.PROTECCION_AC,
                                             cantidad=1, costo_unitario=Decimal("100000"))
        self.assertEqual(item.precio_unitario, Decimal("130000"))

    def test_costo_en_dolares_usa_la_trm_y_se_recalcula(self):
        cot = crear_cotizacion(trm=Decimal("4000"))
        item = ItemCotizacion.objects.create(
            cotizacion=cot, descripcion="Panel Jinko 620 W", categoria=C.PANEL, potencia_w=620, cantidad=10,
            costo_unitario=Decimal("80"), moneda=ItemCotizacion.Moneda.USD, margen=Decimal("0.20"),
        )
        self.assertEqual(item.precio_unitario, Decimal("384000"))
        self.assertEqual(cot.potencia_kwp, Decimal("6.2"))

        cot.trm = Decimal("4200")
        cot.save()
        cot.recalcular_precios()
        item.refresh_from_db()
        self.assertEqual(item.precio_unitario, Decimal("403200"))

    def test_utilidad(self):
        cot = crear_cotizacion()
        ItemCotizacion.objects.create(cotizacion=cot, descripcion="Inversor", categoria=C.INVERSOR, cantidad=2,
                                      costo_unitario=Decimal("1000000"), margen=Decimal("0.25"))
        self.assertEqual(cot.utilidad(), (Decimal("2000000"), Decimal("500000")))

    def test_validaciones(self):
        cot = crear_cotizacion()
        with self.assertRaises(ValidationError) as ctx:
            ItemCotizacion(cotizacion=cot, cantidad=1).full_clean()
        self.assertTrue({"descripcion", "categoria", "costo_unitario"} <= set(ctx.exception.message_dict))
        with self.assertRaises(ValidationError) as ctx:
            ItemCotizacion(cotizacion=cot, descripcion="Panel", categoria=C.PANEL, cantidad=1,
                           costo_unitario=Decimal("80"), moneda=ItemCotizacion.Moneda.USD).full_clean()
        self.assertIn("moneda", ctx.exception.message_dict)

    def test_producto_del_catalogo_sigue_funcionando(self):
        cot = crear_cotizacion()
        panel = Producto.objects.create(nombre="Panel 630 W", categoria=C.PANEL, precio=400000,
                                        iva=Producto.Iva.EXCLUIDO, potencia_w=630, garantia_anios=12)
        item = ItemCotizacion.objects.create(cotizacion=cot, producto=panel, cantidad=2)
        self.assertEqual((item.descripcion, item.categoria, item.precio_unitario), ("Panel 630 W", C.PANEL, 400000))
        self.assertEqual(item.garantia_anios, 12)
        self.assertEqual(cot.potencia_kwp, Decimal("1.26"))

    def test_pdf_con_items_de_proveedor(self):
        cot = crear_cotizacion()
        ItemCotizacion.objects.create(cotizacion=cot, descripcion="Panel Jinko 620 W", categoria=C.PANEL,
                                      potencia_w=620, cantidad=8, costo_unitario=Decimal("350000"))
        ItemCotizacion.objects.create(cotizacion=cot, descripcion="Inversor Growatt 5 kW", categoria=C.INVERSOR,
                                      cantidad=1, costo_unitario=Decimal("3000000"), garantia_anios=10)
        User.objects.create_user("eli", password="x", is_staff=True)
        self.client.login(username="eli", password="x")
        respuesta = self.client.get(reverse("ventas:propuesta_pdf", args=[cot.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.content.startswith(b"%PDF"))


class AdminTrmTests(TestCase):
    def test_cambiar_trm_en_el_admin_recalcula(self):
        cot = crear_cotizacion(trm=Decimal("4000"))
        item = ItemCotizacion.objects.create(cotizacion=cot, descripcion="Panel", categoria=C.PANEL, cantidad=1,
                                             costo_unitario=Decimal("100"), moneda="USD", margen=Decimal("0"))
        User.objects.create_superuser("admin", password="x")
        self.client.login(username="admin", password="x")
        url = reverse("admin:ventas_cotizacion_change", args=[cot.pk])
        form = self.client.get(url).context["adminform"].form
        datos = {k: v for k, v in form.initial.items() if v is not None}
        datos.update({
            "trm": "4100", "fecha": cot.fecha.isoformat(), "prospecto": cot.prospecto_id,
            "items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "1", "items-MIN_NUM_FORMS": "0", "items-MAX_NUM_FORMS": "1000",
            "items-0-id": item.pk, "items-0-cotizacion": cot.pk, "items-0-descripcion": "Panel", "items-0-categoria": "panel",
            "items-0-cantidad": "1", "items-0-costo_unitario": "100", "items-0-moneda": "USD", "items-0-margen": "0",
            "items-0-precio_unitario": "400000", "items-0-tasa_iva": "0", "items-0-orden": "0",
        })
        respuesta = self.client.post(url, datos)
        self.assertEqual(respuesta.status_code, 302, getattr(respuesta, "context", None) and respuesta.context["errors"])
        item.refresh_from_db()
        self.assertEqual(item.precio_unitario, Decimal("410000"))

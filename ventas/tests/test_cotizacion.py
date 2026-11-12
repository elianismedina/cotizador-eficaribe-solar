"""Los totales de una cotización deben coincidir con COT-2026-1987."""
from decimal import Decimal

from django.test import TestCase

from catalogo.models import Producto
from ventas.models import Cliente, Cotizacion, ItemCotizacion, Prospecto

C = Producto.Categoria
EXCL, GRAV = Producto.Iva.EXCLUIDO, Producto.Iva.GRAVADO

ITEMS_COT_2026_1987 = [
    # (nombre, categoría, unidad, IVA, cantidad, valor unitario, potencia W, capacidad kWh)
    ("Panel solar Risen 630 W", C.PANEL, "und", EXCL, 38, 427_800, 630, None),
    ("Inversor híbrido SRNE 18 kW", C.INVERSOR, "und", EXCL, 1, 18_285_000, 18_000, None),
    ("Batería SRNE SR-SE10B", C.BATERIA, "und", GRAV, 2, 5_967_350, None, Decimal("10.49")),
    ("Estructura de montaje", C.ESTRUCTURA, "kit", GRAV, 10, 405_882, None, None),
    ("Cable solar 6 mm² (rojo/negro)", C.CABLEADO, "m", GRAV, 360, 6_325, None, None),
    ("Conectores MC4 (par)", C.CABLEADO, "par", GRAV, 10, 4_590, None, None),
    ('Tubo conduit PVC 3/4" x 3 m (paquete x10)', C.CABLEADO, "paquete", GRAV, 2, 55_857, None, None),
    ('Curva conduit 90° x 3/4"', C.CABLEADO, "und", GRAV, 10, 1_498, None, None),
    ("Breaker DC 2P 600 VDC 50 A", C.PROTECCION_DC, "und", GRAV, 3, 47_256, None, None),
    ("DPS DC 600 VDC con RETIE", C.PROTECCION_DC, "und", GRAV, 3, 94_706, None, None),
    ("Breaker DC baterías 2P 160 A", C.PROTECCION_DC, "und", GRAV, 2, 449_370, None, None),
    ("Cable de batería 1/0 AWG LSHF", C.PROTECCION_DC, "m", GRAV, 8, 46_803, None, None),
    ("Tablero riel DIN 12 puestos IP65 (DC)", C.PROTECCION_DC, "und", GRAV, 1, 132_173, None, None),
    ("Breaker AC 3P 63 A", C.PROTECCION_AC, "und", GRAV, 2, 54_359, None, None),
    ("DPS AC 3P/4P 240 V Tipo 2 20/40 kA", C.PROTECCION_AC, "und", GRAV, 1, 142_871, None, None),
    ("Tablero riel DIN 12 puestos IP65 (AC)", C.PROTECCION_AC, "und", GRAV, 1, 132_173, None, None),
    ("Varilla puesta a tierra cobre 2,4 m", C.PROTECCION_AC, "und", GRAV, 1, 148_727, None, None),
]


class CotizacionTotalesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cliente = Cliente.objects.create(nombre="Cliente de prueba", tipo=Cliente.Tipo.COMERCIAL)
        prospecto = Prospecto.objects.create(cliente=cliente)
        cls.cot = Cotizacion.objects.create(
            prospecto=prospecto, hsp=Decimal("3.5"), tarifa_kwh=Decimal("1150"),
            tipo_sistema=Cotizacion.TipoSistema.HIBRIDO, flete=Decimal("3800000"),
        )
        for orden, (nombre, cat, unidad, iva, cant, precio, w, kwh) in enumerate(ITEMS_COT_2026_1987):
            producto = Producto.objects.create(
                nombre=nombre, categoria=cat, unidad=unidad, iva=iva, precio=precio, potencia_w=w, capacidad_kwh=kwh,
            )
            ItemCotizacion.objects.create(cotizacion=cls.cot, producto=producto, cantidad=cant, orden=orden)

    def test_totales(self):
        self.assertEqual(self.cot.subtotal, Decimal("55348226"))
        self.assertEqual(self.cot.total_iva, Decimal("3953297"))
        self.assertEqual(self.cot.total_equipos, Decimal("59301523"))
        self.assertEqual(self.cot.valor_total, Decimal("63101523"))

    def test_iva_por_linea(self):
        bateria = self.cot.items.get(producto__categoria=C.BATERIA)
        self.assertEqual(bateria.iva, Decimal("2267593"))
        panel = self.cot.items.get(producto__categoria=C.PANEL)
        self.assertEqual(panel.iva, Decimal("0"))

    def test_potencia_y_grupo(self):
        self.assertEqual(self.cot.potencia_kwp, Decimal("23.94"))
        cable = self.cot.items.get(descripcion__startswith="Cable solar")
        self.assertEqual(cable.grupo, ItemCotizacion.Grupo.ESTRUCTURA)

    def test_precio_congelado(self):
        panel = self.cot.items.get(producto__categoria=C.PANEL)
        Producto.objects.filter(pk=panel.producto_id).update(precio=999_999)
        panel.refresh_from_db()
        self.assertEqual(panel.precio_unitario, Decimal("427800"))


class NumeracionTests(TestCase):
    def test_consecutivo_por_anio(self):
        prospecto = Prospecto.objects.create(cliente=Cliente.objects.create(nombre="X"))
        datos = dict(prospecto=prospecto, hsp=4, tarifa_kwh=900)
        a = Cotizacion.objects.create(**datos)
        b = Cotizacion.objects.create(**datos)
        anio = a.fecha.year
        self.assertEqual(a.numero, f"COT-{anio}-0001")
        self.assertEqual(b.numero, f"COT-{anio}-0002")

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from catalogo.importar import importar
from catalogo.models import Producto

ENCABEZADO = ('"Identificador de URL";Nombre;Categorías;Precio;"Precio promocional";Stock;SKU;'
              '"Mostrar en mi tienda en línea";Descripción;Marca;Costo;Visibilidad\n')
FILAS = [
    'panel-630w;"Panel Solar Bifacial Tipo N 630W";"Paneles Solares";480,000.00;;10;;SÍ;"<p>Panel; bifacial</p>";Risen Energy;;Visible\n',
    'bateria-5kwh;"Batería de Litio 5.0kWh 24V Felicity Solar";"Baterias Litio";5,950,000.00;;3;FLB;SÍ;"<p>Batería</p>";Felicity Solar;0.00;Visible\n',
    'inversor-1kw;"Inversor Solar Aislado 1kW 12V";"Inversores offgrid";1,250,000.00;;2;;SÍ;"<p>Línea 1\nLínea 2</p>";Felicity Solar;;Visible\n',
    'lampara;"Lámpara LED Recargable";"Iluminación Solar";40,000.00;;5;;NO;"";;;Oculto\n',
]


def csv_bytes(filas=FILAS, codificacion="latin-1"):
    return (ENCABEZADO + "".join(filas)).encode(codificacion)


class ImportarTests(TestCase):
    def test_importa_y_mapea(self):
        resumen = importar(csv_bytes())
        self.assertEqual(len(resumen.creados), 4)
        panel = Producto.objects.get(slug_tiendanube="panel-630w")
        self.assertEqual(panel.categoria, Producto.Categoria.PANEL)
        self.assertEqual(panel.iva, Producto.Iva.EXCLUIDO)
        self.assertEqual(panel.potencia_w, Decimal("630"))
        self.assertEqual(panel.precio, Decimal("480000"))
        self.assertEqual(panel.url_tienda, "https://eficaribesolar.com/productos/panel-630w/")

        bateria = Producto.objects.get(slug_tiendanube="bateria-5kwh")
        self.assertEqual(bateria.categoria, Producto.Categoria.BATERIA)
        self.assertEqual(bateria.capacidad_kwh, Decimal("5.0"))
        self.assertEqual(bateria.precio, Decimal("5000000"))  # 5.950.000 / 1,19

        inversor = Producto.objects.get(slug_tiendanube="inversor-1kw")
        self.assertEqual(inversor.potencia_w, Decimal("1000"))
        self.assertFalse(Producto.objects.get(slug_tiendanube="lampara").activo)

    def test_precios_sin_iva(self):
        importar(csv_bytes(), precios_con_iva=False)
        self.assertEqual(Producto.objects.get(slug_tiendanube="bateria-5kwh").precio, Decimal("5950000"))

    def test_reimportar_actualiza_y_conserva_ajustes(self):
        importar(csv_bytes())
        panel = Producto.objects.get(slug_tiendanube="panel-630w")
        panel.garantia_anios = 12
        panel.iva = Producto.Iva.GRAVADO
        panel.save()
        filas = [FILAS[0].replace("480,000.00", "450,000.00")]
        resumen = importar(csv_bytes(filas))
        self.assertEqual(resumen.actualizados, ["Panel Solar Bifacial Tipo N 630W"])
        panel.refresh_from_db()
        self.assertEqual(panel.garantia_anios, 12)
        self.assertEqual(panel.iva, Producto.Iva.GRAVADO)
        self.assertEqual(panel.precio, Decimal("378151"))  # gravado: 450.000 / 1,19
        self.assertEqual(Producto.objects.count(), 4)

    def test_acepta_utf8(self):
        self.assertEqual(len(importar(csv_bytes(codificacion="utf-8")).creados), 4)

    def test_fila_sin_precio(self):
        resumen = importar(csv_bytes(['x;"Producto X";Otros;;;1;;SÍ;"";;;Visible\n']))
        self.assertEqual(len(resumen.errores), 1)

    def test_subida_desde_el_panel(self):
        admin = get_user_model().objects.create_superuser("eli", "eli@example.com", "x")
        self.client.force_login(admin)
        url = reverse("admin:catalogo_producto_importar")
        self.assertContains(self.client.get(url), "Importar productos desde Tiendanube")
        r = self.client.post(url, {"archivo": SimpleUploadedFile("t.csv", csv_bytes()), "precios_con_iva": "on"})
        self.assertRedirects(r, reverse("admin:catalogo_producto_changelist"))
        self.assertEqual(Producto.objects.count(), 4)

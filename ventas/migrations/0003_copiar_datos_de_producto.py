"""Copia a los ítems existentes los datos del producto que ahora se guardan en el ítem."""
from django.db import migrations

GRUPO = {"panel": "equipos", "inversor": "equipos", "bateria": "equipos", "estructura": "estructura",
         "cableado": "estructura", "proteccion_dc": "proteccion_dc", "proteccion_ac": "proteccion_ac",
         "servicio": "servicios"}


def copiar(apps, schema_editor):
    Item = apps.get_model("ventas", "ItemCotizacion")
    for item in Item.objects.select_related("producto").exclude(producto=None):
        p = item.producto
        item.categoria = item.categoria or p.categoria
        item.unidad = item.unidad or p.unidad
        item.unidad_detalle = item.unidad_detalle or p.unidad_detalle
        item.potencia_w = item.potencia_w if item.potencia_w is not None else p.potencia_w
        item.capacidad_kwh = item.capacidad_kwh if item.capacidad_kwh is not None else p.capacidad_kwh
        item.garantia_anios = item.garantia_anios if item.garantia_anios is not None else p.garantia_anios
        item.grupo = item.grupo or GRUPO.get(item.categoria, "equipos")
        item.save()


class Migration(migrations.Migration):
    dependencies = [("ventas", "0002_items_de_proveedor"), ("catalogo", "0002_slug_tiendanube")]
    operations = [migrations.RunPython(copiar, migrations.RunPython.noop)]

from django.contrib import admin

from .models import Producto


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "marca", "precio", "iva", "activo", "actualizado")
    list_filter = ("categoria", "iva", "activo", "marca")
    search_fields = ("nombre", "marca", "modelo", "id_tiendanube")
    list_editable = ("precio", "activo")

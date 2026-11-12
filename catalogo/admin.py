from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path

from .importar import importar
from .models import Producto


class ImportarForm(forms.Form):
    archivo = forms.FileField(label="CSV exportado de Tiendanube")
    precios_con_iva = forms.BooleanField(
        label="Los precios de la tienda incluyen IVA", required=False, initial=True,
        help_text="Si está marcado, a los productos gravados se les descuenta el 19 % para guardar el precio sin IVA.",
    )


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "marca", "precio", "iva", "potencia_w", "capacidad_kwh", "activo", "actualizado")
    list_filter = ("categoria", "iva", "activo", "marca")
    search_fields = ("nombre", "marca", "modelo", "id_tiendanube", "slug_tiendanube")
    list_editable = ("precio", "activo")
    change_list_template = "admin/catalogo/producto/change_list.html"

    def get_urls(self):
        propias = [path("importar/", self.admin_site.admin_view(self.importar_view), name="catalogo_producto_importar")]
        return propias + super().get_urls()

    def importar_view(self, request):
        form = ImportarForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            resumen = importar(form.cleaned_data["archivo"].read(), form.cleaned_data["precios_con_iva"])
            messages.success(request, f"Importación terminada: {resumen}.")
            for e in resumen.errores:
                messages.warning(request, e)
            if resumen.creados:
                messages.info(request, "Revisa la categoría, el IVA y la potencia de los productos nuevos.")
            return redirect("admin:catalogo_producto_changelist")
        contexto = {**self.admin_site.each_context(request), "form": form, "opts": self.model._meta,
                    "title": "Importar productos desde Tiendanube"}
        return render(request, "admin/catalogo/producto/importar.html", contexto)

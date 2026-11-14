from django.contrib import admin
from django.contrib.humanize.templatetags.humanize import intcomma
from django.urls import reverse
from django.utils.html import format_html

from .models import Cliente, Cotizacion, ItemCotizacion, Prospecto


def pesos(valor):
    return f"${intcomma(int(valor)).replace(',', '.')}"


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "ciudad", "telefono", "correo", "creado")
    list_filter = ("tipo", "departamento")
    search_fields = ("nombre", "documento", "correo", "telefono")


@admin.register(Prospecto)
class ProspectoAdmin(admin.ModelAdmin):
    list_display = ("cliente", "estado", "origen", "responsable", "proximo_contacto", "creado")
    list_filter = ("estado", "origen", "responsable")
    search_fields = ("cliente__nombre",)
    autocomplete_fields = ("cliente",)


class ItemInline(admin.TabularInline):
    model = ItemCotizacion
    extra = 1
    autocomplete_fields = ("producto",)
    fields = ("orden", "producto", "descripcion", "categoria", "potencia_w", "capacidad_kwh", "cantidad",
              "proveedor", "costo_unitario", "moneda", "margen", "precio_unitario", "tasa_iva", "garantia_anios")


@admin.register(Cotizacion)
class CotizacionAdmin(admin.ModelAdmin):
    list_display = ("numero", "cliente", "tipo_sistema", "alcance", "estado", "fecha", "valor_total_cop", "pdf")
    list_filter = ("estado", "tipo_sistema", "alcance", "tipo_techo")
    search_fields = ("numero", "prospecto__cliente__nombre")
    readonly_fields = ("numero", "resumen_totales", "pdf")
    inlines = [ItemInline]
    fieldsets = (
        (None, {"fields": ("numero", "pdf", "prospecto", "fecha", "validez_dias", "estado", "trm")}),
        ("Proyecto", {"fields": ("tipo_sistema", "alcance", "ubicacion", "tipo_techo", "objeto", "exclusiones")}),
        ("Datos técnicos", {"fields": ("consumo_mensual_kwh", "hsp", "configuracion_strings", "cargas_respaldadas", "red_electrica")}),
        ("Condiciones comerciales", {"fields": ("flete", "descripcion_flete", "lugar_entrega", "forma_pago", "tiempo_entrega", "garantias")}),
        ("Análisis financiero", {"fields": ("tarifa_kwh", "supuestos", "resultados")}),
        ("Totales", {"fields": ("resumen_totales",)}),
    )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if change and "trm" in form.changed_data:
            form.instance.recalcular_precios()

    @admin.display(description="Cliente")
    def cliente(self, obj):
        return obj.prospecto.cliente

    @admin.display(description="Valor total")
    def valor_total_cop(self, obj):
        return pesos(obj.valor_total)

    @admin.display(description="Resumen")
    def resumen_totales(self, obj):
        if not obj.pk:
            return "Guarda la cotización para ver los totales"
        return (
            f"Subtotal {pesos(obj.subtotal)} · IVA {pesos(obj.total_iva)} · "
            f"Equipos {pesos(obj.total_equipos)} · Flete {pesos(obj.flete)} · Total {pesos(obj.valor_total)} · "
            f"{obj.potencia_kwp:.2f} kWp · {obj.capacidad_baterias_kwh:.2f} kWh"
            + self._texto_utilidad(obj)
        )

    @staticmethod
    def _texto_utilidad(obj) -> str:
        datos = obj.utilidad()
        if not datos:
            return ""
        costo, utilidad = datos
        return f" · Costo proveedores {pesos(costo)} · Utilidad {pesos(utilidad)} (solo ítems con costo; no sale en el PDF)"

    @admin.display(description="Propuesta")
    def pdf(self, obj):
        if not obj.pk:
            return "Guarda la cotización para generar el PDF"
        url = reverse("ventas:propuesta_pdf", args=[obj.pk])
        return format_html('<a href="{}" target="_blank">Ver PDF</a> · <a href="{}?descargar=1">Descargar</a>', url, url)

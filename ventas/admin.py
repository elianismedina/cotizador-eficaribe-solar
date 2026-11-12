from django.contrib import admin
from django.contrib.humanize.templatetags.humanize import intcomma

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
    fields = ("orden", "producto", "descripcion", "grupo", "cantidad", "precio_unitario", "tasa_iva")


@admin.register(Cotizacion)
class CotizacionAdmin(admin.ModelAdmin):
    list_display = ("numero", "cliente", "tipo_sistema", "alcance", "estado", "fecha", "valor_total_cop")
    list_filter = ("estado", "tipo_sistema", "alcance")
    search_fields = ("numero", "prospecto__cliente__nombre")
    readonly_fields = ("numero", "resumen_totales")
    inlines = [ItemInline]
    fieldsets = (
        (None, {"fields": ("numero", "prospecto", "fecha", "validez_dias", "estado")}),
        ("Proyecto", {"fields": ("tipo_sistema", "alcance", "ubicacion", "objeto", "exclusiones")}),
        ("Datos técnicos", {"fields": ("consumo_mensual_kwh", "hsp", "configuracion_strings", "cargas_respaldadas", "red_electrica")}),
        ("Condiciones comerciales", {"fields": ("flete", "descripcion_flete", "lugar_entrega", "forma_pago", "tiempo_entrega", "garantias")}),
        ("Análisis financiero", {"fields": ("tarifa_kwh", "supuestos", "resultados")}),
        ("Totales", {"fields": ("resumen_totales",)}),
    )

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
        )

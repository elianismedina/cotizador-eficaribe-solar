from django.contrib import admin

from .models import Empresa, Irradiacion, ParametrosFinancieros, PlantillaCondiciones, PrecioReferencia, Tarifa


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("razon_social", "nit", "telefono", "correo")

    def has_add_permission(self, request):
        return not Empresa.objects.exists()


@admin.register(ParametrosFinancieros)
class ParametrosFinancierosAdmin(admin.ModelAdmin):
    list_display = ("nombre", "vigente", "autoconsumo", "incremento_tarifa", "rendimiento_sistema")
    list_filter = ("vigente",)


@admin.register(Irradiacion)
class IrradiacionAdmin(admin.ModelAdmin):
    list_display = ("zona", "departamento", "hsp")
    list_filter = ("departamento",)
    search_fields = ("zona", "departamento")


@admin.register(Tarifa)
class TarifaAdmin(admin.ModelAdmin):
    list_display = ("operador", "segmento", "estrato", "costo_unitario_kwh", "contribucion", "periodo_referencia", "activa")
    list_filter = ("operador", "segmento", "activa")


@admin.register(PlantillaCondiciones)
class PlantillaCondicionesAdmin(admin.ModelAdmin):
    list_display = ("nombre", "por_defecto", "validez_dias")


@admin.register(PrecioReferencia)
class PrecioReferenciaAdmin(admin.ModelAdmin):
    list_display = ("tipo_sistema", "kwp_desde", "kwp_hasta", "precio_min_wp", "precio_max_wp", "incluye")
    list_filter = ("tipo_sistema",)
    list_editable = ("precio_min_wp", "precio_max_wp")

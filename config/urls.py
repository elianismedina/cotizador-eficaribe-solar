from django.contrib import admin
from django.http import JsonResponse
from django.urls import path


def salud(request):
    return JsonResponse({"estado": "ok"})


admin.site.site_header = "Cotizador · Eficiencia Solar del Caribe"
admin.site.site_title = "Cotizador solar"
admin.site.index_title = "Panel interno"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", salud, name="salud"),
]

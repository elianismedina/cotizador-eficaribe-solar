from django.urls import path

from . import views

app_name = "ventas"

urlpatterns = [
    path("cotizacion/<int:pk>/pdf/", views.propuesta_pdf, name="propuesta_pdf"),
    path("cotizacion/<int:pk>/factura/", views.factura, name="factura"),
]

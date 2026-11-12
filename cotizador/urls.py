from django.urls import path

from . import views

app_name = "cotizador"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("resultado/", views.resultado, name="resultado"),
    path("gracias/", views.gracias, name="gracias"),
]

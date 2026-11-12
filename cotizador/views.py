from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from configuracion.models import Empresa
from ventas.models import Cliente, Cotizacion, Prospecto

from .estimador import Solicitud, estimar
from .forms import ContactoForm, CotizadorForm

UTM = ("utm_source", "utm_campaign")


def _guardar_utm(request):
    for clave in UTM:
        if request.GET.get(clave):
            request.session[clave] = request.GET[clave][:100]


@require_http_methods(["GET", "POST"])
def inicio(request):
    _guardar_utm(request)
    form = CotizadorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        request.session["estimado"] = estimar(
            Solicitud(
                segmento=d["segmento"],
                tipo_sistema=d["tipo_sistema"],
                zona_id=d["zona"].pk,
                consumo_kwh=d["consumo_kwh"],
                valor_factura=d.get("valor_factura"),
            )
        )
        return redirect("cotizador:resultado")
    return render(request, "cotizador/inicio.html", {"form": form, "empresa": Empresa.actual()})


@require_http_methods(["GET", "POST"])
def resultado(request):
    estimado = request.session.get("estimado")
    if not estimado:
        return redirect("cotizador:inicio")
    form = ContactoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cotizacion = crear_prospecto(form.cleaned_data, estimado, request.session)
        notificar_equipo(request, cotizacion, estimado)
        request.session.pop("estimado", None)
        request.session["ultima_cotizacion"] = cotizacion.numero
        return redirect("cotizador:gracias")
    return render(request, "cotizador/resultado.html", {"e": estimado, "form": form, "empresa": Empresa.actual()})


def gracias(request):
    return render(request, "cotizador/gracias.html", {
        "numero": request.session.get("ultima_cotizacion"),
        "empresa": Empresa.actual(),
    })


@transaction.atomic
def crear_prospecto(datos: dict, estimado: dict, session) -> Cotizacion:
    sol = estimado["solicitud"]
    cliente = Cliente.objects.create(
        nombre=datos["nombre"],
        telefono=datos["telefono"],
        correo=datos["correo"],
        ciudad=datos["ciudad"],
        departamento=estimado["departamento"],
        tipo=sol["segmento"],
        acepta_tratamiento_datos=datos["acepta"],
    )
    prospecto = Prospecto.objects.create(
        cliente=cliente,
        origen=Prospecto.Origen.COTIZADOR_WEB,
        utm_source=session.get("utm_source", ""),
        utm_campaign=session.get("utm_campaign", ""),
    )
    return Cotizacion.objects.create(
        prospecto=prospecto,
        tipo_sistema=sol["tipo_sistema"],
        alcance=Cotizacion.Alcance.LLAVE_EN_MANO,
        ubicacion=f"{datos['ciudad']} · {estimado['zona']}",
        consumo_mensual_kwh=Decimal(str(sol["consumo_kwh"])),
        hsp=Decimal(str(estimado["hsp"])),
        tarifa_kwh=Decimal(str(estimado["tarifa_kwh"])),
        supuestos={"origen": "cotizador_web", "solicitud": sol, "tarifa_origen": estimado["tarifa_origen"]},
        resultados=estimado,
    )


def notificar_equipo(request, cotizacion: Cotizacion, e: dict) -> None:
    destinatarios = settings.EMAIL_NOTIFICACIONES
    if not destinatarios:
        return
    cliente = cotizacion.prospecto.cliente
    url = request.build_absolute_uri(reverse("admin:ventas_cotizacion_change", args=[cotizacion.pk]))
    precio = f"${e['precio_min']:,} a ${e['precio_max']:,}".replace(",", ".") if e.get("precio_min") else "sin precio de referencia"
    cuerpo = (
        f"Nuevo prospecto desde el cotizador web\n\n"
        f"Cliente: {cliente.nombre}\nCelular: {cliente.telefono}\nCorreo: {cliente.correo}\n"
        f"Ciudad: {cliente.ciudad} ({e['zona']})\nTipo: {cliente.get_tipo_display()} · {cotizacion.get_tipo_sistema_display()}\n\n"
        f"Consumo: {e['solicitud']['consumo_kwh']:.0f} kWh/mes\nSistema sugerido: {e['potencia_kwp']} kWp ({e['num_paneles']} paneles)\n"
        f"Precio mostrado: {precio}\n\nVer en el panel: {url}\n"
    )
    send_mail(
        f"Nuevo prospecto {cotizacion.numero}: {cliente.nombre}",
        cuerpo,
        settings.DEFAULT_FROM_EMAIL,
        destinatarios,
        fail_silently=True,
    )

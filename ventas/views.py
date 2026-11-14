from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404

from .models import Cotizacion
from .propuesta import generar_pdf


@staff_member_required
def factura(request, pk):
    cot = get_object_or_404(Cotizacion, pk=pk)
    if not cot.factura_archivo:
        raise Http404("Esta cotización no tiene factura adjunta")
    respuesta = HttpResponse(bytes(cot.factura_archivo), content_type=cot.factura_tipo or "application/octet-stream")
    modo = "attachment" if request.GET.get("descargar") else "inline"
    respuesta["Content-Disposition"] = f'{modo}; filename="{cot.numero}_{cot.factura_nombre}"'
    respuesta["X-Content-Type-Options"] = "nosniff"
    return respuesta


@staff_member_required
def propuesta_pdf(request, pk):
    cot = get_object_or_404(Cotizacion, pk=pk)
    respuesta = HttpResponse(generar_pdf(cot), content_type="application/pdf")
    modo = "attachment" if request.GET.get("descargar") else "inline"
    respuesta["Content-Disposition"] = f'{modo}; filename="Cotizacion_{cot.numero}.pdf"'
    return respuesta

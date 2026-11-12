from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from .models import Cotizacion
from .propuesta import generar_pdf


@staff_member_required
def propuesta_pdf(request, pk):
    cot = get_object_or_404(Cotizacion, pk=pk)
    respuesta = HttpResponse(generar_pdf(cot), content_type="application/pdf")
    modo = "attachment" if request.GET.get("descargar") else "inline"
    respuesta["Content-Disposition"] = f'{modo}; filename="Cotizacion_{cot.numero}.pdf"'
    return respuesta

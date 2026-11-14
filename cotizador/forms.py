from django import forms

from configuracion.models import Irradiacion
from ventas.models import Cotizacion

CAMPO = "w-full rounded-lg border border-slate-300 px-3 py-2 focus:border-marca focus:ring-marca"


class CotizadorForm(forms.Form):
    segmento = forms.ChoiceField(
        label="Tipo de proyecto",
        choices=[("residencial", "Hogar"), ("comercial", "Negocio o empresa")],
        widget=forms.RadioSelect,
        initial="residencial",
    )
    tipo_sistema = forms.ChoiceField(
        label="¿Quieres respaldo con baterías durante los cortes de luz?",
        choices=[("on_grid", "No, solo ahorrar en la factura"), ("hibrido", "Sí, con baterías")],
        widget=forms.RadioSelect,
        initial="on_grid",
    )
    zona = forms.ModelChoiceField(
        label="¿Dónde está el proyecto?",
        queryset=Irradiacion.objects.all(),
        empty_label="Elige la zona más cercana",
        widget=forms.Select(attrs={"class": CAMPO}),
    )
    tipo_techo = forms.ChoiceField(
        label="¿Dónde se instalarían los paneles?",
        choices=Cotizacion.TipoTecho.choices,
        widget=forms.RadioSelect,
        error_messages={"required": "Elige el tipo de techo; si no lo sabes, marca «No estoy seguro»."},
    )
    consumo_kwh = forms.FloatField(
        label="Consumo mensual (kWh)",
        min_value=30,
        max_value=500_000,
        help_text="Aparece en tu factura de energía como «consumo» o «kWh».",
        widget=forms.NumberInput(attrs={"class": CAMPO, "placeholder": "Ej. 350", "inputmode": "decimal"}),
    )
    valor_factura = forms.FloatField(
        label="Valor de tu factura mensual (COP, opcional)",
        required=False,
        min_value=10_000,
        help_text="Con este dato calculamos tu tarifa real por kWh.",
        widget=forms.NumberInput(attrs={"class": CAMPO, "placeholder": "Ej. 320000", "inputmode": "numeric"}),
    )

    def clean(self):
        datos = super().clean()
        consumo, factura = datos.get("consumo_kwh"), datos.get("valor_factura")
        if consumo and factura:
            tarifa = factura / consumo
            if not 200 <= tarifa <= 3000:
                raise forms.ValidationError(
                    "El valor de la factura y el consumo no parecen coincidir. Revisa ambos datos."
                )
        return datos


FACTURA_MAX_BYTES = 5 * 1024 * 1024
# Tipos aceptados según los primeros bytes del archivo (no se confía en la extensión).
FIRMAS_FACTURA = [
    (b"%PDF", "application/pdf", ".pdf"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
]


def tipo_de_factura(cabecera: bytes) -> tuple[str, str] | None:
    for firma, tipo, extension in FIRMAS_FACTURA:
        if cabecera.startswith(firma):
            return tipo, extension
    if cabecera[:4] == b"RIFF" and cabecera[8:12] == b"WEBP":
        return "image/webp", ".webp"
    if cabecera[4:8] == b"ftyp" and cabecera[8:12] in {b"heic", b"heix", b"mif1", b"msf1"}:
        return "image/heic", ".heic"
    return None


class ContactoForm(forms.Form):
    nombre = forms.CharField(label="Nombre completo", max_length=200, widget=forms.TextInput(attrs={"class": CAMPO}))
    telefono = forms.CharField(label="Celular o WhatsApp", max_length=40, widget=forms.TextInput(attrs={"class": CAMPO, "inputmode": "tel"}))
    correo = forms.EmailField(label="Correo electrónico", widget=forms.EmailInput(attrs={"class": CAMPO}))
    ciudad = forms.CharField(label="Ciudad o municipio", max_length=80, widget=forms.TextInput(attrs={"class": CAMPO}))
    factura = forms.FileField(
        label="Foto o PDF de tu factura de energía (opcional)",
        required=False,
        help_text="Nos ayuda a revisar tu consumo y tarifa. Máximo 5 MB.",
        widget=forms.ClearableFileInput(attrs={
            "accept": "image/*,application/pdf",
            "class": "block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 "
                     "file:bg-marca file:px-4 file:py-2 file:font-semibold file:text-white hover:file:bg-marca-oscuro",
        }),
    )
    acepta = forms.BooleanField(
        label="Autorizo el tratamiento de mis datos personales para recibir esta cotización (Ley 1581 de 2012).",
    )
    # Campo trampa contra bots: debe quedar vacío.
    sitio_web = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    def clean_factura(self):
        archivo = self.cleaned_data.get("factura")
        if not archivo:
            return None
        if archivo.size > FACTURA_MAX_BYTES:
            raise forms.ValidationError("El archivo pesa más de 5 MB. Prueba con una foto más liviana o un PDF.")
        contenido = archivo.read()
        tipo = tipo_de_factura(contenido[:16])
        if not tipo:
            raise forms.ValidationError("Sube una foto (JPG, PNG, WEBP o HEIC) o un PDF.")
        nombre = (archivo.name or "factura").rsplit("/", 1)[-1][:150]
        if not nombre.lower().endswith(tipo[1]):
            nombre += tipo[1]
        return {"contenido": contenido, "tipo": tipo[0], "nombre": nombre}

    def clean_sitio_web(self):
        if self.cleaned_data.get("sitio_web"):
            raise forms.ValidationError("Solicitud no válida")
        return ""

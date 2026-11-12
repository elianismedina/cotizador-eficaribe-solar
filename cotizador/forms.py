from django import forms

from configuracion.models import Irradiacion

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


class ContactoForm(forms.Form):
    nombre = forms.CharField(label="Nombre completo", max_length=200, widget=forms.TextInput(attrs={"class": CAMPO}))
    telefono = forms.CharField(label="Celular o WhatsApp", max_length=40, widget=forms.TextInput(attrs={"class": CAMPO, "inputmode": "tel"}))
    correo = forms.EmailField(label="Correo electrónico", widget=forms.EmailInput(attrs={"class": CAMPO}))
    ciudad = forms.CharField(label="Ciudad o municipio", max_length=80, widget=forms.TextInput(attrs={"class": CAMPO}))
    acepta = forms.BooleanField(
        label="Autorizo el tratamiento de mis datos personales para recibir esta cotización (Ley 1581 de 2012).",
    )
    # Campo trampa contra bots: debe quedar vacío.
    sitio_web = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    def clean_sitio_web(self):
        if self.cleaned_data.get("sitio_web"):
            raise forms.ValidationError("Solicitud no válida")
        return ""

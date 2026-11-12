from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

PORCENTAJE = [MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))]


class Empresa(models.Model):
    """Datos de la empresa que aparecen en el encabezado de cada propuesta (registro único)."""

    razon_social = models.CharField(max_length=200, default="Eficiencia Solar del Caribe S.A.S.")
    nit = models.CharField("NIT", max_length=30, blank=True)
    direccion = models.CharField(max_length=200, blank=True)
    telefono = models.CharField(max_length=50, blank=True)
    correo = models.EmailField(blank=True)
    sitio_web = models.URLField(blank=True, default="https://eficaribesolar.com")
    logo = models.ImageField(upload_to="empresa/", blank=True)
    color_primario = models.CharField(max_length=7, default="#1F4E79", help_text="Hex, por ejemplo #1F4E79")

    class Meta:
        verbose_name = "empresa"
        verbose_name_plural = "empresa"

    def __str__(self):
        return self.razon_social

    @classmethod
    def actual(cls) -> "Empresa":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ParametrosFinancieros(models.Model):
    """Supuestos del análisis de retorno. Se usa el registro marcado como vigente."""

    nombre = models.CharField(max_length=100, default="Supuestos generales")
    vigente = models.BooleanField(default=True)
    rendimiento_sistema = models.DecimalField(max_digits=4, decimal_places=3, default=Decimal("0.78"), validators=PORCENTAJE)
    autoconsumo = models.DecimalField(max_digits=4, decimal_places=3, default=Decimal("0.90"), validators=PORCENTAJE)
    incremento_tarifa = models.DecimalField(max_digits=4, decimal_places=3, default=Decimal("0.05"), validators=PORCENTAJE)
    degradacion_paneles = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal("0.004"), validators=PORCENTAJE)
    om_porcentaje = models.DecimalField("O&M (% de la inversión)", max_digits=4, decimal_places=3, default=Decimal("0.01"), validators=PORCENTAJE)
    om_incremento = models.DecimalField("Incremento anual O&M", max_digits=4, decimal_places=3, default=Decimal("0.03"), validators=PORCENTAJE)
    tasa_descuento = models.DecimalField(max_digits=4, decimal_places=3, default=Decimal("0.10"), validators=PORCENTAJE)
    horizonte_anios = models.PositiveSmallIntegerField(default=25)
    anio_reposicion_inversor = models.PositiveSmallIntegerField(default=13)
    anio_reposicion_baterias = models.PositiveSmallIntegerField(default=15)
    porcentaje_instalacion_estimada = models.DecimalField(
        max_digits=4, decimal_places=3, default=Decimal("0.20"), validators=PORCENTAJE,
        help_text="Para el escenario 'equipos + instalación (est.)', sobre el total de equipos",
    )
    tarifa_renta = models.DecimalField(max_digits=4, decimal_places=3, default=Decimal("0.35"), validators=PORCENTAJE)
    potencia_panel_referencia_w = models.PositiveIntegerField(
        "Potencia del panel de referencia (W)", default=630,
        help_text="Panel usado por el cotizador público para estimar el número de paneles",
    )
    tarifa_referencia_residencial = models.DecimalField(
        "Tarifa de referencia residencial (COP/kWh)", max_digits=8, decimal_places=2, default=Decimal("900"),
        help_text="Se usa si el cliente no indica el valor de su factura",
    )
    tarifa_referencia_comercial = models.DecimalField(
        "Tarifa de referencia comercial (COP/kWh)", max_digits=8, decimal_places=2, default=Decimal("1150"),
        help_text="Se usa si el cliente no indica el valor de su factura",
    )
    factor_emision_kg_kwh = models.DecimalField(
        "Factor de emisión (kg CO₂/kWh)", max_digits=5, decimal_places=3, default=Decimal("0.126"),
        help_text="Validar con el factor de emisión vigente del SIN",
    )

    class Meta:
        verbose_name = "parámetros financieros"
        verbose_name_plural = "parámetros financieros"

    def __str__(self):
        return f"{self.nombre}{' (vigente)' if self.vigente else ''}"

    @classmethod
    def vigentes(cls) -> "ParametrosFinancieros":
        obj = cls.objects.filter(vigente=True).order_by("-pk").first()
        return obj or cls.objects.create()


class Irradiacion(models.Model):
    """Horas sol pico (HSP) promedio por zona."""

    zona = models.CharField(max_length=120, help_text="Por ejemplo: Costa pacífica del Cauca")
    departamento = models.CharField(max_length=80)
    hsp = models.DecimalField("HSP", max_digits=4, decimal_places=2)
    nota = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "irradiación por zona"
        verbose_name_plural = "irradiación por zona"
        ordering = ["departamento", "zona"]

    def __str__(self):
        return f"{self.zona} ({self.departamento}) · {self.hsp} HSP"


class Tarifa(models.Model):
    """Tarifa de energía por operador de red y segmento."""

    class Segmento(models.TextChoices):
        RESIDENCIAL = "residencial", "Residencial"
        COMERCIAL = "comercial", "Comercial"
        INDUSTRIAL = "industrial", "Industrial"
        OFICIAL = "oficial", "Oficial"

    operador = models.CharField(max_length=80, help_text="Por ejemplo: Cedenar, Celsia, Air-e")
    segmento = models.CharField(max_length=20, choices=Segmento.choices)
    estrato = models.PositiveSmallIntegerField(null=True, blank=True)
    costo_unitario_kwh = models.DecimalField("Costo unitario (COP/kWh)", max_digits=8, decimal_places=2)
    contribucion = models.DecimalField(
        max_digits=4, decimal_places=3, default=Decimal("0"), validators=PORCENTAJE,
        help_text="0,20 para usuarios comerciales; subsidio como valor negativo no se usa aquí",
    )
    periodo_referencia = models.CharField(max_length=30, blank=True, help_text="Por ejemplo: 3T-2025")
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["operador", "segmento", "estrato"]

    def __str__(self):
        est = f" estrato {self.estrato}" if self.estrato else ""
        return f"{self.operador} · {self.get_segmento_display()}{est}"

    @property
    def tarifa_final_kwh(self) -> Decimal:
        return self.costo_unitario_kwh * (1 + self.contribucion)


class PlantillaCondiciones(models.Model):
    """Condiciones comerciales y textos por defecto para las propuestas."""

    nombre = models.CharField(max_length=100)
    por_defecto = models.BooleanField(default=False)
    validez_dias = models.PositiveSmallIntegerField(default=15)
    forma_pago = models.TextField(default="75 % de anticipo con la orden de compra y 25 % contra entrega.")
    tiempo_entrega = models.TextField(default="15 días hábiles a partir del anticipo, sujeto a disponibilidad de inventario.")
    opciones_financiacion = models.TextField(
        blank=True,
        default="Financiación disponible con Addi y Sistecrédito, sujeta al perfil crediticio y al cupo del cliente.",
    )
    garantias = models.TextField(blank=True)
    nota_beneficios_tributarios = models.TextField(blank=True)
    nota_estimaciones = models.TextField(
        default=(
            "Las cifras de este análisis son estimaciones basadas en los supuestos indicados. "
            "La producción real depende del clima, de la orientación de la instalación y del consumo."
        )
    )

    class Meta:
        verbose_name = "plantilla de condiciones"
        verbose_name_plural = "plantillas de condiciones"

    def __str__(self):
        return self.nombre


class PrecioReferencia(models.Model):
    """Precio por Wp instalado que usa el cotizador público para el estimado en línea."""

    class TipoSistema(models.TextChoices):
        ON_GRID = "on_grid", "Conectado a red"
        HIBRIDO = "hibrido", "Híbrido con almacenamiento"

    tipo_sistema = models.CharField(max_length=20, choices=TipoSistema.choices)
    kwp_desde = models.DecimalField("Desde (kWp)", max_digits=7, decimal_places=2, default=Decimal("0"))
    kwp_hasta = models.DecimalField("Hasta (kWp)", max_digits=7, decimal_places=2, null=True, blank=True,
                                    help_text="Vacío = sin límite")
    precio_min_wp = models.DecimalField("Precio mínimo por Wp (COP, antes de IVA)", max_digits=9, decimal_places=2)
    precio_max_wp = models.DecimalField("Precio máximo por Wp (COP, antes de IVA)", max_digits=9, decimal_places=2)
    incluye = models.CharField(max_length=200, blank=True, default="Llave en mano: equipos, instalación, RETIE y trámites")
    nota = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "precio de referencia"
        verbose_name_plural = "precios de referencia"
        ordering = ["tipo_sistema", "kwp_desde"]

    def __str__(self):
        hasta = f"{self.kwp_hasta}" if self.kwp_hasta is not None else "∞"
        return f"{self.get_tipo_sistema_display()} {self.kwp_desde}–{hasta} kWp · ${self.precio_min_wp}–${self.precio_max_wp}/Wp"

    @property
    def precio_por_wp(self) -> Decimal:
        """Punto medio del rango, usado para el análisis de retorno."""
        return (self.precio_min_wp + self.precio_max_wp) / 2

    @classmethod
    def para(cls, tipo_sistema: str, kwp) -> "PrecioReferencia | None":
        candidatos = cls.objects.filter(tipo_sistema=tipo_sistema, kwp_desde__lte=kwp).order_by("-kwp_desde")
        for ref in candidatos:
            if ref.kwp_hasta is None or kwp <= ref.kwp_hasta:
                return ref
        return None

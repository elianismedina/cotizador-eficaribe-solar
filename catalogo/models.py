from decimal import Decimal

from django.db import models


CATEGORIAS_SIN_IVA = {"panel", "inversor"}


def tasa_iva_por_categoria(categoria: str) -> Decimal:
    """En Colombia los paneles y los inversores están excluidos de IVA; lo demás paga 19 %."""
    return Decimal("0") if categoria in CATEGORIAS_SIN_IVA else Decimal("0.19")


class Producto(models.Model):
    """Equipo, material o servicio que se puede incluir en una cotización."""

    class Categoria(models.TextChoices):
        PANEL = "panel", "Panel solar"
        INVERSOR = "inversor", "Inversor"
        BATERIA = "bateria", "Batería"
        ESTRUCTURA = "estructura", "Estructura"
        CABLEADO = "cableado", "Cableado y canalización"
        PROTECCION_DC = "proteccion_dc", "Protección DC"
        PROTECCION_AC = "proteccion_ac", "Protección AC y puesta a tierra"
        SERVICIO = "servicio", "Servicio"
        OTRO = "otro", "Otro"

    class Unidad(models.TextChoices):
        UNIDAD = "und", "und"
        METRO = "m", "m"
        PAR = "par", "par"
        KIT = "kit", "kit"
        PAQUETE = "paquete", "paquete"
        GLOBAL = "global", "global"

    class Iva(models.TextChoices):
        EXCLUIDO = "excluido", "Excluido"
        GRAVADO = "gravado", "Gravado 19 %"

    categoria = models.CharField(max_length=20, choices=Categoria.choices)
    nombre = models.CharField(max_length=200, help_text="Como aparece en la propuesta, ej. Panel solar Risen 630 W")
    marca = models.CharField(max_length=80, blank=True)
    modelo = models.CharField(max_length=120, blank=True)
    descripcion_tecnica = models.CharField(max_length=300, blank=True)
    unidad = models.CharField(max_length=10, choices=Unidad.choices, default=Unidad.UNIDAD)
    unidad_detalle = models.CharField(max_length=40, blank=True, help_text="Ej. 4 pan. para un kit de estructura")
    potencia_w = models.DecimalField("Potencia (W)", max_digits=9, decimal_places=1, null=True, blank=True)
    capacidad_kwh = models.DecimalField("Capacidad (kWh)", max_digits=7, decimal_places=2, null=True, blank=True)
    costo = models.DecimalField("Costo (COP, sin IVA)", max_digits=14, decimal_places=2, default=Decimal("0"))
    precio = models.DecimalField("Precio de venta (COP, sin IVA)", max_digits=14, decimal_places=2)
    iva = models.CharField("IVA", max_length=10, choices=Iva.choices, default=Iva.GRAVADO)
    garantia_anios = models.PositiveSmallIntegerField(null=True, blank=True)
    ficha_tecnica = models.FileField(upload_to="fichas/", blank=True)
    id_tiendanube = models.CharField(max_length=40, blank=True, help_text="ID del producto en Tiendanube")
    slug_tiendanube = models.SlugField(
        "Identificador de URL en Tiendanube", max_length=200, blank=True, db_index=True,
        help_text="Se usa para actualizar el producto al volver a importar el CSV",
    )
    url_tienda = models.URLField(blank=True)
    activo = models.BooleanField(default=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["categoria", "nombre"]

    def __str__(self):
        return self.nombre

    @property
    def tasa_iva(self) -> Decimal:
        return Decimal("0.19") if self.iva == self.Iva.GRAVADO else Decimal("0")

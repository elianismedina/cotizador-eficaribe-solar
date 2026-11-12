from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from catalogo.models import Producto

UN_PESO = Decimal("1")


def redondear(valor: Decimal) -> Decimal:
    return Decimal(valor).quantize(UN_PESO, rounding=ROUND_HALF_UP)


class Cliente(models.Model):
    class Tipo(models.TextChoices):
        RESIDENCIAL = "residencial", "Residencial"
        COMERCIAL = "comercial", "Comercial"

    nombre = models.CharField("Nombre o razón social", max_length=200)
    documento = models.CharField("NIT o cédula", max_length=30, blank=True)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.RESIDENCIAL)
    correo = models.EmailField(blank=True)
    telefono = models.CharField(max_length=40, blank=True)
    ciudad = models.CharField(max_length=80, blank=True)
    departamento = models.CharField(max_length=80, blank=True)
    direccion = models.CharField(max_length=200, blank=True)
    acepta_tratamiento_datos = models.BooleanField(default=False)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return self.nombre


class Prospecto(models.Model):
    class Origen(models.TextChoices):
        COTIZADOR_WEB = "web", "Cotizador web"
        TIENDA = "tienda", "Tienda en línea"
        REFERIDO = "referido", "Referido"
        WHATSAPP = "whatsapp", "WhatsApp"
        OTRO = "otro", "Otro"

    class Estado(models.TextChoices):
        NUEVO = "nuevo", "Nuevo"
        CONTACTADO = "contactado", "Contactado"
        VISITA = "visita", "Visita técnica"
        PROPUESTA = "propuesta", "Propuesta enviada"
        GANADO = "ganado", "Ganado"
        PERDIDO = "perdido", "Perdido"

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="prospectos")
    origen = models.CharField(max_length=20, choices=Origen.choices, default=Origen.COTIZADOR_WEB)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.NUEVO)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    notas = models.TextField(blank=True)
    proximo_contacto = models.DateField(null=True, blank=True)
    utm_source = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.cliente} · {self.get_estado_display()}"


class Cotizacion(models.Model):
    class TipoSistema(models.TextChoices):
        ON_GRID = "on_grid", "Conectado a red"
        HIBRIDO = "hibrido", "Híbrido con almacenamiento"
        AISLADO = "aislado", "Aislado"

    class Alcance(models.TextChoices):
        SUMINISTRO = "suministro", "Solo suministro de equipos"
        INSTALADO = "instalado", "Suministro e instalación"
        LLAVE_EN_MANO = "llave_en_mano", "Llave en mano (instalación, RETIE y trámites)"

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        ENVIADA = "enviada", "Enviada"
        ACEPTADA = "aceptada", "Aceptada"
        RECHAZADA = "rechazada", "Rechazada"
        VENCIDA = "vencida", "Vencida"

    numero = models.CharField(max_length=20, unique=True, editable=False)
    prospecto = models.ForeignKey(Prospecto, on_delete=models.CASCADE, related_name="cotizaciones")
    fecha = models.DateField(default=timezone.localdate)
    validez_dias = models.PositiveSmallIntegerField(default=15)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.BORRADOR)
    tipo_sistema = models.CharField(max_length=20, choices=TipoSistema.choices, default=TipoSistema.ON_GRID)
    alcance = models.CharField(max_length=20, choices=Alcance.choices, default=Alcance.SUMINISTRO)
    exclusiones = models.TextField(blank=True, help_text="Qué no incluye la oferta")
    ubicacion = models.CharField(max_length=120, blank=True)
    objeto = models.TextField(blank=True, help_text="Para qué sirve el sistema (sección 1 del PDF)")

    # Datos técnicos (sección 2)
    consumo_mensual_kwh = models.DecimalField(max_digits=10, decimal_places=1, null=True, blank=True)
    hsp = models.DecimalField("HSP", max_digits=4, decimal_places=2)
    configuracion_strings = models.CharField(max_length=200, blank=True)
    cargas_respaldadas = models.CharField(max_length=300, blank=True)
    red_electrica = models.CharField(max_length=120, blank=True)

    # Comercial (secciones 3 y 4)
    flete = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    descripcion_flete = models.CharField(max_length=120, blank=True, default="Flete de los equipos")
    lugar_entrega = models.CharField(max_length=200, blank=True)
    forma_pago = models.TextField(blank=True)
    tiempo_entrega = models.TextField(blank=True)
    garantias = models.TextField(blank=True)

    # Supuestos financieros congelados al generar (sección 5)
    tarifa_kwh = models.DecimalField("Tarifa año 1 (COP/kWh)", max_digits=8, decimal_places=2)
    supuestos = models.JSONField(default=dict, blank=True, help_text="Copia de los supuestos usados en el análisis")
    resultados = models.JSONField(default=dict, blank=True, help_text="Copia de los resultados del análisis")

    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "cotización"
        verbose_name_plural = "cotizaciones"
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.numero} · {self.prospecto.cliente}"

    def save(self, *args, **kwargs):
        if not self.numero:
            with transaction.atomic():
                self.numero = self.siguiente_numero(self.fecha.year)
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)

    @staticmethod
    def siguiente_numero(anio: int) -> str:
        """Consecutivo por año: COT-2026-0001, COT-2026-0002…"""
        prefijo = f"COT-{anio}-"
        ultimo = (
            Cotizacion.objects.select_for_update()
            .filter(numero__startswith=prefijo)
            .order_by("-numero")
            .values_list("numero", flat=True)
            .first()
        )
        siguiente = int(ultimo.removeprefix(prefijo)) + 1 if ultimo else 1
        return f"{prefijo}{siguiente:04d}"

    # Totales -----------------------------------------------------------
    @property
    def subtotal(self) -> Decimal:
        return sum((i.subtotal for i in self.items.all()), Decimal("0"))

    @property
    def total_iva(self) -> Decimal:
        return sum((i.iva for i in self.items.all()), Decimal("0"))

    @property
    def total_equipos(self) -> Decimal:
        return self.subtotal + self.total_iva

    @property
    def valor_total(self) -> Decimal:
        return self.total_equipos + self.flete

    @property
    def potencia_kwp(self) -> Decimal:
        paneles = self.items.filter(producto__categoria=Producto.Categoria.PANEL)
        return sum((i.cantidad * (i.producto.potencia_w or 0) for i in paneles), Decimal("0")) / 1000

    @property
    def capacidad_baterias_kwh(self) -> Decimal:
        baterias = self.items.filter(producto__categoria=Producto.Categoria.BATERIA)
        return sum((i.cantidad * (i.producto.capacidad_kwh or 0) for i in baterias), Decimal("0"))


class ItemCotizacion(models.Model):
    class Grupo(models.TextChoices):
        EQUIPOS = "equipos", "Equipos principales"
        ESTRUCTURA = "estructura", "Estructura, cableado y canalización"
        PROTECCIONES_DC = "proteccion_dc", "Protecciones DC"
        PROTECCIONES_AC = "proteccion_ac", "Protecciones AC y puesta a tierra"
        SERVICIOS = "servicios", "Servicios"

    GRUPO_POR_CATEGORIA = {
        Producto.Categoria.PANEL: Grupo.EQUIPOS,
        Producto.Categoria.INVERSOR: Grupo.EQUIPOS,
        Producto.Categoria.BATERIA: Grupo.EQUIPOS,
        Producto.Categoria.ESTRUCTURA: Grupo.ESTRUCTURA,
        Producto.Categoria.CABLEADO: Grupo.ESTRUCTURA,
        Producto.Categoria.PROTECCION_DC: Grupo.PROTECCIONES_DC,
        Producto.Categoria.PROTECCION_AC: Grupo.PROTECCIONES_AC,
        Producto.Categoria.SERVICIO: Grupo.SERVICIOS,
    }

    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    grupo = models.CharField(max_length=20, choices=Grupo.choices, blank=True)
    descripcion = models.CharField(max_length=200, blank=True, help_text="Vacío = nombre del producto")
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                          help_text="Vacío = precio actual del catálogo")
    tasa_iva = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True,
                                   help_text="Vacío = según el producto (0 o 0,19)")
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["orden", "pk"]
        verbose_name = "ítem"
        verbose_name_plural = "ítems"

    def __str__(self):
        return self.descripcion or self.producto.nombre

    def save(self, *args, **kwargs):
        # Congelar precio, IVA y grupo al guardar, para que cambios de catálogo no alteren la propuesta.
        if self.precio_unitario is None:
            self.precio_unitario = self.producto.precio
        if self.tasa_iva is None:
            self.tasa_iva = self.producto.tasa_iva
        if not self.grupo:
            self.grupo = self.GRUPO_POR_CATEGORIA.get(self.producto.categoria, self.Grupo.EQUIPOS)
        if not self.descripcion:
            self.descripcion = self.producto.nombre
        super().save(*args, **kwargs)

    @property
    def subtotal(self) -> Decimal:
        return redondear(self.cantidad * (self.precio_unitario or 0))

    @property
    def iva(self) -> Decimal:
        return redondear(self.subtotal * (self.tasa_iva or 0))

    @property
    def total(self) -> Decimal:
        return self.subtotal + self.iva

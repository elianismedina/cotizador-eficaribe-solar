from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from catalogo.models import Producto, tasa_iva_por_categoria

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
    validez_dias = models.PositiveSmallIntegerField(default=8)
    trm = models.DecimalField(
        "TRM (COP por USD)", max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Para los ítems con costo en dólares. Al cambiarla se recalculan sus precios",
    )
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
        paneles = self.items.filter(categoria=Producto.Categoria.PANEL)
        return sum((i.cantidad * (i.potencia_w or 0) for i in paneles), Decimal("0")) / 1000

    @property
    def capacidad_baterias_kwh(self) -> Decimal:
        baterias = self.items.filter(categoria=Producto.Categoria.BATERIA)
        return sum((i.cantidad * (i.capacidad_kwh or 0) for i in baterias), Decimal("0"))

    @property
    def margen_por_defecto(self) -> Decimal:
        from configuracion.models import ParametrosFinancieros

        p = ParametrosFinancieros.vigentes()
        es_comercial = self.prospecto.cliente.tipo == Cliente.Tipo.COMERCIAL
        return p.margen_comercial if es_comercial else p.margen_residencial

    def utilidad(self) -> tuple[Decimal, Decimal] | None:
        """Costo y utilidad (antes de IVA) de los ítems con costo conocido; None si no hay ninguno."""
        con_costo = [i for i in self.items.all() if i.costo_cop is not None]
        if not con_costo:
            return None
        costo = sum((redondear(i.cantidad * i.costo_cop) for i in con_costo), Decimal("0"))
        venta = sum((i.subtotal for i in con_costo), Decimal("0"))
        return costo, venta - costo

    def recalcular_precios(self):
        """Vuelve a calcular el precio de los ítems con costo (por ejemplo, tras cambiar la TRM)."""
        for item in self.items.exclude(costo_unitario=None):
            item.save()


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

    class Moneda(models.TextChoices):
        COP = "COP", "COP"
        USD = "USD", "USD"

    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, null=True, blank=True,
                                 help_text="Opcional: vacío para un equipo de proveedor que no está en el catálogo")
    descripcion = models.CharField(max_length=200, blank=True, help_text="Vacío = nombre del producto")
    categoria = models.CharField(max_length=20, choices=Producto.Categoria.choices, blank=True,
                                 help_text="Vacío = la del producto")
    grupo = models.CharField(max_length=20, choices=Grupo.choices, blank=True)
    potencia_w = models.DecimalField("Potencia (W)", max_digits=9, decimal_places=1, null=True, blank=True,
                                     help_text="Paneles: para calcular los kWp")
    capacidad_kwh = models.DecimalField("Capacidad (kWh)", max_digits=7, decimal_places=2, null=True, blank=True,
                                        help_text="Baterías")
    unidad = models.CharField(max_length=10, choices=Producto.Unidad.choices, blank=True)
    unidad_detalle = models.CharField(max_length=40, blank=True)
    garantia_anios = models.PositiveSmallIntegerField("Garantía (años)", null=True, blank=True)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    proveedor = models.CharField(max_length=120, blank=True)
    costo_unitario = models.DecimalField("Costo unitario", max_digits=14, decimal_places=2, null=True, blank=True,
                                         help_text="Lo que te cobra el proveedor, antes de IVA")
    moneda = models.CharField(max_length=3, choices=Moneda.choices, default=Moneda.COP)
    margen = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True,
                                 help_text="Sobre el costo, ej. 0,25. Vacío = margen por defecto del segmento")
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                          help_text="Con costo se calcula solo (costo × (1 + margen)); sin costo, vacío = precio del catálogo")
    tasa_iva = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True,
                                   help_text="Vacío = según la categoría (paneles e inversores 0, lo demás 0,19)")
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["orden", "pk"]
        verbose_name = "ítem"
        verbose_name_plural = "ítems"

    def __str__(self):
        return self.descripcion or (self.producto.nombre if self.producto else "Ítem")

    @property
    def costo_cop(self) -> Decimal | None:
        if self.costo_unitario is None:
            return None
        if self.moneda == self.Moneda.USD:
            return self.costo_unitario * self.cotizacion.trm if self.cotizacion.trm else None
        return self.costo_unitario

    def clean(self):
        errores = {}
        if not self.producto_id:
            if not self.descripcion:
                errores["descripcion"] = "Escribe la descripción del equipo o elige un producto del catálogo."
            if not self.categoria:
                errores["categoria"] = "Elige la categoría (define el grupo y el IVA)."
            if self.costo_unitario is None and self.precio_unitario is None:
                errores["costo_unitario"] = "Indica el costo del proveedor o el precio de venta."
        cot = getattr(self, "cotizacion", None)
        if self.costo_unitario is not None and self.moneda == self.Moneda.USD and not (cot and cot.trm):
            errores["moneda"] = "Para costos en dólares, indica la TRM en la cotización."
        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        # Congelar los datos del producto al guardar, para que cambios de catálogo no alteren la propuesta.
        prod = self.producto
        if prod:
            self.descripcion = self.descripcion or prod.nombre
            self.categoria = self.categoria or prod.categoria
            self.unidad = self.unidad or prod.unidad
            self.unidad_detalle = self.unidad_detalle or prod.unidad_detalle
            for campo in ("potencia_w", "capacidad_kwh", "garantia_anios"):
                if getattr(self, campo) is None:
                    setattr(self, campo, getattr(prod, campo))
        self.categoria = self.categoria or Producto.Categoria.OTRO
        self.unidad = self.unidad or Producto.Unidad.UNIDAD
        if self.costo_cop is not None:
            if self.margen is None:
                self.margen = self.cotizacion.margen_por_defecto
            # Con costo, el precio siempre sale de costo × (1 + margen); para ajustarlo se cambia el margen.
            self.precio_unitario = redondear(self.costo_cop * (1 + self.margen))
        if self.precio_unitario is None:
            self.precio_unitario = prod.precio if prod else Decimal("0")
        if self.tasa_iva is None:
            self.tasa_iva = prod.tasa_iva if prod else tasa_iva_por_categoria(self.categoria)
        if not self.grupo:
            self.grupo = self.GRUPO_POR_CATEGORIA.get(self.categoria, self.Grupo.EQUIPOS)
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

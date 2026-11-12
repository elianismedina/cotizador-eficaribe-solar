"""Datos iniciales para que el cotizador público funcione desde el primer despliegue.

Todos los valores son puntos de partida y se ajustan desde el panel de administración:
- HSP por zona: aproximados, salvo la costa pacífica del Cauca (3,5, tomado de COT-2026-1987).
- Precios por Wp: rangos de referencia de mercado llave en mano (finales de 2026), antes de IVA.
"""
from decimal import Decimal

from django.db import migrations

APROX = "Aproximado; validar con datos del sitio"

ZONAS = [
    ("Barranquilla y área metropolitana", "Atlántico", "5.5", APROX),
    ("Cartagena y norte de Bolívar", "Bolívar", "5.3", APROX),
    ("Santa Marta y zona bananera", "Magdalena", "5.5", APROX),
    ("Riohacha y La Guajira", "La Guajira", "6.0", APROX),
    ("Valledupar", "Cesar", "5.3", APROX),
    ("Montería", "Córdoba", "4.8", APROX),
    ("Sincelejo", "Sucre", "5.0", APROX),
    ("San Andrés", "San Andrés y Providencia", "5.2", APROX),
    ("Cali y valle geográfico", "Valle del Cauca", "4.5", APROX),
    ("Buenaventura", "Valle del Cauca", "3.5", APROX),
    ("Popayán y centro del Cauca", "Cauca", "4.2", APROX),
    ("Costa pacífica del Cauca (Timbiquí, Guapi)", "Cauca", "3.5", "Tomado de COT-2026-1987 (alta nubosidad)"),
    ("Pasto", "Nariño", "4.2", APROX),
    ("Tumaco y costa pacífica de Nariño", "Nariño", "3.5", APROX),
    ("Medellín y Valle de Aburrá", "Antioquia", "4.5", APROX),
    ("Bogotá y sabana", "Cundinamarca", "4.0", APROX),
    ("Bucaramanga", "Santander", "4.5", APROX),
]

# Rangos de referencia de mercado (finales de 2026, llave en mano, COP por Wp antes de IVA)
# entregados por Eli. El cotizador muestra el rango y usa el punto medio para el retorno.
NOTA_PRECIO = "Rango de referencia de mercado, finales de 2026; ajustar con costos propios"
PRECIOS = [
    # (tipo, desde kWp, hasta kWp, mínimo, máximo)
    ("on_grid", "0", "5", "4000", "5500"),
    ("on_grid", "5", "10", "3500", "4500"),
    ("on_grid", "10", "50", "3000", "3800"),
    ("on_grid", "50", "200", "2600", "3200"),
    ("on_grid", "200", None, "2200", "2800"),
    ("hibrido", "0", None, "6000", "9000"),
]


def cargar(apps, schema_editor):
    Irradiacion = apps.get_model("configuracion", "Irradiacion")
    PrecioReferencia = apps.get_model("configuracion", "PrecioReferencia")
    Empresa = apps.get_model("configuracion", "Empresa")
    Tarifa = apps.get_model("configuracion", "Tarifa")

    if not Irradiacion.objects.exists():
        Irradiacion.objects.bulk_create(
            Irradiacion(zona=z, departamento=d, hsp=Decimal(h), nota=n) for z, d, h, n in ZONAS
        )
    if not PrecioReferencia.objects.exists():
        PrecioReferencia.objects.bulk_create(
            PrecioReferencia(
                tipo_sistema=t,
                kwp_desde=Decimal(desde),
                kwp_hasta=Decimal(hasta) if hasta else None,
                precio_min_wp=Decimal(minimo),
                precio_max_wp=Decimal(maximo),
                nota=NOTA_PRECIO,
            )
            for t, desde, hasta, minimo, maximo in PRECIOS
        )
    Empresa.objects.get_or_create(
        pk=1,
        defaults=dict(
            razon_social="Eficiencia Solar del Caribe S.A.S.",
            nit="901.398.773-1",
            direccion="Calle 12 # 35 Oeste 100, Candelaria, Valle del Cauca",
            telefono="323 939 8511",
            correo="contacto@eficaribesolar.com",
        ),
    )
    if not Tarifa.objects.exists():
        Tarifa.objects.create(
            operador="Cedenar", segmento="comercial", costo_unitario_kwh=Decimal("960"),
            contribucion=Decimal("0.20"), periodo_referencia="3T-2025",
        )


def borrar(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("configuracion", "0002_precios_referencia")]
    operations = [migrations.RunPython(cargar, borrar)]

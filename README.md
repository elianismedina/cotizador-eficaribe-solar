# Cotizador solar · Eficiencia Solar del Caribe

Aplicación Django para cotizar proyectos fotovoltaicos (residenciales y comerciales, on-grid e híbridos)
y generar propuestas profesionales. Se publica en `cotizador.eficaribesolar.com` (Render + Postgres).

## Estructura

| App | Contenido |
| --- | --- |
| `configuracion` | Empresa, parámetros financieros, HSP por zona, tarifas por operador, plantillas de condiciones |
| `catalogo` | Productos (paneles, inversores, baterías, estructura, protecciones, servicios) con IVA por producto |
| `ventas` | Clientes, prospectos, cotizaciones con numeración `COT-AAAA-NNNN` e ítems con precio congelado |
| `cotizador` | Motor de cálculo en Python puro (`cotizador/motor/`) y, próximamente, el cotizador público |

El motor financiero reproduce la metodología de la cotización COT-2026-1987
(autoconsumo, incremento de tarifa, degradación, O&M, reposiciones, TIR, VPN, recuperación y sensibilidad);
las pruebas en `cotizador/tests/test_motor.py` verifican que da los mismos números.

## Desarrollo local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Panel interno: http://localhost:8000/admin/

## Cotizador público

En la raíz del sitio (`/`) el cliente indica tipo de proyecto, zona, consumo y, si quiere, el valor de su factura.
Ve el sistema sugerido, el ahorro y un rango de precio. Al dejar sus datos se crean el cliente, el prospecto y una
cotización en borrador, y se envía un correo a `EMAIL_NOTIFICACIONES`.

Los valores que usa se ajustan en el panel: **Precios de referencia** (COP por Wp instalado), **Irradiación por zona**
(HSP) y **Parámetros financieros** (tarifas de referencia, panel de referencia, margen del rango).

### Estilos

Los estilos usan Tailwind compilado en `cotizador/static/cotizador/app.css` (no hace falta Node en Render).
Si cambias clases en las plantillas, vuelve a compilar:

```bash
npx tailwindcss@3.4.17 -c tailwind/tailwind.config.js -i tailwind/entrada.css -o cotizador/static/cotizador/app.css --minify
```

## Pruebas

```bash
python manage.py test
```

## Despliegue en Render

1. En Render: **New > Blueprint** y elegir este repositorio (usa `render.yaml`).
2. Tras el primer despliegue, crear el usuario administrador desde la consola del servicio:
   `python manage.py createsuperuser`.
3. En Squarespace Domains (DNS de eficaribesolar.com), agregar un registro `CNAME`
   `cotizador` → `cotizador-eficaribe-solar.onrender.com` (el nombre exacto lo muestra Render en *Custom Domains*).

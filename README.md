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

## Catálogo desde Tiendanube

En Tiendanube: **Productos › Exportar** y descargar el CSV. Luego, en el panel, **Productos › Importar desde Tiendanube**
(o `python manage.py importar_tiendanube archivo.csv`). Cada producto se identifica por su identificador de URL:
volver a importar actualiza nombre, precio, marca y visibilidad, y conserva la categoría, el IVA y la potencia ajustados
en el panel. Por defecto se asume que los precios de la tienda incluyen IVA y se guarda el precio sin IVA de los
productos gravados (paneles e inversores quedan excluidos).

## Equipos de proveedor (sin catálogo)

Una cotización puede llevar equipos que no están en el catálogo. En el ítem se deja vacío el producto y se llenan la
descripción, la categoría, el proveedor y el costo (antes de IVA):

- **Precio de venta** = costo × (1 + margen). Si el margen se deja vacío se usa el de *Parámetros financieros*
  (25 % residencial y 15 % comercial por defecto). Para ajustar el precio se cambia el margen.
- **Costo en dólares**: se elige USD y se indica la TRM en la cotización. Al cambiar la TRM se recalculan los precios.
- **IVA**: según la categoría (paneles e inversores excluidos, lo demás 19 %).
- El resumen de la cotización en el panel muestra el costo y la utilidad; esos datos no salen en el PDF.

Las propuestas valen 8 días por defecto y el PDF aclara que los precios dependen de la disponibilidad y de la TRM
(texto editable en *Plantillas de condiciones*).

## Propuesta en PDF

Desde el panel, en cada cotización, los enlaces **Ver PDF** y **Descargar** generan la propuesta formal con la estructura
de COT-2026-1987: datos de la empresa, objeto, descripción del sistema, tabla económica por grupos con IVA por línea,
condiciones comerciales y análisis de retorno (supuestos, escenarios, flujo de caja, sensibilidad y beneficios tributarios).
Cuando el alcance es *solo suministro*, se agrega un segundo escenario con la instalación estimada.

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

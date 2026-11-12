#!/usr/bin/env bash
# Build de Render: instala dependencias y recolecta archivos estáticos.
set -o errexit
pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --no-input

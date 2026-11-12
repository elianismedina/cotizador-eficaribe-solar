from pathlib import Path

from django.core.management.base import BaseCommand

from catalogo.importar import importar


class Command(BaseCommand):
    help = "Importa o actualiza el catálogo desde el CSV exportado de Tiendanube"

    def add_arguments(self, parser):
        parser.add_argument("archivo", type=Path)
        parser.add_argument("--precios-sin-iva", action="store_true",
                            help="Usar si los precios de la tienda NO incluyen IVA")

    def handle(self, archivo, precios_sin_iva, **opciones):
        resumen = importar(archivo.read_bytes(), precios_con_iva=not precios_sin_iva)
        self.stdout.write(self.style.SUCCESS(str(resumen)))
        for e in resumen.errores:
            self.stdout.write(self.style.WARNING(e))

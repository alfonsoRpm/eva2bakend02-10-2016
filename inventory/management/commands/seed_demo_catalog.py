from decimal import Decimal

from django.core.management.base import BaseCommand

from inventory.models import Category, Machinery


class Command(BaseCommand):
    help = "Carga un catálogo de demostración sin modificar registros existentes."

    def handle(self, *args, **options):
        category_data = [
            ("excavadoras", "Excavadoras"),
            ("carga", "Cargadores y retroexcavadoras"),
            ("compactacion", "Compactación"),
        ]
        categories = {}
        created_categories = 0
        for slug, name in category_data:
            category, created = Category.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "description": "Categoría de demostración."},
            )
            categories[slug] = category
            created_categories += int(created)

        machine_data = [
            {
                "sku": "DEMO-EXC-020",
                "name": "DEMO - Excavadora hidráulica 20 t",
                "brand": "Demo",
                "model_name": "EX-20",
                "category": "excavadoras",
                "daily_rate": Decimal("350000.00"),
                "fixed_guarantee": Decimal("500000.00"),
                "total_units": 2,
            },
            {
                "sku": "DEMO-EXC-035",
                "name": "DEMO - Mini excavadora 3.5 t",
                "brand": "Demo",
                "model_name": "EX-035",
                "category": "excavadoras",
                "daily_rate": Decimal("180000.00"),
                "fixed_guarantee": Decimal("250000.00"),
                "total_units": 3,
            },
            {
                "sku": "DEMO-RET-4X4",
                "name": "DEMO - Retroexcavadora 4x4",
                "brand": "Demo",
                "model_name": "RT-4X4",
                "category": "carga",
                "daily_rate": Decimal("220000.00"),
                "fixed_guarantee": Decimal("300000.00"),
                "total_units": 2,
            },
            {
                "sku": "DEMO-CAR-03",
                "name": "DEMO - Cargador frontal compacto",
                "brand": "Demo",
                "model_name": "CF-03",
                "category": "carga",
                "daily_rate": Decimal("265000.00"),
                "fixed_guarantee": Decimal("350000.00"),
                "total_units": 2,
            },
            {
                "sku": "DEMO-ROD-10",
                "name": "DEMO - Rodillo compactador 10 t",
                "brand": "Demo",
                "model_name": "ROD-10",
                "category": "compactacion",
                "daily_rate": Decimal("190000.00"),
                "fixed_guarantee": Decimal("250000.00"),
                "total_units": 2,
            },
            {
                "sku": "DEMO-PLA-090",
                "name": "DEMO - Placa compactadora 90 kg",
                "brand": "Demo",
                "model_name": "PL-090",
                "category": "compactacion",
                "daily_rate": Decimal("35000.00"),
                "fixed_guarantee": Decimal("60000.00"),
                "total_units": 5,
            },
        ]
        created_machinery = 0
        for item in machine_data:
            category = categories[item.pop("category")]
            _, created = Machinery.objects.get_or_create(
                sku=item["sku"],
                defaults={
                    **item,
                    "category": category,
                    "description": "Equipo de demostración. Reemplazar por datos reales antes de publicar.",
                    "available_units": item["total_units"],
                },
            )
            created_machinery += int(created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Catálogo demo listo: {created_categories} categorías y "
                f"{created_machinery} equipos nuevos. Los registros existentes no se modificaron."
            )
        )

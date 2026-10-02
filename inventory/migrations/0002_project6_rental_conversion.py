import datetime

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def prepare_legacy_data(apps, schema_editor):
    """Drop ecommerce-only cart lines and orders before converting their schema."""
    CartItem = apps.get_model("inventory", "CartItem")
    Order = apps.get_model("inventory", "Order")
    CartItem.objects.all().delete()
    Order.objects.all().delete()


def copy_legacy_stock(apps, schema_editor):
    """Initialize physical availability from the former product stock balance."""
    Machinery = apps.get_model("inventory", "Machinery")
    for machinery in Machinery.objects.all().iterator():
        machinery.available_units = machinery.total_units
        machinery.save(update_fields=["available_units"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_project6_roles"),
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(prepare_legacy_data),
        migrations.RenameModel(old_name="Product", new_name="Machinery"),
        migrations.RenameModel(old_name="Order", new_name="RentalContract"),
        migrations.RenameModel(old_name="OrderItem", new_name="RentalContractItem"),
        migrations.RenameField(model_name="machinery", old_name="price", new_name="daily_rate"),
        migrations.RenameField(model_name="machinery", old_name="stock", new_name="total_units"),
        migrations.RenameField(model_name="rentalcontractitem", old_name="order", new_name="contract"),
        migrations.RenameField(model_name="rentalcontractitem", old_name="product", new_name="machinery"),
        migrations.RenameField(model_name="rentalcontractitem", old_name="product_name", new_name="machinery_name"),
        migrations.RenameField(model_name="rentalcontractitem", old_name="product_sku", new_name="machinery_sku"),
        migrations.RenameField(model_name="rentalcontractitem", old_name="unit_price", new_name="daily_rate"),
        migrations.RenameField(model_name="cartitem", old_name="product", new_name="machinery"),
        migrations.RemoveConstraint(model_name="machinery", name="product_stock_nonnegative"),
        migrations.RemoveConstraint(model_name="machinery", name="product_price_nonnegative"),
        migrations.RemoveConstraint(model_name="rentalcontractitem", name="order_item_quantity_positive"),
        migrations.RemoveConstraint(model_name="cartitem", name="unique_product_per_cart"),
        migrations.AddField(
            model_name="machinery",
            name="model_name",
            field=models.CharField(blank=True, max_length=100, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="machinery",
            name="fixed_guarantee",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="machinery",
            name="available_units",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(copy_legacy_stock, migrations.RunPython.noop),
        migrations.AddField(
            model_name="cartitem",
            name="start_date",
            field=models.DateField(default=datetime.date(2000, 1, 1)),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="cartitem",
            name="end_date",
            field=models.DateField(default=datetime.date(2000, 1, 2)),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="rentalcontract",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="rentalcontractitem",
            name="start_date",
            field=models.DateField(default=datetime.date(2000, 1, 1)),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="rentalcontractitem",
            name="end_date",
            field=models.DateField(default=datetime.date(2000, 1, 2)),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="rentalcontractitem",
            name="fixed_guarantee",
            field=models.DecimalField(decimal_places=2, max_digits=10),
        ),
        migrations.AlterField(
            model_name="machinery",
            name="category",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="machinery",
                to="inventory.category",
            ),
        ),
        migrations.AlterField(
            model_name="machinery",
            name="daily_rate",
            field=models.DecimalField(decimal_places=2, max_digits=10),
        ),
        migrations.AlterField(
            model_name="rentalcontract",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="rental_contracts",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="rentalcontractitem",
            name="machinery",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="contract_items",
                to="inventory.machinery",
            ),
        ),
        migrations.AlterField(
            model_name="cartitem",
            name="machinery",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="cart_items",
                to="inventory.machinery",
            ),
        ),
        migrations.AlterField(
            model_name="rentalcontract",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDIENTE", "Pendiente"),
                    ("PAGADO", "Pagado"),
                    ("ENTREGADO", "Entregado"),
                    ("COMPLETADO", "Completado"),
                    ("CANCELADO", "Cancelado"),
                ],
                default="PENDIENTE",
                max_length=12,
            ),
        ),
        migrations.AddConstraint(
            model_name="machinery",
            constraint=models.CheckConstraint(
                condition=models.Q(("available_units__gte", 0)),
                name="machinery_available_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="machinery",
            constraint=models.CheckConstraint(
                condition=models.Q(("available_units__lte", models.F("total_units"))),
                name="machinery_available_lte_total",
            ),
        ),
        migrations.AddConstraint(
            model_name="machinery",
            constraint=models.CheckConstraint(
                condition=models.Q(("daily_rate__gte", 0)),
                name="machinery_rate_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="machinery",
            constraint=models.CheckConstraint(
                condition=models.Q(("fixed_guarantee__gte", 0)),
                name="machinery_guarantee_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="cartitem",
            constraint=models.UniqueConstraint(
                fields=("cart", "machinery"), name="unique_machinery_per_cart"
            ),
        ),
        migrations.AddConstraint(
            model_name="cartitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("end_date__gt", models.F("start_date"))),
                name="cart_item_valid_dates",
            ),
        ),
        migrations.AddConstraint(
            model_name="rentalcontractitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("quantity__gt", 0)),
                name="contract_item_quantity_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="rentalcontractitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("end_date__gt", models.F("start_date"))),
                name="contract_item_valid_dates",
            ),
        ),
    ]
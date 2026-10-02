from django.db import migrations, models


def convert_existing_roles(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(role="CLIENTE").update(role="EMPRESA_CONSTRUCTORA")
    User.objects.filter(role="ADMINISTRADOR").update(role="EJECUTIVO_ARRIENDOS")


def restore_existing_roles(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(role="EMPRESA_CONSTRUCTORA").update(role="CLIENTE")
    User.objects.filter(role="EJECUTIVO_ARRIENDOS").update(role="ADMINISTRADOR")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(convert_existing_roles, restore_existing_roles),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("EMPRESA_CONSTRUCTORA", "Empresa Constructora"),
                    ("EJECUTIVO_ARRIENDOS", "Ejecutivo de Arriendos"),
                ],
                default="EMPRESA_CONSTRUCTORA",
                max_length=20,
            ),
        ),
    ]
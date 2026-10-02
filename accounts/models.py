from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = "EMPRESA_CONSTRUCTORA", "Empresa Constructora"
        ADMIN = "EJECUTIVO_ARRIENDOS", "Ejecutivo de Arriendos"

    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
    )

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

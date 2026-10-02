import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Category(models.Model):
    """Clasificación de maquinaria administrada por el ejecutivo de arriendos."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Machinery(models.Model):
    """Equipo arrendable con flota, tarifa diaria y garantía fija."""

    name = models.CharField(max_length=150)
    brand = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100, blank=True)
    sku = models.CharField(max_length=40, unique=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="machinery")
    daily_rate = models.DecimalField(max_digits=10, decimal_places=2)
    fixed_guarantee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_units = models.PositiveIntegerField(default=0)
    available_units = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=Q(available_units__gte=0), name="machinery_available_nonnegative"),
            models.CheckConstraint(condition=Q(available_units__lte=models.F("total_units")), name="machinery_available_lte_total"),
            models.CheckConstraint(condition=Q(daily_rate__gte=0), name="machinery_rate_nonnegative"),
            models.CheckConstraint(condition=Q(fixed_guarantee__gte=0), name="machinery_guarantee_nonnegative"),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"


class Cart(models.Model):
    """Carro persistente único por usuario, independiente de su sesión."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Carro de {self.user.username}"


class CartItem(models.Model):
    """Solicitud fechada que no reserva unidades de la flota."""

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    machinery = models.ForeignKey(Machinery, on_delete=models.PROTECT, related_name="cart_items")
    quantity = models.PositiveIntegerField(default=1)
    start_date = models.DateField()
    end_date = models.DateField()
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cart", "machinery"], name="unique_machinery_per_cart"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="cart_item_quantity_positive"),
            models.CheckConstraint(condition=Q(end_date__gt=models.F("start_date")), name="cart_item_valid_dates"),
        ]


class RentalContract(models.Model):
    """Contrato de arriendo con estados válidos y trazabilidad de pago."""

    class Status(models.TextChoices):
        PENDING = "PENDIENTE", "Pendiente"
        PAID = "PAGADO", "Pagado"
        DELIVERED = "ENTREGADO", "Entregado"
        COMPLETED = "COMPLETADO", "Completado"
        CANCELLED = "CANCELADO", "Cancelado"

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="rental_contracts")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def total_cost(self):
        return sum((item.total_cost for item in self.items.all()), start=0)

    def __str__(self):
        return f"Contrato {self.reference} ({self.get_status_display()})"


class RentalContractItem(models.Model):
    """Snapshot de equipo, fechas, tarifa y garantía acordadas al confirmar."""

    contract = models.ForeignKey(RentalContract, on_delete=models.CASCADE, related_name="items")
    machinery = models.ForeignKey(Machinery, on_delete=models.PROTECT, related_name="contract_items")
    machinery_name = models.CharField(max_length=150)
    machinery_sku = models.CharField(max_length=40)
    quantity = models.PositiveIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    daily_rate = models.DecimalField(max_digits=10, decimal_places=2)
    fixed_guarantee = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="contract_item_quantity_positive"),
            models.CheckConstraint(condition=Q(end_date__gt=models.F("start_date")), name="contract_item_valid_dates"),
        ]

    @property
    def rental_days(self):
        return (self.end_date - self.start_date).days

    @property
    def rental_cost(self):
        return self.daily_rate * self.rental_days * self.quantity

    @property
    def total_cost(self):
        return self.rental_cost + self.fixed_guarantee * self.quantity

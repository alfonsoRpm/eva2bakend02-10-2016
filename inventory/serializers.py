"""Validación y representación de maquinaria, carros fechados y contratos."""

from decimal import Decimal

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from .models import Cart, CartItem, Category, Machinery, RentalContract, RentalContractItem


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description"]


class StockAdditionSerializer(serializers.Serializer):
    cantidad = serializers.IntegerField(min_value=1)


class StockRemovalSerializer(serializers.Serializer):
    cantidad = serializers.IntegerField(min_value=1)


class StockAdditionResponseSerializer(serializers.Serializer):
    mensaje = serializers.CharField()
    maquinaria = serializers.IntegerField()
    unidades_totales = serializers.IntegerField()
    unidades_disponibles = serializers.IntegerField()


class MachinerySerializer(serializers.ModelSerializer):
    """Convertir datos del catálogo y mantener flota disponible consistente."""

    nombre = serializers.CharField(source="name")
    marca = serializers.CharField(source="brand")
    modelo = serializers.CharField(source="model_name", required=False, allow_blank=True)
    descripcion = serializers.CharField(source="description", required=False, allow_blank=True)
    categoria = serializers.PrimaryKeyRelatedField(
        source="category", queryset=Category.objects.all()
    )
    categoria_nombre = serializers.CharField(source="category.name", read_only=True)
    tarifa_diaria = serializers.DecimalField(source="daily_rate", max_digits=10, decimal_places=2)
    garantia_fija = serializers.DecimalField(
        source="fixed_guarantee", max_digits=10, decimal_places=2
    )
    unidades_totales = serializers.IntegerField(source="total_units", min_value=0)
    unidades_disponibles = serializers.IntegerField(source="available_units", read_only=True)

    class Meta:
        model = Machinery
        fields = [
            "id",
            "nombre",
            "marca",
            "modelo",
            "sku",
            "descripcion",
            "categoria",
            "categoria_nombre",
            "tarifa_diaria",
            "garantia_fija",
            "unidades_totales",
            "unidades_disponibles",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "unidades_disponibles", "created_at", "updated_at"]

    def validate(self, attrs):
        total_units = attrs.get("total_units")
        if self.instance is not None and total_units is not None:
            rented_units = self.instance.total_units - self.instance.available_units
            if total_units < rented_units:
                raise serializers.ValidationError(
                    {"unidades_totales": "No puede ser menor que las unidades actualmente arrendadas."}
                )
        return attrs

    def create(self, validated_data):
        validated_data["available_units"] = validated_data["total_units"]
        return super().create(validated_data)

    def update(self, instance, validated_data):
        total_units = validated_data.pop("total_units", instance.total_units)
        rented_units = instance.total_units - instance.available_units
        instance.total_units = total_units
        instance.available_units = total_units - rented_units
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class CartItemInputSerializer(serializers.Serializer):
    """Exigir cantidad positiva y fechas cronológicas para cada solicitud."""

    maquinaria = serializers.PrimaryKeyRelatedField(
        source="machinery", queryset=Machinery.objects.all()
    )
    cantidad = serializers.IntegerField(source="quantity", min_value=1)
    fecha_inicio = serializers.DateField(source="start_date")
    fecha_fin = serializers.DateField(source="end_date")

    def validate(self, attrs):
        if attrs["end_date"] <= attrs["start_date"]:
            raise serializers.ValidationError(
                {"fecha_fin": "Debe ser posterior a fecha_inicio."}
            )
        return attrs


class CartLineSerializer(serializers.ModelSerializer):
    """Representar una línea persistente e incluir su costo calculado."""

    maquinaria = serializers.PrimaryKeyRelatedField(source="machinery", read_only=True)
    maquinaria_nombre = serializers.CharField(source="machinery.name", read_only=True)
    maquinaria_sku = serializers.CharField(source="machinery.sku", read_only=True)
    cantidad = serializers.IntegerField(source="quantity", read_only=True)
    fecha_inicio = serializers.DateField(source="start_date", read_only=True)
    fecha_fin = serializers.DateField(source="end_date", read_only=True)
    tarifa_diaria = serializers.DecimalField(
        source="machinery.daily_rate",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    garantia_fija = serializers.DecimalField(
        source="machinery.fixed_guarantee",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    dias = serializers.SerializerMethodField()
    costo_total = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "id", "maquinaria", "maquinaria_nombre", "maquinaria_sku", "cantidad",
            "fecha_inicio", "fecha_fin", "tarifa_diaria", "garantia_fija", "dias",
            "costo_total",
        ]

    @extend_schema_field(serializers.IntegerField())
    def get_dias(self, obj) -> int:
        return (obj.end_date - obj.start_date).days

    @extend_schema_field(serializers.DecimalField(max_digits=12, decimal_places=2))
    def get_costo_total(self, obj) -> Decimal:
        days = (obj.end_date - obj.start_date).days
        return (obj.machinery.daily_rate * days + obj.machinery.fixed_guarantee) * obj.quantity


class CartSerializer(serializers.ModelSerializer):
    items = CartLineSerializer(many=True, read_only=True)
    costo_total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ["id", "items", "costo_total", "created_at", "updated_at"]

    @extend_schema_field(serializers.DecimalField(max_digits=12, decimal_places=2))
    def get_costo_total(self, obj) -> Decimal:
        return sum(
            (
                (item.machinery.daily_rate * (item.end_date - item.start_date).days
                 + item.machinery.fixed_guarantee) * item.quantity
                for item in obj.items.all()
            ),
            start=Decimal("0"),
        )


class RentalContractItemSerializer(serializers.ModelSerializer):
    """Representar el snapshot inmutable de equipo, período, tarifa y garantía."""

    maquinaria = serializers.PrimaryKeyRelatedField(source="machinery", read_only=True)
    maquinaria_nombre = serializers.CharField(source="machinery_name", read_only=True)
    maquinaria_sku = serializers.CharField(source="machinery_sku", read_only=True)
    cantidad = serializers.IntegerField(source="quantity", read_only=True)
    fecha_inicio = serializers.DateField(source="start_date", read_only=True)
    fecha_fin = serializers.DateField(source="end_date", read_only=True)
    dias = serializers.IntegerField(source="rental_days", read_only=True)
    costo_arriendo = serializers.DecimalField(source="rental_cost", max_digits=12, decimal_places=2, read_only=True)
    costo_total = serializers.DecimalField(source="total_cost", max_digits=12, decimal_places=2, read_only=True)
    tarifa_diaria = serializers.DecimalField(source="daily_rate", max_digits=10, decimal_places=2, read_only=True)
    garantia_fija = serializers.DecimalField(source="fixed_guarantee", max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = RentalContractItem
        fields = [
            "id", "maquinaria", "maquinaria_nombre", "maquinaria_sku", "cantidad",
            "fecha_inicio", "fecha_fin", "dias", "tarifa_diaria", "garantia_fija",
            "costo_arriendo", "costo_total",
        ]
        read_only_fields = fields


class RentalContractSerializer(serializers.ModelSerializer):
    """Exponer el contrato completo con cliente, estado y total calculado."""

    items = RentalContractItemSerializer(many=True, read_only=True)
    costo_total = serializers.DecimalField(source="total_cost", max_digits=12, decimal_places=2, read_only=True)
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = RentalContract
        fields = [
            "id",
            "reference",
            "user",
            "user_name",
            "status",
            "items",
            "costo_total",
            "created_at",
            "updated_at",
            "paid_at",
            "completed_at",
        ]
        read_only_fields = fields


class RentalContractStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=RentalContract.Status.choices)

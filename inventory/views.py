"""Vistas REST para catálogo público, arriendos de clientes y gestión ejecutiva."""

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema

from accounts.permissions import IsAdminOrReadOnly, IsAdministrator, IsCustomer

from .filters import MachineryFilter
from .models import Cart, Category, Machinery, RentalContract
from .serializers import (
    CartItemInputSerializer,
    CartSerializer,
    CategorySerializer,
    MachinerySerializer,
    RentalContractSerializer,
    RentalContractStatusSerializer,
    StockAdditionSerializer,
    StockAdditionResponseSerializer,
    StockRemovalSerializer,
)
from .services import change_contract_status, checkout, remove_cart_item, set_cart_item


class CatalogPermissionsMixin:
    """Permitir lectura pública y reservar toda escritura al ejecutivo de arriendos."""

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [IsAdministrator()]


class CategoryViewSet(CatalogPermissionsMixin, viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class MachineryViewSet(viewsets.ModelViewSet):
    """Exponer el catálogo filtrable y las operaciones CRUD de maquinaria."""

    queryset = Machinery.objects.select_related("category").all()
    serializer_class = MachinerySerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_class = MachineryFilter
    search_fields = ["name", "brand", "model_name", "sku", "description", "category__name"]
    ordering_fields = ["name", "daily_rate", "available_units", "created_at"]


class AgregarStockView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        request=StockAdditionSerializer,
        responses={status.HTTP_200_OK: StockAdditionResponseSerializer},
    )
    @transaction.atomic
    def patch(self, request, pk):
        serializer = StockAdditionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # El bloqueo serializa las entradas concurrentes para esta maquinaria.
        machinery = get_object_or_404(
            Machinery.objects.select_for_update(),
            pk=pk,
        )
        quantity = serializer.validated_data["cantidad"]
        machinery.total_units += quantity
        machinery.available_units += quantity
        machinery.save(update_fields=["total_units", "available_units", "updated_at"])

        return Response(
            {
                "mensaje": "Stock agregado correctamente.",
                "maquinaria": machinery.pk,
                "unidades_totales": machinery.total_units,
                "unidades_disponibles": machinery.available_units,
            },
            status=status.HTTP_200_OK,
        )


class RetirarStockView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        request=StockRemovalSerializer,
        responses={status.HTTP_200_OK: StockAdditionResponseSerializer},
    )
    @transaction.atomic
    def patch(self, request, pk):
        serializer = StockRemovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        machinery = get_object_or_404(
            Machinery.objects.select_for_update(),
            pk=pk,
        )
        quantity = serializer.validated_data["cantidad"]
        if quantity > machinery.available_units:
            raise ValidationError(
                {
                    "cantidad": (
                        f"Solo puedes retirar hasta {machinery.available_units} "
                        "unidades disponibles."
                    )
                }
            )

        machinery.total_units -= quantity
        machinery.available_units -= quantity
        machinery.save(update_fields=["total_units", "available_units", "updated_at"])
        return Response(
            {
                "mensaje": "Stock retirado correctamente.",
                "maquinaria": machinery.pk,
                "unidades_totales": machinery.total_units,
                "unidades_disponibles": machinery.available_units,
            },
            status=status.HTTP_200_OK,
        )


class RentalCartView(APIView):
    """Administrar el carro persistente de arriendo de la empresa autenticada."""

    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(responses=CartSerializer)
    def get(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart = Cart.objects.prefetch_related("items__machinery").get(pk=cart.pk)
        return Response(CartSerializer(cart).data)

    @extend_schema(request=CartItemInputSerializer, responses=CartSerializer)
    def post(self, request):
        item_serializer = CartItemInputSerializer(data=request.data)
        item_serializer.is_valid(raise_exception=True)
        cart = set_cart_item(
            user=request.user,
            machinery=item_serializer.validated_data["machinery"],
            quantity=item_serializer.validated_data["quantity"],
            start_date=item_serializer.validated_data["start_date"],
            end_date=item_serializer.validated_data["end_date"],
        )
        cart = Cart.objects.prefetch_related("items__machinery").get(pk=cart.pk)
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)

    @extend_schema(request=None, responses={204: None})
    def delete(self, request):
        raw_machinery_id = request.query_params.get("machinery_id")
        if raw_machinery_id is None:
            raise ValidationError({"machinery_id": "Este parámetro es obligatorio."})
        try:
            machinery_id = int(raw_machinery_id)
        except ValueError as exc:
            raise ValidationError({"machinery_id": "Debe ser un identificador numérico."}) from exc

        remove_cart_item(user=request.user, machinery_id=machinery_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ContractCheckoutView(APIView):
    """Validar el carro y generar un contrato pendiente."""

    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(request=None, responses={201: RentalContractSerializer})
    def post(self, request):
        contract = checkout(user=request.user)
        contract = RentalContract.objects.prefetch_related("items").get(pk=contract.pk)
        return Response(RentalContractSerializer(contract).data, status=status.HTTP_201_CREATED)


class MyContractsView(generics.ListAPIView):
    """Listar únicamente los contratos de la empresa constructora autenticada."""

    queryset = RentalContract.objects.none()
    serializer_class = RentalContractSerializer
    permission_classes = [IsAuthenticated, IsCustomer]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return RentalContract.objects.none()
        return (
            RentalContract.objects.filter(user=self.request.user)
            .prefetch_related("items")
            .order_by("-created_at")
        )


class ExecutiveContractsView(generics.ListAPIView):
    """Permitir al ejecutivo revisar contratos para gestionar sus estados."""

    queryset = RentalContract.objects.all().prefetch_related("items")
    serializer_class = RentalContractSerializer
    permission_classes = [IsAuthenticated, IsAdministrator]


class ContractStatusView(APIView):
    """Restringir transiciones de contrato a usuarios de personal."""

    permission_classes = [IsAdminUser]

    @extend_schema(request=RentalContractStatusSerializer, responses=RentalContractSerializer)
    def patch(self, request, pk):
        status_serializer = RentalContractStatusSerializer(data=request.data)
        status_serializer.is_valid(raise_exception=True)
        contract = change_contract_status(
            contract_id=pk,
            new_status=status_serializer.validated_data["status"],
        )
        contract = RentalContract.objects.prefetch_related("items").get(pk=contract.pk)
        return Response(RentalContractSerializer(contract).data)

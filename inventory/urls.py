from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
	AgregarStockView,
	RetirarStockView,
	RentalCartView,
	CategoryViewSet,
	ContractCheckoutView,
	ExecutiveContractsView,
	MyContractsView,
	ContractStatusView,
	MachineryViewSet,
)


router = DefaultRouter()
router.register("categorias", CategoryViewSet, basename="categoria")
router.register("maquinarias", MachineryViewSet, basename="maquinaria")

urlpatterns = [
	path("maquinarias/<int:pk>/agregar-stock/", AgregarStockView.as_view(), name="maquinaria-agregar-stock"),
	path("maquinarias/<int:pk>/retirar-stock/", RetirarStockView.as_view(), name="maquinaria-retirar-stock"),
	path("carro-arriendo/", RentalCartView.as_view(), name="carro-arriendo"),
	path("contratos/", ExecutiveContractsView.as_view(), name="contrato-lista-ejecutiva"),
	path("contratos/checkout/", ContractCheckoutView.as_view(), name="contrato-checkout"),
	path("mis-contratos/", MyContractsView.as_view(), name="mis-contratos"),
	path("contratos/<int:pk>/estado/", ContractStatusView.as_view(), name="contrato-estado"),
] + router.urls

from datetime import date
from decimal import Decimal

from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from .models import CartItem, Category, Machinery, RentalContract, RentalContractItem


class MachineryRentalApiTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Excavadoras", slug="excavadoras")
        self.machinery = Machinery.objects.create(
            name="Excavadora de prueba",
            brand="MaquiLab",
            model_name="EX-200",
            sku="EXC-001",
            description="Equipo para pruebas de arriendo",
            category=self.category,
            daily_rate=Decimal("850.00"),
            fixed_guarantee=Decimal("1000.00"),
            total_units=5,
            available_units=5,
        )
        self.customer = User.objects.create_user(
            username="constructora",
            email="cliente@example.com",
            password="ClaveSegura123!",
        )
        self.executive = User.objects.create_user(
            username="ejecutivo",
            email="ejecutivo@example.com",
            password="ClaveSegura123!",
            role=User.Role.ADMIN,
            is_staff=True,
        )

    def authenticate_as_customer(self):
        self.client.force_authenticate(user=self.customer)

    def authenticate_as_executive(self):
        self.client.force_authenticate(user=self.executive)

    def add_to_cart(self, machinery=None, quantity=1, start="2026-11-01", end="2026-11-04"):
        return self.client.post(
            "/api/carro-arriendo/",
            {
                "maquinaria": (machinery or self.machinery).pk,
                "cantidad": quantity,
                "fecha_inicio": start,
                "fecha_fin": end,
            },
            format="json",
        )

    def checkout_contract(self):
        response = self.client.post("/api/contratos/checkout/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return RentalContract.objects.get(pk=response.data["id"])

    def change_status(self, contract, new_status):
        return self.client.patch(
            f"/api/contratos/{contract.pk}/estado/",
            {"status": new_status},
            format="json",
        )

    def test_public_machinery_catalog_filters_by_category_and_daily_rate(self):
        response = self.client.get(
            f"/api/maquinarias/?category={self.category.pk}&tarifa_min=500&tarifa_max=1000"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["sku"], "EXC-001")
        self.assertEqual(self.client.get("/api/categorias/").status_code, status.HTTP_200_OK)

    def test_staff_can_add_stock_without_losing_existing_reservations(self):
        Machinery.objects.filter(pk=self.machinery.pk).update(available_units=3)
        self.authenticate_as_customer()
        denied = self.client.patch(
            f"/api/maquinarias/{self.machinery.pk}/agregar-stock/",
            {"cantidad": 2},
            format="json",
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        self.authenticate_as_executive()
        added = self.client.patch(
            f"/api/maquinarias/{self.machinery.pk}/agregar-stock/",
            {"cantidad": 2},
            format="json",
        )
        self.machinery.refresh_from_db()

        self.assertEqual(added.status_code, status.HTTP_200_OK)
        self.assertEqual(self.machinery.total_units, 7)
        self.assertEqual(self.machinery.available_units, 5)
        self.assertEqual(added.data["unidades_disponibles"], 5)

    def test_add_stock_rejects_invalid_amount_and_missing_machinery(self):
        self.authenticate_as_executive()

        invalid = self.client.patch(
            f"/api/maquinarias/{self.machinery.pk}/agregar-stock/",
            {"cantidad": 0},
            format="json",
        )
        missing = self.client.patch(
            "/api/maquinarias/99999/agregar-stock/",
            {"cantidad": 1},
            format="json",
        )

        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)

    def test_staff_can_remove_only_available_stock(self):
        Machinery.objects.filter(pk=self.machinery.pk).update(available_units=3)
        self.authenticate_as_executive()

        removed = self.client.patch(
            f"/api/maquinarias/{self.machinery.pk}/retirar-stock/",
            {"cantidad": 2},
            format="json",
        )
        self.machinery.refresh_from_db()
        self.assertEqual(removed.status_code, status.HTTP_200_OK)
        self.assertEqual(self.machinery.total_units, 3)
        self.assertEqual(self.machinery.available_units, 1)

        excessive = self.client.patch(
            f"/api/maquinarias/{self.machinery.pk}/retirar-stock/",
            {"cantidad": 2},
            format="json",
        )
        self.machinery.refresh_from_db()
        self.assertEqual(excessive.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.machinery.total_units, 3)
        self.assertEqual(self.machinery.available_units, 1)

    def test_jwt_contains_human_readable_role_and_refresh_token(self):
        registration = self.client.post(
            "/api/auth/register/",
            {
                "username": "nueva-constructora",
                "email": "nueva@example.com",
                "password": "OtraClave123!",
            },
            format="json",
        )
        token_response = self.client.post(
            "/api/auth/token/",
            {"username": "nueva-constructora", "password": "OtraClave123!"},
            format="json",
        )

        self.assertEqual(registration.status_code, status.HTTP_201_CREATED)
        self.assertEqual(token_response.status_code, status.HTTP_200_OK)
        self.assertEqual(token_response.data["user"]["role"], "Empresa Constructora")
        self.assertFalse(token_response.data["user"]["is_staff"])
        access_token = AccessToken(token_response.data["access"])
        self.assertEqual(access_token["role"], "Empresa Constructora")
        self.assertIn("refresh", token_response.data)

    def test_staff_token_exposes_admin_access_to_frontend(self):
        response = self.client.post(
            "/api/auth/token/",
            {"username": "ejecutivo", "password": "ClaveSegura123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["user"]["is_staff"])

    def test_cart_persists_dates_and_calculates_rental_plus_guarantee(self):
        self.authenticate_as_customer()
        added = self.add_to_cart(quantity=2)
        self.assertEqual(added.status_code, status.HTTP_200_OK)
        self.machinery.refresh_from_db()
        self.assertEqual(self.machinery.available_units, 5)
        self.assertEqual(added.data["items"][0]["costo_total"], Decimal("7100.00"))

        self.client.force_authenticate(user=None)
        another_device = APIClient()
        another_device.force_authenticate(user=self.customer)
        response = another_device.get("/api/carro-arriendo/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items"][0]["fecha_inicio"], "2026-11-01")
        self.assertEqual(CartItem.objects.count(), 1)

    def test_invalid_dates_are_rejected(self):
        self.authenticate_as_customer()
        response = self.add_to_cart(start="2026-11-04", end="2026-11-01")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_checkout_snapshots_cost_and_reserves_units(self):
        self.authenticate_as_customer()
        self.add_to_cart(quantity=2)
        Machinery.objects.filter(pk=self.machinery.pk).update(daily_rate=Decimal("900.00"))

        contract = self.checkout_contract()
        item = RentalContractItem.objects.get(contract=contract)
        self.machinery.refresh_from_db()

        self.assertEqual(contract.status, RentalContract.Status.PENDING)
        self.assertEqual(item.daily_rate, Decimal("900.00"))
        self.assertEqual(item.start_date, date(2026, 11, 1))
        self.assertEqual(item.end_date, date(2026, 11, 4))
        self.assertEqual(self.machinery.available_units, 3)
        self.assertEqual(CartItem.objects.count(), 0)

    def test_checkout_reserves_stock_catalog_updates_and_overbooking_is_rejected(self):
        self.authenticate_as_customer()
        self.add_to_cart(quantity=4)
        contract = self.checkout_contract()
        self.machinery.refresh_from_db()
        self.assertEqual(self.machinery.available_units, 1)
        catalog = self.client.get("/api/maquinarias/")
        listed_machine = next(
            item for item in catalog.data["results"] if item["id"] == self.machinery.pk
        )
        self.assertEqual(listed_machine["unidades_disponibles"], 1)

        second_customer = User.objects.create_user(
            username="constructora-reserva", email="reserva@example.com", password="ClaveSegura123!"
        )
        self.client.force_authenticate(user=second_customer)
        self.add_to_cart(quantity=2)
        second_checkout = self.client.post("/api/contratos/checkout/", {}, format="json")
        self.assertEqual(second_checkout.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("No hay unidades libres", second_checkout.data["detail"])
        self.machinery.refresh_from_db()
        self.assertEqual(self.machinery.available_units, 1)

        self.authenticate_as_executive()
        paid = self.change_status(contract, RentalContract.Status.PAID)
        self.assertEqual(paid.status_code, status.HTTP_200_OK)
        self.machinery.refresh_from_db()
        self.assertEqual(self.machinery.available_units, 1)

    def test_cancelling_paid_contract_releases_reserved_stock(self):
        self.authenticate_as_customer()
        self.add_to_cart(quantity=2)
        contract = self.checkout_contract()
        self.machinery.refresh_from_db()
        self.assertEqual(self.machinery.available_units, 3)

        self.authenticate_as_executive()
        paid = self.change_status(contract, RentalContract.Status.PAID)
        self.machinery.refresh_from_db()
        self.assertEqual(paid.status_code, status.HTTP_200_OK)
        self.assertEqual(self.machinery.available_units, 3)

        cancelled = self.change_status(contract, RentalContract.Status.CANCELLED)
        self.machinery.refresh_from_db()

        self.assertEqual(cancelled.status_code, status.HTTP_200_OK)
        self.assertEqual(self.machinery.available_units, 5)

    def test_overlapping_paid_contract_rejects_checkout(self):
        self.authenticate_as_customer()
        self.add_to_cart(quantity=4)
        first_contract = self.checkout_contract()
        self.authenticate_as_executive()
        self.assertEqual(
            self.change_status(first_contract, RentalContract.Status.PAID).status_code,
            status.HTTP_200_OK,
        )

        second_customer = User.objects.create_user(
            username="constructora2", email="cliente2@example.com", password="ClaveSegura123!"
        )
        self.client.force_authenticate(user=second_customer)
        self.add_to_cart(quantity=2)
        response = self.client.post("/api/contratos/checkout/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("No hay unidades libres", response.data["detail"])

    def test_paid_contract_decrements_units_and_completion_restores_them(self):
        self.authenticate_as_customer()
        self.add_to_cart(quantity=4)
        contract = self.checkout_contract()
        self.machinery.refresh_from_db()
        self.assertEqual(self.machinery.available_units, 1)
        self.authenticate_as_executive()

        paid = self.change_status(contract, RentalContract.Status.PAID)
        self.machinery.refresh_from_db()
        self.assertEqual(paid.status_code, status.HTTP_200_OK)
        self.assertEqual(self.machinery.available_units, 1)

        delivered = self.change_status(contract, RentalContract.Status.DELIVERED)
        self.assertEqual(delivered.status_code, status.HTTP_200_OK)
        completed = self.change_status(contract, RentalContract.Status.COMPLETED)
        self.machinery.refresh_from_db()
        self.assertEqual(completed.status_code, status.HTTP_200_OK)
        self.assertEqual(self.machinery.available_units, 5)

    def test_payment_failure_rolls_back_without_decrementing_stock(self):
        other_machinery = Machinery.objects.create(
            name="Grúa de prueba",
            brand="MaquiLab",
            sku="GRU-001",
            category=self.category,
            daily_rate=Decimal("1200.00"),
            fixed_guarantee=Decimal("500.00"),
            total_units=1,
            available_units=1,
        )
        self.authenticate_as_customer()
        self.add_to_cart(quantity=2)
        self.add_to_cart(machinery=other_machinery, quantity=1)
        contract = self.checkout_contract()
        self.machinery.refresh_from_db()
        self.assertEqual(self.machinery.available_units, 3)
        blocking_contract = RentalContract.objects.create(
            user=self.customer,
            status=RentalContract.Status.PAID,
        )
        RentalContractItem.objects.create(
            contract=blocking_contract,
            machinery=other_machinery,
            machinery_name=other_machinery.name,
            machinery_sku=other_machinery.sku,
            quantity=1,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 4),
            daily_rate=other_machinery.daily_rate,
            fixed_guarantee=other_machinery.fixed_guarantee,
        )
        self.authenticate_as_executive()

        response = self.change_status(contract, RentalContract.Status.PAID)
        self.machinery.refresh_from_db()
        contract.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.machinery.available_units, 3)
        self.assertEqual(contract.status, RentalContract.Status.PENDING)

    def test_only_executive_can_manage_machinery_or_change_contract_status(self):
        self.authenticate_as_customer()
        self.add_to_cart()
        contract = self.checkout_contract()
        denied_status = self.change_status(contract, RentalContract.Status.PAID)
        denied_catalog_write = self.client.post("/api/maquinarias/", {}, format="json")

        self.assertEqual(denied_status.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(denied_catalog_write.status_code, status.HTTP_403_FORBIDDEN)

    def test_only_executive_can_list_all_contracts(self):
        contract = RentalContract.objects.create(user=self.customer)

        self.authenticate_as_customer()
        denied = self.client.get("/api/contratos/")
        self.authenticate_as_executive()
        allowed = self.client.get("/api/contratos/")

        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
        self.assertEqual(allowed.data["results"][0]["id"], contract.pk)

    def test_docs_and_student_footer_are_available(self):
        self.assertEqual(self.client.get("/api/docs/").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get("/api/schema/").status_code, status.HTTP_200_OK)
        home = self.client.get("/")
        self.assertEqual(home.status_code, status.HTTP_200_OK)
        self.assertContains(home, "Nombre Completo:")

    def test_unknown_page_redirects_home_without_hiding_api_404s(self):
        response = self.client.get("/lkjhgfd")

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(response["Location"], "/")
        docs_response = self.client.get("/api/docs/fghgnhnt")
        self.assertEqual(docs_response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(docs_response["Location"], "/api/docs/")
        self.assertEqual(self.client.get("/api/ruta-inexistente/").status_code, status.HTTP_404_NOT_FOUND)

    def test_demo_catalog_seed_is_idempotent(self):
        call_command("seed_demo_catalog")
        call_command("seed_demo_catalog")

        self.assertEqual(Machinery.objects.filter(sku__startswith="DEMO-").count(), 6)
        self.assertEqual(
            Category.objects.filter(slug__in=["excavadoras", "carga", "compactacion"]).count(),
            3,
        )

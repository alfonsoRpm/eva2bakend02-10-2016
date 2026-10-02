from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from .models import Cart, CartItem, Machinery, RentalContract, RentalContractItem


def _validate_date_range(*, start_date, end_date):
    if end_date <= start_date:
        raise ValidationError({"end_date": "Debe ser posterior a start_date."})


def _validate_period_availability(
    *, machinery, quantity, start_date, end_date, exclude_contract_id=None
):
    """Contar contratos activos cuyos períodos se cruzan con el solicitado."""
    active_statuses = [
        RentalContract.Status.PENDING,
        RentalContract.Status.PAID,
        RentalContract.Status.DELIVERED,
    ]
    items = RentalContractItem.objects.filter(
        machinery=machinery,
        contract__status__in=active_statuses,
        start_date__lt=end_date,
        end_date__gt=start_date,
    )
    if exclude_contract_id is not None:
        items = items.exclude(contract_id=exclude_contract_id)
    items = items.values_list("quantity", "start_date", "end_date")
    events = [(start_date, quantity), (end_date, -quantity)]
    for booked_quantity, booked_start, booked_end in items:
        events.append((max(start_date, booked_start), booked_quantity))
        events.append((min(end_date, booked_end), -booked_quantity))

    current_units = 0
    peak_units = 0
    for _, delta in sorted(events, key=lambda event: (event[0], event[1])):
        current_units += delta
        peak_units = max(peak_units, current_units)

    if peak_units > machinery.total_units:
        raise ValidationError(
            {"detail": f"No hay unidades libres de {machinery.name} para el período solicitado."}
        )


def _refresh_available_units(*, machinery: Machinery):
    """Actualizar la flota libre según el máximo uso simultáneo contratado."""
    active_statuses = [
        RentalContract.Status.PENDING,
        RentalContract.Status.PAID,
        RentalContract.Status.DELIVERED,
    ]
    items = RentalContractItem.objects.filter(
        machinery=machinery,
        contract__status__in=active_statuses,
    ).values_list("quantity", "start_date", "end_date")
    events = []
    for quantity, start_date, end_date in items:
        events.append((start_date, quantity))
        events.append((end_date, -quantity))

    current_units = 0
    peak_units = 0
    for _, delta in sorted(events, key=lambda event: (event[0], event[1])):
        current_units += delta
        peak_units = max(peak_units, current_units)

    Machinery.objects.filter(pk=machinery.pk).update(
        available_units=max(0, machinery.total_units - peak_units)
    )


@transaction.atomic
def set_cart_item(*, user, machinery: Machinery, quantity: int, start_date, end_date) -> Cart:
    """Guardar una solicitud fechada sin reservar unidades hasta el checkout."""
    if quantity <= 0:
        raise ValidationError({"quantity": "La cantidad debe ser mayor que cero."})
    _validate_date_range(start_date=start_date, end_date=end_date)

    cart, _ = Cart.objects.get_or_create(user=user)
    cart = Cart.objects.select_for_update().get(pk=cart.pk)
    CartItem.objects.update_or_create(
        cart=cart,
        machinery=machinery,
        defaults={"quantity": quantity, "start_date": start_date, "end_date": end_date},
    )
    Cart.objects.filter(pk=cart.pk).update(updated_at=timezone.now())
    return cart


@transaction.atomic
def remove_cart_item(*, user, machinery_id: int) -> Cart:
    """Eliminar una línea del carro persistente autenticado."""
    cart = Cart.objects.select_for_update().filter(user=user).first()
    if cart is None:
        raise NotFound("El usuario no tiene un carro activo.")
    deleted, _ = CartItem.objects.filter(cart=cart, machinery_id=machinery_id).delete()
    if not deleted:
        raise NotFound("La maquinaria no está en el carro.")
    Cart.objects.filter(pk=cart.pk).update(updated_at=timezone.now())
    return cart


@transaction.atomic
def checkout(*, user) -> RentalContract:
    """Validar y reservar el carro al crear su contrato pendiente."""
    cart = Cart.objects.select_for_update().filter(user=user).first()
    if cart is None:
        raise ValidationError({"detail": "El carro está vacío."})

    cart_items = list(
        CartItem.objects.select_related("machinery")
        .filter(cart=cart)
        .order_by("machinery_id")
    )
    if not cart_items:
        raise ValidationError({"detail": "El carro está vacío."})

    for item in cart_items:
        machinery = Machinery.objects.select_for_update().get(pk=item.machinery_id)
        _validate_period_availability(
            machinery=machinery,
            quantity=item.quantity,
            start_date=item.start_date,
            end_date=item.end_date,
        )
        item.machinery = machinery

    contract = RentalContract.objects.create(user=user)
    RentalContractItem.objects.bulk_create(
        [
            RentalContractItem(
                contract=contract,
                machinery=item.machinery,
                machinery_name=item.machinery.name,
                machinery_sku=item.machinery.sku,
                quantity=item.quantity,
                start_date=item.start_date,
                end_date=item.end_date,
                daily_rate=item.machinery.daily_rate,
                fixed_guarantee=item.machinery.fixed_guarantee,
            )
            for item in cart_items
        ]
    )
    for item in cart_items:
        _refresh_available_units(machinery=item.machinery)
    CartItem.objects.filter(cart=cart).delete()
    Cart.objects.filter(pk=cart.pk).update(updated_at=timezone.now())
    return contract


@transaction.atomic
def change_contract_status(*, contract_id: int, new_status: str) -> RentalContract:
    """Aplicar transiciones legales y movimientos de flota en una transacción."""
    allowed_transitions = {
        RentalContract.Status.PENDING: {
            RentalContract.Status.PAID,
            RentalContract.Status.CANCELLED,
        },
        RentalContract.Status.PAID: {
            RentalContract.Status.DELIVERED,
            RentalContract.Status.CANCELLED,
        },
        RentalContract.Status.DELIVERED: {
            RentalContract.Status.COMPLETED,
            RentalContract.Status.CANCELLED,
        },
    }

    try:
        contract = RentalContract.objects.select_for_update().get(pk=contract_id)
    except RentalContract.DoesNotExist as exc:
        raise NotFound("El contrato solicitado no existe.") from exc

    if new_status not in RentalContract.Status.values:
        raise ValidationError({"status": "El estado solicitado no es válido."})
    if new_status not in allowed_transitions.get(contract.status, set()):
        raise ValidationError(
            {"status": f"No se permite pasar de {contract.status} a {new_status}."}
        )

    contract_items = list(
        contract.items.select_related("machinery").order_by("machinery_id")
    )

    affected_machinery_ids = set()
    if new_status == RentalContract.Status.PAID:
        # El contrato ya reservó stock al crearse; el bloqueo evita pagos concurrentes incompatibles.
        for item in contract_items:
            machinery = Machinery.objects.select_for_update().get(pk=item.machinery_id)
            _validate_period_availability(
                machinery=machinery,
                quantity=item.quantity,
                start_date=item.start_date,
                end_date=item.end_date,
                exclude_contract_id=contract.pk,
            )
            affected_machinery_ids.add(machinery.pk)
        contract.paid_at = timezone.now()

    releases_units = new_status in {
        RentalContract.Status.CANCELLED,
        RentalContract.Status.COMPLETED,
    } and contract.status in {
        RentalContract.Status.PENDING,
        RentalContract.Status.PAID,
        RentalContract.Status.DELIVERED,
    }
    if releases_units:
        affected_machinery_ids.update(item.machinery_id for item in contract_items)

    if new_status == RentalContract.Status.COMPLETED:
        contract.completed_at = timezone.now()
    contract.status = new_status
    contract.save(update_fields=["status", "paid_at", "completed_at", "updated_at"])
    for machinery_id in sorted(affected_machinery_ids):
        machinery = Machinery.objects.select_for_update().get(pk=machinery_id)
        _refresh_available_units(machinery=machinery)
    return contract

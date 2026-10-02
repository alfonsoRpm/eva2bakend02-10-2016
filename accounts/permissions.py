from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import User


class IsAdminOrReadOnly(BasePermission):
    """Permitir lectura pública y exigir staff para mutar el catálogo."""

    message = "Se requiere una cuenta de personal para modificar el inventario."

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or bool(
            request.user and request.user.is_staff
        )


class IsCustomer(BasePermission):
    message = "Este recurso está disponible solo para empresas constructoras."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.CUSTOMER
        )


class IsAdministrator(BasePermission):
    message = "Se requiere el rol Ejecutivo de Arriendos."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                request.user.is_superuser
                or request.user.role == User.Role.ADMIN
            )
        )

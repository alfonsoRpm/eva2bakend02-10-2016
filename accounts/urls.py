from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import CustomerRegistrationView, RoleTokenObtainPairView


urlpatterns = [
    path("register/", CustomerRegistrationView.as_view(), name="customer-register"),
    path("token/", RoleTokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
]

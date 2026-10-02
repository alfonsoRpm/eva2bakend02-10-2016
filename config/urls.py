from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .views import HomeView


urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("inventory.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    re_path(
        r"^api/docs/.+$",
        RedirectView.as_view(url="/api/docs/", permanent=False),
        name="docs-fallback-redirect",
    ),
    re_path(
        r"^(?!api(?:/|$)|admin(?:/|$)).+$",
        RedirectView.as_view(url="/", permanent=False),
        name="fallback-redirect",
    ),
]

import django_filters

from .models import Machinery


class MachineryFilter(django_filters.FilterSet):
    category = django_filters.NumberFilter(field_name="category_id")
    tarifa_min = django_filters.NumberFilter(field_name="daily_rate", lookup_expr="gte")
    tarifa_max = django_filters.NumberFilter(field_name="daily_rate", lookup_expr="lte")

    class Meta:
        model = Machinery
        fields = ["category", "brand", "sku"]

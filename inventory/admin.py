from django.contrib import admin

from .models import Cart, CartItem, Category, Machinery, RentalContract, RentalContractItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")


@admin.register(Machinery)
class MachineryAdmin(admin.ModelAdmin):
    list_display = (
        "id", "name", "brand", "sku", "category", "daily_rate",
        "total_units", "available_units",
    )
    search_fields = ("name", "brand", "sku")
    list_filter = ("category", "brand")


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ("machinery", "quantity", "start_date", "end_date", "added_at")


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "created_at", "updated_at")
    search_fields = ("user__username", "user__email")
    inlines = (CartItemInline,)


class RentalContractItemInline(admin.TabularInline):
    model = RentalContractItem
    extra = 0
    can_delete = False
    readonly_fields = (
        "machinery", "machinery_name", "machinery_sku", "quantity",
        "start_date", "end_date", "daily_rate", "fixed_guarantee",
    )


@admin.register(RentalContract)
class RentalContractAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "status", "created_at", "paid_at", "completed_at")
    list_filter = ("status", "created_at")
    search_fields = ("reference", "user__username", "user__email")
    readonly_fields = ("reference", "user", "status", "created_at", "updated_at", "paid_at")
    inlines = (RentalContractItemInline,)

    def has_add_permission(self, request):
        return False

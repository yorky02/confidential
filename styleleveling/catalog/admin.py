from django.contrib import admin
from .models import (
    Store,
    Product,
    Listing,
    ListingImage,
    Membership,
    PriceHistory,
    SavedDeal,
    ListingReview,
    StoreRequest,
    SyncRun,
)

# Register your models here.

class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 1
    fields = ["image_url", "alt_text", "position"]


class ListingAdmin(admin.ModelAdmin):
    list_display = ['product', 'store', 'current_price', 'original_price', 'discount_percentage', 'is_promo_active' , 'last_checked_time']
    list_filter = ['store__store_name', 'product__brand_name', 'is_promo_active']
    search_fields = ['product__product_name', 'external_product_id', 'product__brand_name', 'store__store_name']
    readonly_fields = ['discount_percentage', 'last_checked_time', 'last_seen',]
    inlines = [ListingImageInline]


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ["store_name", "is_active", "is_guest_visible", "last_sync_at"]
    list_filter = ["is_active", "is_guest_visible"]
    search_fields = ["store_name"]

admin.site.register(Product)
admin.site.register(Listing, ListingAdmin)
admin.site.register(PriceHistory)
admin.site.register(SyncRun)
admin.site.register(Membership)
admin.site.register(SavedDeal)


@admin.register(ListingReview)
class ListingReviewAdmin(admin.ModelAdmin):
    list_display = ["listing", "user", "rating", "is_approved", "created_at"]
    list_filter = ["is_approved", "rating", "created_at"]
    search_fields = ["listing__product__product_name", "user__email", "reason"]
    actions = ["approve_reviews"]

    @admin.action(description="Approve selected reviews")
    def approve_reviews(self, request, queryset):
        queryset.update(is_approved=True)


@admin.register(StoreRequest)
class StoreRequestAdmin(admin.ModelAdmin):
    list_display = ["store_name", "website_url", "status", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["store_name", "website_url", "reason"]

from django.contrib import admin
from .models import Store, Product, Listing, PriceHistory, SyncRun

# Register your models here.

class ListingAdmin(admin.ModelAdmin):
    list_display = ['store', 'current_price', 'original_price', 'discount_percentage', 'is_promo_active' , 'last_checked_time']
    list_filter = ['store__store_name', 'product__brand_name', 'is_promo_active']
    search_fields = ['product__product_name', 'external_product_id', 'product__brand_name', 'store__store_name']
    readonly_fields = ['discount_percentage', 'last_checked_time', 'last_seen',]

admin.site.register(Store)
admin.site.register(Product)
admin.site.register(Listing, ListingAdmin)
admin.site.register(PriceHistory)
admin.site.register(SyncRun)


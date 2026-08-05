from rest_framework import serializers
from .models import Listing

class ListingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing
        fields = ['id', 'store', 'product', 'external_product_id', 'product_page_url', 'current_price', 'original_price', 'quantity', 'is_promo_active', 'is_discounted', 'discount_amount', 'discount_percentage', 'last_checked_time', 'last_seen']
        
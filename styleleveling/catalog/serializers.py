from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Listing, ListingImage, Membership, SavedDeal


class ListingImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingImage
        fields = ["id", "image_url", "alt_text", "position"]


class ListingSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source="store.store_name", read_only=True)
    product_name = serializers.CharField(source="product.product_name", read_only=True)
    brand_name = serializers.CharField(source="product.brand_name", read_only=True)
    category = serializers.CharField(source="product.category", read_only=True)
    image_urls = serializers.SerializerMethodField()
    images = ListingImageSerializer(many=True, read_only=True)
    outbound_url = serializers.URLField(read_only=True)

    class Meta:
        model = Listing
        fields = [
            "id", "store", "store_name", "product", "product_name",
            "brand_name", "category", "external_product_id",
            "product_page_url", "affiliate_url", "outbound_url",
            "current_price", "original_price", "quantity", "is_promo_active",
            "is_discounted", "discount_amount", "discount_percentage",
            "image_urls", "images", "last_checked_time", "last_seen",
        ]

    def get_image_urls(self, listing):
        urls = [image.image_url for image in listing.images.all()]
        if not urls and listing.product.image_url:
            urls.append(listing.product.image_url)
        return urls


class MemberSignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)

    def validate_email(self, value):
        user_model = get_user_model()
        if user_model.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value.lower()

    def create(self, validated_data):
        user_model = get_user_model()
        email = validated_data["email"]
        user = user_model.objects.create_user(
            username=email,
            email=email,
            password=validated_data["password"],
        )
        Membership.objects.create(user=user, has_full_access=True)
        return user


class SavedDealSerializer(serializers.ModelSerializer):
    listing_detail = ListingSerializer(source="listing", read_only=True)

    class Meta:
        model = SavedDeal
        fields = ["id", "listing", "listing_detail", "saved_at"]
        read_only_fields = ["id", "saved_at"]

    def create(self, validated_data):
        saved_deal, _ = SavedDeal.objects.get_or_create(
            user=self.context["request"].user,
            listing=validated_data["listing"],
        )
        return saved_deal
        

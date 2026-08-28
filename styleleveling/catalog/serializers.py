from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Listing, ListingImage, ListingReview, Membership, SavedDeal, Store, StoreRequest


class ListingReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.SerializerMethodField()

    class Meta:
        model = ListingReview
        fields = ["id", "listing", "rating", "reason", "reviewer_name", "created_at"]
        read_only_fields = ["id", "listing", "reviewer_name", "created_at"]

    def get_reviewer_name(self, review):
        return (review.user.first_name or review.user.username.split("@")[0])[:40]

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def create(self, validated_data):
        review, _ = ListingReview.objects.update_or_create(
            user=self.context["request"].user,
            listing=validated_data["listing"],
            defaults={
                "rating": validated_data["rating"],
                "reason": validated_data["reason"],
                "is_approved": False,
            },
        )
        return review


class StoreRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreRequest
        fields = ["id", "store_name", "website_url", "reason", "created_at"]
        read_only_fields = ["id", "created_at"]


class StoreSerializer(serializers.ModelSerializer):
    listing_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Store
        fields = ["id", "store_name", "website_url", "listing_count"]


class ListingImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingImage
        fields = ["id", "image_url", "alt_text", "position"]


class ListingSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source="store.store_name", read_only=True)
    product_name = serializers.CharField(source="product.product_name", read_only=True)
    brand_name = serializers.CharField(source="product.brand_name", read_only=True)
    category = serializers.CharField(source="product.category", read_only=True)
    audience = serializers.CharField(source="product.audience", read_only=True)
    image_urls = serializers.SerializerMethodField()
    images = ListingImageSerializer(many=True, read_only=True)
    outbound_url = serializers.URLField(read_only=True)
    approved_reviews = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            "id", "store", "store_name", "product", "product_name",
            "brand_name", "category", "audience", "external_product_id",
            "product_page_url", "affiliate_url", "outbound_url",
            "current_price", "original_price", "quantity", "is_promo_active",
            "is_discounted", "discount_amount", "discount_percentage",
            "image_urls", "images", "approved_reviews", "average_rating",
            "last_checked_time", "last_seen",
        ]

    def get_image_urls(self, listing):
        urls = [image.image_url for image in listing.images.all()]
        if not urls and listing.product.image_url:
            urls.append(listing.product.image_url)
        return urls

    def get_approved_reviews(self, listing):
        reviews = listing.reviews.filter(is_approved=True).select_related("user")
        return ListingReviewSerializer(reviews, many=True).data

    def get_average_rating(self, listing):
        reviews = list(listing.reviews.filter(is_approved=True))
        if not reviews:
            return None
        return round(sum(review.rating for review in reviews) / len(reviews), 1)


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
        

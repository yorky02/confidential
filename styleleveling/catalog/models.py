from django.db import models
from django.conf import settings
from decimal import Decimal

# Create your models here.
# Use DecimalField for money instead of FloatField
# DecimalField requires max_digits and decimal_places
# for synchronizatrion use DateTimeField

class Store(models.Model):

    def __str__(self):
        return self.store_name
    
    store_name = models.CharField(max_length=255)
    website_url = models.URLField()
    is_active = models.BooleanField(default=True)
    is_guest_visible = models.BooleanField(
        default=False,
        help_text="Allow non-members to see deals from this store.",
    )
    last_sync_at = models.DateTimeField(
        null=True, 
        blank=True
    )


class Product(models.Model):

    def __str__(self):
        return self.product_name
    
    product_name = models.CharField(max_length=255)
    brand_name = models.CharField(
        max_length=255,
        blank=True
    )
    model_name = models.CharField(
        max_length=255,
        blank=True
    )
    category = models.CharField(max_length=255)
    image_url = models.URLField(
        blank=True
    )

class Listing(models.Model):

    def __str__(self):
        return f"{self.product} at {self.store}"

    store = models.ForeignKey(Store, on_delete= models.CASCADE)
    product = models.ForeignKey(Product, on_delete= models.CASCADE)
    external_product_id = models.CharField(max_length=50)
    product_page_url = models.URLField()
    affiliate_url = models.URLField(
        blank=True,
        help_text="Optional affiliate link. Falls back to the retailer product URL.",
    )
    current_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    original_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True, blank=True
    )
    quantity = models.PositiveIntegerField(
        null=True,
        blank=True
    )
    is_promo_active = models.BooleanField(default=False)
    last_checked_time = models.DateTimeField(
        null=True,
        blank=True
    )
    last_seen = models.DateTimeField(
        null=True,
        blank=True
    )
    missing_count = models.PositiveIntegerField(default=0)

    @property
    def outbound_url(self):
        return self.affiliate_url or self.product_page_url

    @property
    def is_discounted(self):
        if self.original_price is None:
            return False
        return self.current_price < self.original_price

    @property
    def discount_amount(self):
        if not self.is_discounted:
            return Decimal("0.00")
        
        return self.original_price - self.current_price


    @property
    def discount_percentage(self):
        if not self.is_discounted or not self.original_price:
           return Decimal("0.00")

        return round((self.discount_amount / self.original_price) * Decimal("100"), 2)

class PriceHistory(models.Model):

    def __str__ (self):
        return f"{self.listing} - ${self.price}"

    listing = models.ForeignKey(Listing, on_delete= models.CASCADE)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    original_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True, blank=True
    )
    date_recorded = models.DateTimeField(auto_now_add=True)


class ListingImage(models.Model):
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image_url = models.URLField()
    alt_text = models.CharField(max_length=255, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"Image {self.position + 1} for {self.listing}"


class Membership(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="styleleveling_membership",
    )
    has_full_access = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email or self.user.username} membership"


class SavedDeal(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_deals",
    )
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name="saved_by",
    )
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "listing"],
                name="unique_saved_deal_per_user",
            )
        ]
        ordering = ["-saved_at"]

    def __str__(self):
        return f"{self.user} saved {self.listing}"
    

class SyncRun(models.Model):

    def __str__(self):
        return f"{self.store} sync - {self.started_at}"
    store = models.ForeignKey(Store, on_delete= models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    successful = models.BooleanField(default=False)
    listings_found = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)



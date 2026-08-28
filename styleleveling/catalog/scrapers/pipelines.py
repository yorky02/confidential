from django.db import transaction
from django.utils import timezone
from scrapy import signals

from catalog.models import Listing, ListingImage, PriceHistory, Product, Store, SyncRun
from catalog.classification import classify_category
from catalog.scrapers.fashion_filter import fashion_product_decision


class DjangoCatalogPipeline:
    """Upsert spider items into the existing StyleLeveling catalog."""

    @classmethod
    def from_crawler(cls, crawler):
        pipeline = cls()
        pipeline.crawler = crawler
        crawler.signals.connect(pipeline.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(pipeline.spider_closed, signal=signals.spider_closed)
        return pipeline

    def spider_opened(self, spider):
        self.store, _ = Store.objects.update_or_create(
            store_name=spider.store_name,
            defaults={
                "website_url": spider.store_url,
                "is_active": True,
                "is_guest_visible": True,
            },
        )
        self.sync_run = SyncRun.objects.create(store=self.store)
        self.listings_found = 0

        if spider.name == "asos":
            # Remove mixed-catalog products imported by older ASOS spider
            # versions before the new filtered results become visible.
            for listing in Listing.objects.filter(
                store=self.store,
                is_promo_active=True,
            ).select_related("product"):
                accepted, _ = fashion_product_decision(
                    listing.product.product_name,
                    listing.product.source_category,
                )
                if not accepted:
                    listing.is_promo_active = False
                    listing.save(update_fields=["is_promo_active"])

    @transaction.atomic
    def process_item(self, item):
        now = timezone.now()
        listing = Listing.objects.filter(
            store=self.store,
            external_product_id=item["external_product_id"],
        ).select_related("product").first()

        if listing:
            product = listing.product
            previous_price = listing.current_price
        else:
            product = Product()
            previous_price = None

        product.product_name = item["product_name"]
        product.brand_name = item["brand_name"]
        product.audience = item["audience"]
        product.source_category = item["category"]
        if not product.category_locked:
            category, confidence, needs_review = classify_category(
                item["product_name"], item["category"], item["audience"]
            )
            product.category = category
            product.category_confidence = confidence
            product.needs_category_review = needs_review
        product.image_url = item["image_urls"][0] if item["image_urls"] else ""
        product.save()

        if listing is None:
            listing = Listing(store=self.store, product=product)
        listing.external_product_id = item["external_product_id"]
        listing.product_page_url = item["product_page_url"]
        listing.current_price = item["current_price"]
        listing.original_price = item["original_price"]
        listing.is_promo_active = item["current_price"] < item["original_price"]
        listing.last_checked_time = now
        listing.last_seen = now
        listing.missing_count = 0
        listing.save()

        ListingImage.objects.filter(listing=listing).delete()
        ListingImage.objects.bulk_create(
            [
                ListingImage(
                    listing=listing,
                    image_url=image_url,
                    alt_text=item["product_name"],
                    position=position,
                )
                for position, image_url in enumerate(item["image_urls"])
            ]
        )

        if previous_price != item["current_price"]:
            PriceHistory.objects.create(
                listing=listing,
                price=item["current_price"],
                original_price=item["original_price"],
            )

        self.listings_found += 1
        return item

    def spider_closed(self, spider, reason):
        error_count = self.crawler.stats.get_value("log_count/ERROR", 0)
        successful = self.listings_found > 0
        self.store.last_sync_at = timezone.now()
        self.store.save(update_fields=["last_sync_at"])
        self.sync_run.finished_at = timezone.now()
        self.sync_run.successful = successful
        self.sync_run.listings_found = self.listings_found
        if not successful:
            self.sync_run.error_message = (
                f"Spider closed: {reason}; logged errors: {error_count}"
            )
        elif error_count:
            self.sync_run.error_message = f"Imported with {error_count} logged error(s)."
        self.sync_run.save()

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Listing, Product, Store


class ListingDiscountTests(TestCase):

    def setUp(self):
        self.store = Store.objects.create(
            store_name="Test Store",
            website_url="https://example.com",
        )

        self.product = Product.objects.create(
            product_name="Test Product",
            brand_name="Test Brand",
            category="Clothing",
        )

        self.discounted_listing = Listing.objects.create(
            store=self.store,
            product=self.product,
            external_product_id="TEST-1",
            product_page_url="https://example.com/product-1",
            current_price=Decimal("75.00"),
            original_price=Decimal("100.00"),
            is_promo_active=True,
        )

        self.regular_listing = Listing.objects.create(
            store=self.store,
            product=self.product,
            external_product_id="TEST-2",
            product_page_url="https://example.com/product-2",
            current_price=Decimal("100.00"),
            original_price=Decimal("100.00"),
            is_promo_active=False,
        )

        self.no_original_price_listing = Listing.objects.create(
            store=self.store,
            product=self.product,
            external_product_id="TEST-3",
            product_page_url="https://example.com/product-3",
            current_price=Decimal("50.00"),
            original_price=None,
            is_promo_active=False,
        )

    def test_discounted_listing_is_detected(self):
        self.assertTrue(self.discounted_listing.is_discounted)

    def test_discount_amount_is_calculated(self):
        self.assertEqual(
            self.discounted_listing.discount_amount,
            Decimal("25.00"),
        )

    def test_discount_percentage_is_calculated(self):
        self.assertEqual(
            self.discounted_listing.discount_percentage,
            Decimal("25.00"),
        )

    def test_regular_price_is_not_discounted(self):
        self.assertFalse(self.regular_listing.is_discounted)
        self.assertEqual(
            self.regular_listing.discount_amount,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.regular_listing.discount_percentage,
            Decimal("0.00"),
        )

    def test_missing_original_price_is_handled(self):
        self.assertFalse(self.no_original_price_listing.is_discounted)
        self.assertEqual(
            self.no_original_price_listing.discount_amount,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.no_original_price_listing.discount_percentage,
            Decimal("0.00"),
        )


class ListingAPITests(APITestCase):

    def setUp(self):
        self.store_one = Store.objects.create(
            store_name="Cotton On",
            website_url="https://cottonon.com",
        )

        self.store_two = Store.objects.create(
            store_name="Example Electronics",
            website_url="https://electronics.example.com",
        )

        self.shirt = Product.objects.create(
            product_name="Morgan Wallen Shirt",
            brand_name="Cotton On",
            category="Clothing",
        )

        self.headphones = Product.objects.create(
            product_name="Wireless Headphones",
            brand_name="Sound Test",
            category="Electronics",
        )

        self.shirt_listing = Listing.objects.create(
            store=self.store_one,
            product=self.shirt,
            external_product_id="SHIRT-100",
            product_page_url="https://cottonon.com/shirt",
            current_price=Decimal("24.98"),
            original_price=Decimal("49.99"),
            is_promo_active=True,
        )

        self.headphones_listing = Listing.objects.create(
            store=self.store_two,
            product=self.headphones,
            external_product_id="HEADPHONES-200",
            product_page_url="https://electronics.example.com/headphones",
            current_price=Decimal("89.99"),
            original_price=Decimal("89.99"),
            is_promo_active=False,
        )

    def get_results(self, response):
        """
        Supports APIs with or without pagination.
        """
        if isinstance(response.data, dict) and "results" in response.data:
            return response.data["results"]

        return response.data

    def test_listing_list_returns_success(self):
        url = reverse("listing-list")
        response = self.client.get(url)
        results = self.get_results(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(results), 2)

    def test_listing_detail_returns_correct_listing(self):
        url = reverse(
            "listing-detail",
            args=[self.shirt_listing.pk],
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["id"],
            self.shirt_listing.id,
        )

    def test_missing_listing_returns_404(self):
        url = reverse(
            "listing-detail",
            args=[999999],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_filter_by_active_promotion(self):
        url = reverse("listing-list")
        response = self.client.get(
            url,
            {"is_promo_active": "true"},
        )
        results = self.get_results(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["id"],
            self.shirt_listing.id,
        )

    def test_filter_by_store(self):
        url = reverse("listing-list")
        response = self.client.get(
            url,
            {"store": self.store_two.id},
        )
        results = self.get_results(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["id"],
            self.headphones_listing.id,
        )

    def test_filter_by_category(self):
        url = reverse("listing-list")
        response = self.client.get(
            url,
            {"product__category": "Electronics"},
        )
        results = self.get_results(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["id"],
            self.headphones_listing.id,
        )

    def test_search_by_product_name(self):
        url = reverse("listing-list")
        response = self.client.get(
            url,
            {"search": "Morgan"},
        )
        results = self.get_results(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["id"],
            self.shirt_listing.id,
        )

    def test_search_by_brand_name(self):
        url = reverse("listing-list")
        response = self.client.get(
            url,
            {"search": "Sound Test"},
        )
        results = self.get_results(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["id"],
            self.headphones_listing.id,
        )

    def test_search_by_store_name(self):
        url = reverse("listing-list")
        response = self.client.get(
            url,
            {"search": "Cotton On"},
        )
        results = self.get_results(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["id"],
            self.shirt_listing.id,
        )

    def test_search_by_external_product_id(self):
        url = reverse("listing-list")
        response = self.client.get(
            url,
            {"search": "HEADPHONES-200"},
        )
        results = self.get_results(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["id"],
            self.headphones_listing.id,
        )

    def test_order_by_lowest_price_first(self):
        url = reverse("listing-list")
        response = self.client.get(
            url,
            {"ordering": "current_price"},
        )
        results = self.get_results(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            results[0]["id"],
            self.shirt_listing.id,
        )
        self.assertEqual(
            results[1]["id"],
            self.headphones_listing.id,
        )

    def test_order_by_highest_price_first(self):
        url = reverse("listing-list")
        response = self.client.get(
            url,
            {"ordering": "-current_price"},
        )
        results = self.get_results(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            results[0]["id"],
            self.headphones_listing.id,
        )
        self.assertEqual(
            results[1]["id"],
            self.shirt_listing.id,
        )

    def test_combined_filter_search_and_ordering(self):
        url = reverse("listing-list")
        response = self.client.get(
            url,
            {
                "is_promo_active": "true",
                "search": "shirt",
                "ordering": "current_price",
            },
        )
        results = self.get_results(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["id"],
            self.shirt_listing.id,
        )

    def test_api_contains_calculated_discount_fields(self):
        url = reverse(
            "listing-detail",
            args=[self.shirt_listing.pk],
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("is_discounted", response.data)
        self.assertIn("discount_amount", response.data)
        self.assertIn("discount_percentage", response.data)
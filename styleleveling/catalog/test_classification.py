from django.test import SimpleTestCase

from .classification import classify_category

class CategoryClassificationTests(SimpleTestCase):
    def test_specific_name_wins_over_broad_retailer_category(self):
        self.assertEqual(classify_category("Ultra High Rise Denim Shorts", "Clothing", "women"), ("Denim Shorts", 90, False))

    def test_gender_specific_shirt_label(self):
        self.assertEqual(classify_category("Relaxed Oxford Shirt", "Clothing", "men"), ("Shirts & Polos", 90, False))

    def test_ambiguous_item_goes_to_review_queue(self):
        category, confidence, needs_review = classify_category("Everyday Essential", "Clothing", "women")
        self.assertEqual(category, "Uncategorized")
        self.assertLess(confidence, 50)
        self.assertTrue(needs_review)

from django.test import SimpleTestCase

from .classification import classify_category

class CategoryClassificationTests(SimpleTestCase):
    def test_specific_name_wins_over_broad_retailer_category(self):
        self.assertEqual(classify_category("Ultra High Rise Denim Shorts", "Clothing", "women"), ("Denim Shorts", 92, False))

    def test_gender_specific_shirt_label(self):
        self.assertEqual(classify_category("Relaxed Oxford Shirt", "Clothing", "men"), ("Shirts & Polos", 92, False))

    def test_ambiguous_item_goes_to_review_queue(self):
        category, confidence, needs_review = classify_category("Everyday Essential", "Clothing", "women")
        self.assertEqual(category, "Other Clothing")
        self.assertLess(confidence, 50)
        self.assertTrue(needs_review)

    def test_jort_and_bikini_names_are_classified(self):
        self.assertEqual(classify_category("91 Baggy Denim Jort", "Clothing", "women")[0], "Denim Shorts")
        self.assertEqual(classify_category("Micro Knit Bikini Bottom", "Clothing", "women")[0], "Swimwear")

    def test_broad_accessory_still_has_a_filter_while_queued(self):
        self.assertEqual(classify_category("Core Gym Towel", "Accessories", "women"), ("Other Accessories", 55, True))

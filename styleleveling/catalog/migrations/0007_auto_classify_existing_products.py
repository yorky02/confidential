from django.db import migrations, models

CATEGORIES = [(name, name) for name in [
    "Tees & Tanks", "Graphic T-Shirts", "Blouses & Shirts", "Shirts & Polos",
    "Sweats & Hoodies", "Sweaters", "Jackets & Coats", "Suits & Blazers",
    "Jeans", "Denim Shorts", "Shorts", "Pants", "Pants & Chinos", "Joggers",
    "Skirts", "Dresses & Jumpsuits", "Activewear", "Sleepwear", "Swimwear",
    "Lingerie & Underwear", "Socks & Underwear", "Shoes", "Bags & Belts",
    "Jewelry", "Hats & Sunglasses", "Other Clothing", "Other Accessories",
    "Uncategorized",
]]

def classify_existing_products(apps, schema_editor):
    from catalog.classification import classify_category
    Product = apps.get_model("catalog", "Product")
    for product in Product.objects.filter(category_locked=False).iterator(chunk_size=500):
        category, confidence, needs_review = classify_category(
            product.product_name, product.source_category, product.audience
        )
        product.category = category
        product.category_confidence = confidence
        product.needs_category_review = needs_review
        product.save(update_fields=["category", "category_confidence", "needs_category_review"])

class Migration(migrations.Migration):
    dependencies = [("catalog", "0006_merge_duplicate_stores")]
    operations = [
        migrations.AlterField(model_name="product", name="category", field=models.CharField(choices=CATEGORIES, default="Uncategorized", max_length=50)),
        migrations.RunPython(classify_existing_products, migrations.RunPython.noop),
    ]

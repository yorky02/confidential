from django.db import migrations, models

CATEGORIES = [(x, x) for x in [
    "Tees & Tanks", "Graphic T-Shirts", "Blouses & Shirts", "Shirts & Polos",
    "Sweats & Hoodies", "Sweaters", "Jackets & Coats", "Suits & Blazers",
    "Jeans", "Denim Shorts", "Shorts", "Pants", "Pants & Chinos", "Joggers",
    "Skirts", "Dresses & Jumpsuits", "Activewear", "Sleepwear", "Swimwear",
    "Lingerie & Underwear", "Socks & Underwear", "Shoes", "Bags & Belts",
    "Jewelry", "Hats & Sunglasses", "Uncategorized",
]]

def queue_existing_products(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    Product.objects.update(source_category=models.F("category"), category="Uncategorized", category_confidence=0, needs_category_review=True)

class Migration(migrations.Migration):
    dependencies = [("catalog", "0004_product_audience_listingreview_storerequest")]
    operations = [
        migrations.AddField(model_name="product", name="source_category", field=models.CharField(blank=True, help_text="Original category supplied by the retailer.", max_length=255)),
        migrations.AddField(model_name="product", name="category_confidence", field=models.PositiveSmallIntegerField(default=0)),
        migrations.AddField(model_name="product", name="needs_category_review", field=models.BooleanField(db_index=True, default=True)),
        migrations.AddField(model_name="product", name="category_locked", field=models.BooleanField(default=False, help_text="Keep the administrator's category during future imports.")),
        migrations.RunPython(queue_existing_products, migrations.RunPython.noop),
        migrations.AlterField(model_name="product", name="category", field=models.CharField(choices=CATEGORIES, default="Uncategorized", max_length=50)),
    ]

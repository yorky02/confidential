from django.db import migrations, models


def hide_adidas(apps, schema_editor):
    """Retire Adidas after repeated 403 responses without deleting history."""

    Store = apps.get_model("catalog", "Store")
    Listing = apps.get_model("catalog", "Listing")
    stores = Store.objects.filter(store_name__iexact="Adidas")
    Listing.objects.filter(store__in=stores).update(is_promo_active=False)
    stores.update(is_active=False, is_guest_visible=False)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0008_hide_unsupported_stores")]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="image_url",
            field=models.URLField(blank=True, max_length=1000),
        ),
        migrations.AlterField(
            model_name="listing",
            name="product_page_url",
            field=models.URLField(max_length=1000),
        ),
        migrations.AlterField(
            model_name="listing",
            name="affiliate_url",
            field=models.URLField(
                blank=True,
                help_text="Optional affiliate link. Falls back to the retailer product URL.",
                max_length=1000,
            ),
        ),
        migrations.AlterField(
            model_name="listingimage",
            name="image_url",
            field=models.URLField(max_length=1000),
        ),
        migrations.RunPython(hide_adidas, migrations.RunPython.noop),
    ]

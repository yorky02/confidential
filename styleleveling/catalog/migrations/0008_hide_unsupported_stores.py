from django.db import migrations


UNSUPPORTED_STORES = (
    "Pacsun",
    "PacSun",
    "Gap",
    "H&M",
    "Uniqlo",
    "Hollister",
    "HOLLISTER",
    "Urban Outfitters",
    "Brandy Melville",
)


def hide_unsupported_stores(apps, schema_editor):
    Store = apps.get_model("catalog", "Store")
    Listing = apps.get_model("catalog", "Listing")
    stores = Store.objects.filter(store_name__in=UNSUPPORTED_STORES)
    Listing.objects.filter(store__in=stores).update(is_promo_active=False)
    stores.update(is_active=False, is_guest_visible=False)


def restore_stores(apps, schema_editor):
    Store = apps.get_model("catalog", "Store")
    Store.objects.filter(store_name__in=UNSUPPORTED_STORES).update(is_active=True)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0007_auto_classify_existing_products")]
    operations = [migrations.RunPython(hide_unsupported_stores, restore_stores)]

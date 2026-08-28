from django.db import migrations

CANONICAL = {
    "pacsun": "PacSun",
    "pac sun": "PacSun",
    "hollister": "Hollister",
    "hollister co": "Hollister",
}

def merge_duplicate_stores(apps, schema_editor):
    Store = apps.get_model("catalog", "Store")
    Listing = apps.get_model("catalog", "Listing")
    SyncRun = apps.get_model("catalog", "SyncRun")
    for key, proper_name in CANONICAL.items():
        matches = list(Store.objects.filter(store_name__iexact=key))
        if not matches:
            continue
        primary = max(matches, key=lambda store: Listing.objects.filter(store=store).count())
        primary.store_name = proper_name
        primary.is_active = True
        primary.is_guest_visible = True
        primary.save(update_fields=["store_name", "is_active", "is_guest_visible"])
        for duplicate in matches:
            if duplicate.pk == primary.pk:
                continue
            Listing.objects.filter(store=duplicate).update(store=primary)
            SyncRun.objects.filter(store=duplicate).update(store=primary)
            duplicate.delete()

class Migration(migrations.Migration):
    dependencies = [("catalog", "0005_product_category_review")]
    operations = [migrations.RunPython(merge_duplicate_stores, migrations.RunPython.noop)]

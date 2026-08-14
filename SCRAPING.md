# Automated retailer sale imports

The Django project includes polite Scrapy importers for the public men's and
women's sale pages at Cotton On, PacSun, Hollister, Urban Outfitters, H&M, Gap,
and Uniqlo. They follow available pagination and import each item's
name, retailer ID, retailer URL, sale and original prices, audience, category,
and ordered image gallery.

## Run it manually

From the repository root:

```powershell
python styleleveling/manage.py scrape_sales
```

Useful test options:

```powershell
python styleleveling/manage.py scrape_sales --stores pacsun,hm --audience men --max-pages 1
python styleleveling/manage.py scrape_sales --stores uniqlo --audience women --max-pages 1
python styleleveling/manage.py scrape_sales --stores gap --audience men --max-pages 1 --max-items 5
```

Omit `--max-pages` for the complete import.

## Enable the daily GitHub Action

The workflow `.github/workflows/scrape-cotton-on.yml` runs every day at
08:17 UTC and can also be started manually from **GitHub → Actions → Import
retailer sale deals → Run workflow**.

Create one repository secret before running it:

1. Open **GitHub → repository Settings → Secrets and variables → Actions**.
2. Select **New repository secret**.
3. Name it `DATABASE_URL`.
4. Use the Render PostgreSQL **External Database URL** as its value.

Never paste the database URL into source code or a commit. The workflow stops
with a clear error when the secret is missing, rather than writing to a local
temporary database.

## Import behavior

- Existing items are updated by store and retailer product ID.
- A price-history record is added only when the price changes.
- Gallery images are replaced in the current retailer order.
- Imported stores are marked as guest-visible.
- Each run is recorded in Django Admin under `Sync runs`.
- The spider obeys `robots.txt`, identifies StyleLeveling in its user agent,
  limits requests per domain, and uses automatic throttling.
- If a retailer returns an access block or changes its HTML, that store's run
  records the problem instead of attempting to bypass the restriction.

# Automated Cotton On imports

The Django project includes a polite Scrapy importer for the public Cotton On
US men's and women's sale pages. It follows pagination and imports each item's
name, retailer ID, retailer URL, sale and original prices, audience, category,
and ordered image gallery.

## Run it manually

From the repository root:

```powershell
python styleleveling/manage.py scrape_cotton_on
```

Useful test options:

```powershell
python styleleveling/manage.py scrape_cotton_on --audience men --max-pages 1
python styleleveling/manage.py scrape_cotton_on --audience women --max-pages 1
```

Omit `--max-pages` for the complete import.

## Enable the daily GitHub Action

The workflow `.github/workflows/scrape-cotton-on.yml` runs every day at
08:17 UTC and can also be started manually from **GitHub → Actions → Import
Cotton On sale deals → Run workflow**.

Create one repository secret before running it:

1. Open **GitHub → repository Settings → Secrets and variables → Actions**.
2. Select **New repository secret**.
3. Name it `DATABASE_URL`.
4. Use the Render PostgreSQL **External Database URL** as its value.

Never paste the database URL into source code or a commit. The workflow stops
with a clear error when the secret is missing, rather than writing to a local
temporary database.

## Import behavior

- Existing Cotton On items are updated by retailer product ID.
- A price-history record is added only when the price changes.
- Gallery images are replaced in the current retailer order.
- Cotton On is marked as guest-visible.
- Each run is recorded in Django Admin under `Sync runs`.
- The spider obeys `robots.txt`, identifies StyleLeveling in its user agent,
  limits requests per domain, and uses automatic throttling.

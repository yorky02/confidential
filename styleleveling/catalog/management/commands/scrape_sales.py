from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from catalog.scrapers.cotton_on import CottonOnSpider
from catalog.scrapers.retailers import (
    AsosSpider,
    Forever21Spider,
    GapSpider,
    HMSpider,
    HollisterSpider,
    PacSunSpider,
    UniqloSpider,
    UrbanOutfittersSpider,
)
from catalog.models import SyncRun


SPIDERS = {
    "cotton_on": CottonOnSpider,
    "pacsun": PacSunSpider,
    "hollister": HollisterSpider,
    "urban_outfitters": UrbanOutfittersSpider,
    "hm": HMSpider,
    "gap": GapSpider,
    "uniqlo": UniqloSpider,
    "forever21": Forever21Spider,
    "asos": AsosSpider,
}


class Command(BaseCommand):
    help = "Import public men's and women's sale listings from supported retailers."

    def add_arguments(self, parser):
        parser.add_argument(
            "--stores",
            default="all",
            help="Comma-separated store keys or 'all' (default).",
        )
        parser.add_argument("--minimum-successful-stores", type=int, default=2)
        parser.add_argument(
            "--audience",
            choices=["men", "women", "both"],
            default="both",
        )
        parser.add_argument("--max-pages", type=int)
        parser.add_argument(
            "--max-items",
            type=int,
            help="Optional per-store item limit for a small verification run.",
        )

    def handle(self, *args, **options):
        requested = list(SPIDERS) if options["stores"] == "all" else [
            name.strip() for name in options["stores"].split(",") if name.strip()
        ]
        unknown = sorted(set(requested) - set(SPIDERS))
        if unknown:
            raise CommandError(
                f"Unknown stores: {', '.join(unknown)}. Choose from: {', '.join(SPIDERS)}"
            )

        settings = get_project_settings()
        settings.set(
            "TWISTED_REACTOR",
            "twisted.internet.selectreactor.SelectReactor",
            priority="cmdline",
        )
        settings.set(
            "ITEM_PIPELINES",
            {"catalog.scrapers.pipelines.DjangoCatalogPipeline": 300},
            priority="cmdline",
        )
        if options["max_items"]:
            settings.set("CLOSESPIDER_ITEMCOUNT", options["max_items"], priority="cmdline")
        run_started_at = timezone.now()
        requested_store_names = [SPIDERS[name].store_name for name in requested]
        process = CrawlerProcess(settings)
        for name in requested:
            process.crawl(
                SPIDERS[name],
                audience=options["audience"],
                max_pages=options["max_pages"],
            )
        process.start()
        # Matrix jobs share one database and may run concurrently. Restrict the
        # summary to this command's retailers so one job cannot report another
        # job's SyncRun records.
        runs = list(
            SyncRun.objects.filter(
                started_at__gte=run_started_at,
                store__store_name__in=requested_store_names,
            )
            .select_related("store")
            .order_by("store__store_name")
        )
        successful_stores = 0
        self.stdout.write("\nRetailer import summary")
        for run in runs:
            imported = run.successful and run.listings_found > 0
            successful_stores += int(imported)
            status = "IMPORTED" if imported else "FAILED/EMPTY"
            detail = f" ({run.error_message})" if run.error_message else ""
            self.stdout.write(f"- {run.store.store_name}: {status}, {run.listings_found} listings{detail}")
        minimum = min(options["minimum_successful_stores"], len(requested))
        if successful_stores < minimum:
            raise CommandError(
                f"Only {successful_stores} retailer(s) imported products; expected at least {minimum}. "
                "Open this workflow log and review the retailer summary above."
            )
        self.stdout.write(self.style.SUCCESS(f"Sale imports finished across {successful_stores} retailers."))

from django.core.management.base import BaseCommand, CommandError
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from catalog.scrapers.cotton_on import CottonOnSpider
from catalog.scrapers.retailers import (
    GapSpider,
    HMSpider,
    HollisterSpider,
    PacSunSpider,
    UniqloSpider,
    UrbanOutfittersSpider,
)


SPIDERS = {
    "cotton_on": CottonOnSpider,
    "pacsun": PacSunSpider,
    "hollister": HollisterSpider,
    "urban_outfitters": UrbanOutfittersSpider,
    "hm": HMSpider,
    "gap": GapSpider,
    "uniqlo": UniqloSpider,
}


class Command(BaseCommand):
    help = "Import public men's and women's sale listings from supported retailers."

    def add_arguments(self, parser):
        parser.add_argument(
            "--stores",
            default="all",
            help="Comma-separated store keys or 'all' (default).",
        )
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
        process = CrawlerProcess(settings)
        for name in requested:
            process.crawl(
                SPIDERS[name],
                audience=options["audience"],
                max_pages=options["max_pages"],
            )
        process.start()
        self.stdout.write(self.style.SUCCESS("Sale imports finished."))

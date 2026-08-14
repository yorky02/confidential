from django.core.management.base import BaseCommand
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from catalog.scrapers.cotton_on import CottonOnSpider


class Command(BaseCommand):
    help = "Import Cotton On US men's and women's sale listings."

    def add_arguments(self, parser):
        parser.add_argument(
            "--audience",
            choices=["men", "women", "both"],
            default="both",
            help="Sale section to import (default: both).",
        )
        parser.add_argument(
            "--max-pages",
            type=int,
            help="Optional page limit for testing. Omit for a complete import.",
        )

    def handle(self, *args, **options):
        settings = get_project_settings()
        # Django's ORM is synchronous. Keep Scrapy on Twisted's synchronous
        # reactor so database writes never run inside an asyncio context.
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
        process = CrawlerProcess(settings)
        process.crawl(
            CottonOnSpider,
            audience=options["audience"],
            max_pages=options["max_pages"],
        )
        process.start()
        self.stdout.write(self.style.SUCCESS("Cotton On import finished."))

import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from rentals.constants import CURRENCY_CHOICES
from rentals.services.fx_refresh import CurrencyPair, YahooRateProvider, refresh_rates


class Command(BaseCommand):
    help = "Refresh required FX rates through the bounded scheduled provider."

    def add_arguments(self, parser):
        parser.add_argument("--date", dest="as_of")
        parser.add_argument("--pair", action="append", dest="pair")

    def handle(self, *args, **options):
        as_of = date.fromisoformat(options["as_of"]) if options.get("as_of") else timezone.localdate(timezone.now())
        raw_pairs = options.get("pair") or [f"USD/{code}" for code, _ in CURRENCY_CHOICES if code != "USD"]
        try:
            pairs = [CurrencyPair(*value.split("/", 1)) for value in raw_pairs]
        except (TypeError, ValueError) as exc:
            raise CommandError(f"Invalid currency pair: {exc}") from exc
        report = refresh_rates(as_of=as_of, pairs=pairs, provider=YahooRateProvider())
        payload = {
            bucket: [f"{p.from_currency}/{p.to_currency}" for p in getattr(report, bucket)]
            for bucket in ("cached", "fetched", "unavailable", "invalid")
        }
        self.stdout.write(json.dumps({"as_of": as_of.isoformat(), **payload}, sort_keys=True))
        if report.unavailable or report.invalid:
            raise CommandError("Required FX rates are unavailable or invalid")

import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from rentals.constants import CURRENCY_CHOICES
from rentals.services.fx_refresh import (
    CurrencyPair,
    RoutingRateProvider,
    refresh_missing_rates,
    refresh_rates,
)


class Command(BaseCommand):
    help = "Refresh required FX rates through the bounded scheduled provider."

    def add_arguments(self, parser):
        parser.add_argument("--date", dest="as_of")
        parser.add_argument("--through", dest="through")
        parser.add_argument("--pair", action="append", dest="pair")
        parser.add_argument(
            "--scan-gaps",
            action="store_true",
            help="Explicitly run the full business-record FX gap scan.",
        )

    def handle(self, *args, **options):
        if options.get("scan_gaps") and (options.get("as_of") or options.get("pair")):
            raise CommandError("--scan-gaps cannot be combined with --date or --pair")
        if options.get("through") and (options.get("as_of") or options.get("pair")):
            raise CommandError("--through is only valid for the gap scan")

        if options.get("scan_gaps") or (
            not options.get("as_of") and not options.get("pair")
        ):
            through = self._parse_date_option(
                options.get("through"),
                default=timezone.localdate(timezone.now()),
            )
            report = refresh_missing_rates(
                target_currencies=None,
                through=through,
                provider=RoutingRateProvider(),
            )
            payload = {
                bucket: [_format_requirement(item) for item in getattr(report, bucket)]
                for bucket in ("cached", "fetched", "unavailable", "invalid")
            }
            self.stdout.write(
                json.dumps(
                    {"mode": "gap_scan", "through": through.isoformat(), **payload},
                    sort_keys=True,
                )
            )
            if report.unavailable or report.invalid:
                raise CommandError("Required FX gaps are unavailable or invalid")
            return

        try:
            as_of = (
                date.fromisoformat(options["as_of"])
                if options.get("as_of")
                else timezone.localdate(timezone.now())
            )
        except ValueError as exc:
            raise CommandError(f"Invalid date: {options['as_of']}") from exc
        raw_pairs = options.get("pair") or [f"USD/{code}" for code, _ in CURRENCY_CHOICES if code != "USD"]
        try:
            pairs = [CurrencyPair(*value.split("/", 1)) for value in raw_pairs]
        except (TypeError, ValueError) as exc:
            raise CommandError(f"Invalid currency pair: {exc}") from exc
        report = refresh_rates(as_of=as_of, pairs=pairs, provider=RoutingRateProvider())
        payload = {
            bucket: [f"{p.from_currency}/{p.to_currency}" for p in getattr(report, bucket)]
            for bucket in ("cached", "fetched", "unavailable", "invalid")
        }
        self.stdout.write(
            json.dumps(
                {"mode": "date_pair", "as_of": as_of.isoformat(), **payload},
                sort_keys=True,
            )
        )
        if report.unavailable or report.invalid:
            raise CommandError("Required FX rates are unavailable or invalid")

    def _parse_date_option(self, raw_value, *, default):
        if not raw_value:
            return default
        try:
            return date.fromisoformat(raw_value)
        except ValueError as exc:
            raise CommandError(f"Invalid date: {raw_value}") from exc


def _format_requirement(requirement):
    pair = requirement.pair
    return {
        "date": requirement.effective_date.isoformat(),
        "pair": f"{pair.from_currency}/{pair.to_currency}",
    }

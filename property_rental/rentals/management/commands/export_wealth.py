"""Write an owned Rent ledger in Wealth's v1.1 interchange format."""
import json
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from rentals.services.wealth_export import WealthExportError, build_wealth_export


class Command(BaseCommand):
    help = "Export one OIDC subject's owned history to Wealth v1.1 (database reads only)."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--out", required=True)
        parser.add_argument("--subject", required=True)
        parser.add_argument("--issuer", help="Disambiguate the OIDC issuer when a subject is reused.")
        parser.add_argument("--as-of", help="YYYY-MM-DD for arrears/deposit snapshots; history remains complete.")

    def handle(self, *args, **options):
        try:
            as_of = date.fromisoformat(options["as_of"]) if options["as_of"] else None
            payload = build_wealth_export(subject=options["subject"], issuer=options["issuer"], as_of=as_of)
            Path(options["out"]).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        except (WealthExportError, ValueError, OSError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(f"Exported {len(payload['properties'])} properties, {len(payload['loans'])} loans and {len(payload['transactions'])} transactions.")
        for loan in payload["loans"]:
            if loan["lender"].startswith("UNKNOWN"):
                self.stdout.write(f"Loan {loan['id']} (property {loan['property_id']}): lender needs filling in.")

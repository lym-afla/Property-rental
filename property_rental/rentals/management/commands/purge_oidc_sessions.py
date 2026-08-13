from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.db import transaction

from rentals.models import OIDCSession


class Command(BaseCommand):
    help = "Count or purge all OIDC session associations at a controlled maintenance boundary."

    def add_arguments(self, parser):
        parser.add_argument("--confirm-all-current", action="store_true")

    def handle(self, *args, **options):
        with transaction.atomic():
            rows = list(
                OIDCSession.objects.select_for_update()
                .order_by("pk")
                .values_list("pk", "session_key")
            )
            association_ids = [pk for pk, _ in rows]
            session_keys = [session_key for _, session_key in rows]
            referenced_count = Session.objects.filter(
                session_key__in=session_keys
            ).count()

            if not options["confirm_all_current"]:
                action = "dry-run"
            else:
                Session.objects.filter(session_key__in=session_keys).delete()
                OIDCSession.objects.filter(pk__in=association_ids).delete()
                action = "purged"

        self.stdout.write(
            f"action={action} oidc_associations={len(rows)} "
            f"referenced_django_sessions={referenced_count}"
        )

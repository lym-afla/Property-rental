from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from rentals.models import OIDCIdentity, User


class Command(BaseCommand):
    help = "Deliberately bind one local user to one verified OIDC identity."

    def add_arguments(self, parser):
        parser.add_argument("--user-id", required=True, type=int)
        parser.add_argument("--issuer", required=True)
        parser.add_argument("--subject", required=True)

    def handle(self, *args, **options):
        with transaction.atomic():
            try:
                user = User.objects.select_for_update().get(pk=options["user_id"])
            except User.DoesNotExist as exc:
                raise CommandError(f"Unknown user ID: {options['user_id']}") from exc
            if OIDCIdentity.objects.filter(user=user).exists():
                raise CommandError(f"User ID {user.pk} is already linked")
            if OIDCIdentity.objects.filter(
                issuer=options["issuer"], subject=options["subject"]
            ).exists():
                raise CommandError("OIDC issuer/subject is already linked")
            OIDCIdentity.objects.create(
                user=user, issuer=options["issuer"], subject=options["subject"]
            )
        self.stdout.write(
            f"Linked user_id={user.pk} issuer={options['issuer']} subject={options['subject']}"
        )


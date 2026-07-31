import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from rentals.models import OIDCIdentity, User


ISSUER = "https://auth.example/application/o/rent/"


@pytest.mark.django_db
def test_links_only_the_explicit_user_id(capsys):
    user = User.objects.create_user("owner", email="shared@example.com")
    User.objects.create_user("other", email="shared@example.com")
    call_command("link_oidc_identity", user_id=user.pk, issuer=ISSUER, subject="stable-1")
    identity = OIDCIdentity.objects.get()
    assert identity.user_id == user.pk
    assert "shared@example.com" not in capsys.readouterr().out


@pytest.mark.django_db
def test_refuses_unknown_user_and_each_conflicting_link():
    first = User.objects.create_user("first")
    second = User.objects.create_user("second")
    OIDCIdentity.objects.create(user=first, issuer=ISSUER, subject="stable-1")
    with pytest.raises(CommandError, match="Unknown user"):
        call_command("link_oidc_identity", user_id=999999, issuer=ISSUER, subject="new")
    with pytest.raises(CommandError, match="already linked"):
        call_command("link_oidc_identity", user_id=first.pk, issuer=ISSUER, subject="new")
    with pytest.raises(CommandError, match="already linked"):
        call_command("link_oidc_identity", user_id=second.pk, issuer=ISSUER, subject="stable-1")
    assert OIDCIdentity.objects.count() == 1

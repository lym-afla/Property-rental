import pytest
from django.urls import reverse
from unittest.mock import patch


def test_landlord_cannot_delete_other_landlords_property(auth_client, sample_property, other_landlord_user):
    # sample_property is owned by landlord_user (the auth_client's user).
    # Attempt to delete it as other_landlord_user's session.
    from django.test import Client
    other_client = Client()
    other_client.force_login(other_landlord_user)
    url = reverse("rentals:handle_element", kwargs={"data_type": "property", "element_id": sample_property.id})
    resp = other_client.delete(url)
    assert resp.status_code == 403
    # Confirm the property still exists
    from rentals.models import Property
    assert Property.objects.filter(pk=sample_property.pk).exists()


def test_landlord_cannot_delete_other_landlords_tenant(auth_client, sample_property, other_landlord_user):
    # Tenant lives in sample_property, which is owned by landlord_user.
    # other_landlord_user must not be able to delete it.
    from django.test import Client
    from rentals.models import Tenant
    from rentals.tests.factories import TenantFactory

    tenant = TenantFactory(property=sample_property)
    other_client = Client()
    other_client.force_login(other_landlord_user)
    url = reverse("rentals:handle_element", kwargs={"data_type": "tenant", "element_id": tenant.id})
    resp = other_client.delete(url)
    assert resp.status_code == 403
    # The tenant row must survive the unauthorized delete.
    assert Tenant.objects.filter(pk=tenant.pk).exists()


def test_landlord_cannot_delete_other_landlords_transaction(auth_client, sample_property, other_landlord_user):
    # Transaction is booked against sample_property, owned by landlord_user.
    # other_landlord_user must not be able to delete it.
    from django.test import Client
    from rentals.models import Transaction
    from rentals.tests.factories import TransactionFactory

    transaction = TransactionFactory(property=sample_property, category="rent")
    other_client = Client()
    other_client.force_login(other_landlord_user)
    url = reverse("rentals:handle_element", kwargs={"data_type": "transaction", "element_id": transaction.id})
    resp = other_client.delete(url)
    assert resp.status_code == 403
    # The transaction row must survive the unauthorized delete.
    assert Transaction.objects.filter(pk=transaction.pk).exists()


def test_landlord_cannot_delete_other_landlords_property_valuation(auth_client, sample_property, other_landlord_user):
    # propertyValuation (Property_capital_structure) is attached to sample_property,
    # which is owned by landlord_user. other_landlord_user must not be able to delete it.
    from django.test import Client
    from rentals.models import Property_capital_structure
    from rentals.tests.factories import PropertyCapitalStructureFactory

    valuation = PropertyCapitalStructureFactory(property=sample_property)
    other_client = Client()
    other_client.force_login(other_landlord_user)
    url = reverse("rentals:handle_element", kwargs={"data_type": "propertyValuation", "element_id": valuation.id})
    resp = other_client.delete(url)
    assert resp.status_code == 403
    # The valuation row must survive the unauthorized delete.
    assert Property_capital_structure.objects.filter(pk=valuation.pk).exists()


# ---------------------------------------------------------------------------
# Task 7: unauthenticated access + update_fx_view scoping
# ---------------------------------------------------------------------------

# URL names verified against rentals/urls.py. Note: the view function is named
# ``update_fx_view`` but its URL name is ``update_fx`` (see urls.py).
# ``new_form`` requires a ``form_type`` kwarg; ``chart_data_request`` is a GET
# endpoint but the auth gate must trigger on the incoming request regardless
# of method, so we hit it with its natural verb. (Task 8 removed the
# ``update_date`` endpoint entirely along with the per-request global.)

AUTH_REQUIRED_URLS_GET = [
    "rentals:update_fx",
    "rentals:fx_list",
    "rentals:property_choices",
    "rentals:chart_data_request",
]


@pytest.mark.parametrize("url_name", AUTH_REQUIRED_URLS_GET)
def test_anonymous_get_is_rejected(db, client, url_name):
    """Anonymous GET to a protected endpoint must redirect to login or 401/403."""
    url = reverse(url_name)
    resp = client.get(url)
    assert resp.status_code in (302, 401, 403), (
        f"{url_name} returned {resp.status_code} for anonymous GET; expected 302/401/403"
    )
    if resp.status_code == 302:
        assert "/login" in resp.url or "/accounts/login" in resp.url, (
            f"{url_name} redirected to {resp.url!r}, expected a login URL"
        )


def test_anonymous_get_new_form_rejected(db, client):
    """Anonymous GET to new_form must redirect to login (currently reads request.user)."""
    url = reverse("rentals:new_form", kwargs={"form_type": "property"})
    resp = client.get(url)
    assert resp.status_code in (302, 401, 403)
    if resp.status_code == 302:
        assert "/login" in resp.url or "/accounts/login" in resp.url


def test_update_fx_view_only_processes_requesting_users_properties(db, landlord_user, other_landlord_user):
    """update_fx_view must scope its queryset to owned_by__user=request.user.

    The view iterates properties and calls ``FX.update_fx_rates(property.id)`` for
    each. We mock that classmethod (it would otherwise hit Yahoo Finance) and
    assert it was invoked once per property OWNED BY THE LOGGED-IN USER and never
    for ``other_landlord_user``'s property.
    """
    from django.test import Client
    from rentals.models import Property
    from rentals.tests.factories import PropertyFactory

    # landlord_user already has a landlord row via the fixture; give them a
    # property. other_landlord_user also has a property — that one must NOT be touched.
    my_property = PropertyFactory(owned_by=landlord_user.landlord)
    other_property = PropertyFactory(owned_by=other_landlord_user.landlord)

    client = Client()
    client.force_login(landlord_user)

    # Patch the network-touching classmethod at the source module so the view's
    # ``FX.update_fx_rates(...)`` call resolves to the mock regardless of import style.
    with patch("rentals.models.FX.update_fx_rates") as mock_update:
        resp = client.get(reverse("rentals:update_fx"))

    assert resp.status_code == 200
    # The view must have considered exactly the user's own properties.
    called_property_ids = {call.args[0] for call in mock_update.call_args_list}
    assert called_property_ids == {my_property.id}, (
        f"update_fx_view processed property ids {called_property_ids}; "
        f"expected only {{{my_property.id}}} (requesting user's property). "
        f"other_landlord_user's property id {other_property.id} must NOT be touched."
    )
    assert other_property.id not in called_property_ids


# ---------------------------------------------------------------------------
# Task 8: per-user as-of date isolation
# ---------------------------------------------------------------------------
#
# The process-global ``effective_current_date`` in ``rentals/utils`` was a
# cross-user-bleed bug: one user mutating the as-of date changed it for every
# concurrent user. Task 8 replaces it with a per-user ``User.effective_date``
# field plus a ``get_effective_date(user)`` helper. These tests pin the
# per-user isolation contract.

def test_effective_date_is_per_user(db, landlord_user, other_landlord_user):
    """Two users with different ``effective_date`` values must observe
    different as-of dates from ``get_effective_date``.

    Before Task 8 this was impossible because the date lived in a single
    module global mutated per-request; any user's update bled into every
    other user's view. With the per-user field each user sees their own
    date.
    """
    from datetime import date
    from rentals.utils import get_effective_date

    landlord_user.effective_date = date(2024, 1, 1)
    landlord_user.save()
    other_landlord_user.effective_date = date(2025, 6, 1)
    other_landlord_user.save()

    assert get_effective_date(landlord_user) == date(2024, 1, 1)
    assert get_effective_date(other_landlord_user) == date(2025, 6, 1)


def test_get_effective_date_defaults_to_today_when_unset(db, landlord_user):
    """A user with no ``effective_date`` falls back to ``date.today()``.

    This preserves existing behavior for users created before the field
    existed (and for the characterization tests, which run with an empty
    ``effective_date``).
    """
    from datetime import date
    from rentals.utils import get_effective_date

    # User was created by the factory without setting effective_date.
    assert landlord_user.effective_date is None
    assert get_effective_date(landlord_user) == date.today()

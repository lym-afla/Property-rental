import json

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
# Final review: PUT IDOR in handle_element (mirrors Task 6 DELETE pattern)
# ---------------------------------------------------------------------------
#
# Before this fix the PUT branch of ``handle_element`` performed NO ownership
# check at all: any authenticated landlord could PUT to
# ``/handling/<data_type>/<other_landlords_id>`` and mutate another
# landlord's records. The DELETE branch (Task 6) and GET branch already
# scoped to the requesting user; PUT did not. Each test builds an entity
# owned by ``landlord_user``, PUTs as ``other_landlord_user``, and asserts
# 403 + the original record survives unchanged.

def _put_as_other(url, payload, other_landlord_user):
    """Helper: PUT ``payload`` to ``url`` authenticated as
    ``other_landlord_user``. Returns the response."""
    from django.test import Client

    other_client = Client()
    other_client.force_login(other_landlord_user)
    return other_client.put(
        url,
        data=json.dumps(payload),
        content_type="application/json",
    )


def test_landlord_cannot_put_other_landlords_property(sample_property, other_landlord_user):
    # sample_property is owned by landlord_user; other_landlord_user must
    # not be able to rename (or otherwise mutate) it via PUT.
    from rentals.models import Property

    original_name = sample_property.name
    url = reverse(
        "rentals:handle_element",
        kwargs={"data_type": "property", "element_id": sample_property.id},
    )
    resp = _put_as_other(
        url,
        {
            "name": "Hijacked Name",
            "location": sample_property.location,
            "num_bedrooms": sample_property.num_bedrooms,
            "currency": sample_property.currency,
        },
        other_landlord_user,
    )
    assert resp.status_code == 403
    sample_property.refresh_from_db()
    assert sample_property.name == original_name, "PUT mutated a property the caller does not own"


def test_landlord_cannot_put_other_landlords_tenant(sample_property, other_landlord_user):
    # Tenant lives in sample_property, owned by landlord_user.
    from rentals.models import Tenant
    from rentals.tests.factories import TenantFactory

    tenant = TenantFactory(property=sample_property)
    original_first_name = tenant.first_name
    url = reverse(
        "rentals:handle_element",
        kwargs={"data_type": "tenant", "element_id": tenant.id},
    )
    resp = _put_as_other(
        url,
        {
            "first_name": "Hijacked",
            "last_name": tenant.last_name,
            "phone": tenant.phone,
            "property": sample_property.id,
            "lease_start": tenant.lease_start.isoformat(),
        },
        other_landlord_user,
    )
    assert resp.status_code == 403
    tenant.refresh_from_db()
    assert tenant.first_name == original_first_name, "PUT mutated a tenant the caller does not own"


def test_landlord_cannot_put_other_landlords_transaction(sample_property, other_landlord_user):
    # Transaction is booked against sample_property, owned by landlord_user.
    from rentals.models import Transaction
    from rentals.tests.factories import TransactionFactory

    transaction = TransactionFactory(property=sample_property, category="rent")
    original_comment = transaction.comment
    url = reverse(
        "rentals:handle_element",
        kwargs={"data_type": "transaction", "element_id": transaction.id},
    )
    resp = _put_as_other(
        url,
        {
            "property": sample_property.id,
            "category": "rent",
            "amount": "9999.00",
            "currency": transaction.currency,
            "date": transaction.date.isoformat(),
            "comment": "hijacked-by-other-landlord",
            "period": transaction.period,
        },
        other_landlord_user,
    )
    assert resp.status_code == 403
    transaction.refresh_from_db()
    assert transaction.comment == original_comment, "PUT mutated a transaction the caller does not own"


def test_landlord_cannot_put_other_landlords_property_valuation(sample_property, other_landlord_user):
    # propertyValuation (Property_capital_structure) is attached to
    # sample_property, owned by landlord_user.
    from rentals.models import Property_capital_structure
    from rentals.tests.factories import PropertyCapitalStructureFactory

    valuation = PropertyCapitalStructureFactory(property=sample_property)
    original_value = valuation.capital_structure_value
    url = reverse(
        "rentals:handle_element",
        kwargs={"data_type": "propertyValuation", "element_id": valuation.id},
    )
    resp = _put_as_other(
        url,
        {
            "property": sample_property.id,
            "capital_structure_date": valuation.capital_structure_date.isoformat(),
            "capital_structure_value": "9999999",
            "capital_structure_debt": "0",
        },
        other_landlord_user,
    )
    assert resp.status_code == 403
    valuation.refresh_from_db()
    assert valuation.capital_structure_value == original_value, (
        "PUT mutated a property valuation the caller does not own"
    )


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


def test_anonymous_property_valuation_rejected(db, client):
    """Anonymous GET to property_valuation must redirect to login or 401/403.

    Regression guard: before this fix the view had no ``@login_required``
    and unconditionally read ``request.session['chart_settings']``, which
    is unset for an anonymous session → KeyError → 500. The fix adds
    ``@login_required`` so Django's auth gate fires first.
    """
    url = reverse("rentals:property_valuation", kwargs={"property_id": 1})
    resp = client.get(url)
    assert resp.status_code in (302, 401, 403), (
        f"property_valuation returned {resp.status_code} for anonymous GET; "
        f"expected 302/401/403 (before the fix this was a 500 KeyError on "
        f"request.session['chart_settings'])"
    )
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


# ---------------------------------------------------------------------------
# Task 14: handle_element must reject unknown data_type with 400 (not 500)
# ---------------------------------------------------------------------------
#
# The outer ``match data_type:`` in ``handle_element`` had no ``case _:``
# default. An unknown ``data_type`` (typo, attacker probe, stale client)
# fell through with ``element`` unbound, and the next reference to
# ``element`` raised ``NameError`` → Django returned a 500. The fix adds
# an explicit ``case _:`` returning 400. Note this is a sibling guard to
# the existing default in ``handle_data`` (the bulk-data view) — the two
# outer matches are independent and Task 14 only adds the missing one in
# ``handle_element``.


def test_handle_element_unknown_data_type_returns_400(auth_client):
    """GET to handle_element with an unrecognized ``data_type`` must
    return 400, not 500.

    Regression guard: before Task 14 the unknown-type branch fell through
    the outer ``match`` with ``element`` unbound, raising ``NameError``
    on the next reference and surfacing as a 500 to the client.
    """
    url = reverse(
        "rentals:handle_element",
        kwargs={"data_type": "unknown_type", "element_id": 1},
    )
    resp = auth_client.get(url)
    assert resp.status_code == 400, (
        f"unknown data_type expected 400; got {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# Task 15: effective_date exposed via the profile settings form
# ---------------------------------------------------------------------------
#
# Task 8 added the per-user ``User.effective_date`` field and removed the
# navbar date picker, but added no replacement UI — users lost the ability
# to change their as-of date. Task 15 wires the field into the existing
# ``UserSettingsForm`` on the profile page. These tests pin the POST flow:
# the form must persist ``effective_date`` to the ``User`` row, and a blank
# submission must clear it so ``get_effective_date`` falls back to today
# (preserving the "leave blank to always use today" help text contract).
#
# The settings form has other required fields (default_currency,
# chart_frequency, chart_timeline, digits); every POST below includes
# valid values for them so form validation passes and the effective_date
# field is what's under test.

def _settings_post_data(**overrides):
    """Minimal valid POST body for ``UserSettingsForm``.

    Mirrors the model defaults (USD / Monthly / 6m / 0 digits). Tests
    override individual fields (typically ``effective_date``).
    """
    data = {
        "default_currency": "USD",
        "chart_frequency": "M",
        "chart_timeline": "6m",
        "digits": "0",
    }
    data.update(overrides)
    return data


def test_user_can_set_effective_date_via_api(db, landlord_user):
    """PATCHing ``effective_date`` to /api/v1/auth/me/ must persist it on the User.
    (Replaces the old profile_page POST test — the SPA uses the DRF endpoint.)
    """
    from datetime import date
    from django.test import Client
    from rentals.utils import get_effective_date

    client = Client()
    client.force_login(landlord_user)

    resp = client.patch(
        "/api/v1/auth/me/",
        data={"effective_date": "2024-06-15"},
        content_type="application/json",
    )
    assert resp.status_code == 200, f"PATCH /me/ failed: {resp.status_code} {resp.content!r}"

    landlord_user.refresh_from_db()
    assert landlord_user.effective_date == date(2024, 6, 15)
    assert get_effective_date(landlord_user) == date(2024, 6, 15)


def test_blank_effective_date_defaults_to_today(db, landlord_user):
    """PATCHing a blank ``effective_date`` clears the field so
    ``get_effective_date`` falls back to ``date.today()``.
    """
    from datetime import date
    from django.test import Client
    from rentals.utils import get_effective_date

    landlord_user.effective_date = date(2020, 1, 1)
    landlord_user.save()

    client = Client()
    client.force_login(landlord_user)

    resp = client.patch(
        "/api/v1/auth/me/",
        data={"effective_date": None},
        content_type="application/json",
    )
    assert resp.status_code == 200

    landlord_user.refresh_from_db()
    assert landlord_user.effective_date is None, (
        f"blank effective_date should clear the field; got {landlord_user.effective_date!r}"
    )
    assert get_effective_date(landlord_user) == date.today()


def test_effective_date_field_present_on_profile_form(db):
    """``UserSettingsForm`` must declare the ``effective_date`` field so it
    renders on the profile page and is saved by ``settings_form.save()``.

    Regression guard for Task 15: the navbar date picker was removed in
    Task 8 with no replacement; this asserts the replacement exists in the
    form (the field is declared, bound to the User model, optional, and
    renders a native date input). Asserting on the form class rather than
    the rendered HTML avoids a Django/Python 3.14 test-client interaction
    (``store_rendered_templates`` calls ``copy(context)`` which fails on
    3.14 for any template-rendering view) that is unrelated to this task.
    """
    from rentals.forms import UserSettingsForm
    from django.forms.widgets import DateInput

    form = UserSettingsForm()
    assert "effective_date" in form.fields, (
        "UserSettingsForm must include effective_date so it renders on the profile page"
    )
    field = form.fields["effective_date"]
    assert field.required is False, (
        "effective_date must be optional (blank means 'use today' via get_effective_date)"
    )
    widget = field.widget
    assert isinstance(widget, DateInput), (
        f"effective_date widget must be a DateInput for a native date picker; got {type(widget).__name__}"
    )
    assert widget.input_type == "date", (
        f"effective_date widget must render type='date'; got input_type={widget.input_type!r}"
    )
    # And it's bound to the User model so save() persists it.
    assert "effective_date" in UserSettingsForm._meta.fields, (
        "effective_date must be in UserSettingsForm.Meta.fields so ModelForm.save() persists it"
    )

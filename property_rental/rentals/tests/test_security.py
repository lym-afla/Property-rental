"""Security / isolation tests that survive the legacy cleanup (Task 10 of Plan B2).

The bulk of this file historically pinned IDOR behavior on the legacy
template views (``handle_element``, ``create_element``, ``table_data``,
``vacate_tenant``, ``new_form``, ``property_valuation``,
``chart_data_request``, ``update_fx_view``, ``property_choices``) plus
the inline-serializer PUT/DELETE branches and the ``UserSettingsForm``
regressions. All of those views and forms were deleted in Task 10 of
Plan B2 — their equivalent coverage now lives in the API-layer tests:

* IDOR on create/retrieve/update/delete: ``test_api.py``'s
  ``test_*_excludes_other_landlords`` / ``test_create_*_rejects_*`` /
  ``test_*_retrieve_other_landlord_returns_404`` tests.
* Anonymous-access enforcement: ``test_api.py``'s
  ``test_*_requires_auth`` tests.
* ``update_fx_view`` scoping: ``test_api.py``'s
  ``test_fx_update_endpoint``.
* The unknown-data-type 400 guard on ``handle_element``: obsolete — the
  endpoint no longer exists, and the DRF router returns 404 for unknown
  paths.
* The ``UserSettingsForm`` regression: the form was deleted along with
  the rest of ``forms.py``; ``effective_date`` is now persisted via
  PATCH ``/api/v1/auth/me/`` (covered by
  ``test_user_can_set_effective_date_via_api`` /
  ``test_blank_effective_date_defaults_to_today`` in ``test_auth_api``).

What STAYS here is the per-user ``effective_date`` isolation contract
(Task 8): the module global ``effective_current_date`` was a
cross-user-bleed bug, replaced with a per-user ``User.effective_date``
field plus a ``get_effective_date(user)`` helper. These two tests pin
the isolation contract and do not depend on any view layer.
"""


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


def test_production_effective_date_uses_business_timezone_today(
    settings, monkeypatch, landlord_user
):
    from datetime import date
    from rentals import utils

    settings.LOCAL_PASSWORD_AUTH_ENABLED = False
    landlord_user.effective_date = date(2040, 1, 1)
    monkeypatch.setattr(utils.timezone, "localdate", lambda: date(2026, 7, 31))

    assert utils.get_effective_date(landlord_user) == date(2026, 7, 31)

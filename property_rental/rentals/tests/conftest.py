"""Pytest fixtures shared by the characterization tests.

These mirror the personas the test suite exercises most often: a logged-in
landlord with a property, plus an ``auth_client`` wired to that landlord.
"""

import pytest
from django.test import Client

from rentals.tests.factories import (
    LandlordFactory,
    PropertyFactory,
    UserFactory,
)


@pytest.fixture
def landlord_user(db):
    user = UserFactory(is_landlord=True)
    LandlordFactory(user=user)
    return user


@pytest.fixture
def other_landlord_user(db):
    user = UserFactory(is_landlord=True)
    LandlordFactory(user=user)
    return user


@pytest.fixture
def auth_client(db, landlord_user):
    c = Client()
    c.force_login(landlord_user)
    return c


@pytest.fixture
def sample_property(db, landlord_user):
    return PropertyFactory(owned_by=landlord_user.landlord)


# These characterization modules seed the legacy FX table directly.
_LEGACY_FX_MODULES = frozenset({
    'test_services.py', 'test_financials_char.py', 'test_analytics_pnl.py',
    'test_analytics_cash_flow.py', 'test_fx_refresh.py', 'test_api.py',
    'test_factories_smoke.py', 'test_analytics_tenant.py',
    'test_financials_consolidation.py', 'test_fx_char.py',
    'test_fx_migration.py', 'test_migration_command.py',
    'test_analytics_portfolio.py', 'test_deposits_analytics.py',
    'test_stats_endpoints.py',
})


@pytest.fixture(autouse=True)
def _legacy_fx_for_existing_characterization(request, settings):
    if request.node.path.name in _LEGACY_FX_MODULES:
        settings.FX_BACKEND = 'legacy'

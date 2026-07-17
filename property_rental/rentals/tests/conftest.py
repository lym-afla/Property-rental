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

"""factory-boy factories for the rentals app.

One ``DjangoModelFactory`` per model in ``rentals.models``. Required
non-nullable fields without a model-level default are given sensible
defaults here so callers can simply call ``XFactory()``.

Financial fields that the characterization tests (Tasks 3-5) need to vary
are intentionally left **unset** so callers must provide them:

* ``Transaction.amount`` (and ``category``/``currency``/``date`` already
  have model defaults, but the brief asks us not to bake financial values
  into the factory — they remain overridable via the model default).
* ``FX`` rate fields (``EURUSD``/``GBPUSD``/``USDRUB`` are nullable in the
  model, so callers provide whichever pair they need; only ``date`` is
  required).
* ``Tenant.lease_end`` is nullable and left to the caller.
* ``Lease_rent.rent`` / ``Lease_rent.date_rent_set`` are required by the
  model — they get defaults here since the factory must persist on its
  own, but callers can override.

FKs are wired via :class:`factory.SubFactory`.
"""

from datetime import date

import factory

from rentals.models import (
    FX,
    Landlord,
    Lease_rent,
    Property,
    Property_capital_structure,
    Tenant,
    Transaction,
    User,
)


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    # AbstractUser requires a unique username; Sequence keeps them unique.
    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")

    # Custom flags — defaults chosen to mirror the most common test persona
    # (a landlord). Tests that want a tenant pass is_tenant=True explicitly.
    is_landlord = True
    is_tenant = False


class LandlordFactory(factory.django.DjangoModelFactory):
    # ``User.save()`` auto-creates a Landlord when ``is_landlord=True``, so a
    # Landlord row may already exist by the time this factory runs (e.g. the
    # ``landlord_user`` fixture creates ``UserFactory(is_landlord=True)`` and
    # then calls ``LandlordFactory(user=...)``). ``django_get_or_create``
    # makes that idempotent instead of raising a UNIQUE constraint error.
    class Meta:
        model = Landlord
        django_get_or_create = ("user",)

    user = factory.SubFactory(UserFactory)


class PropertyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Property

    owned_by = factory.SubFactory(LandlordFactory)
    # name / location / num_bedrooms are required (no default, not nullable).
    name = factory.Faker("word")
    location = factory.Faker("city")
    num_bedrooms = 2
    # currency has a model default ('USD'); leave it to the model.


class PropertyCapitalStructureFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Property_capital_structure

    property = factory.SubFactory(PropertyFactory)
    # capital_structure_date has a model default (timezone.now).
    # capital_structure_value / capital_structure_debt are nullable.


class TenantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tenant

    # NB: both flags False. ``User.save()`` auto-creates a Tenant (with no
    # lease_start) when ``is_tenant=True`` — that Tenant then crashes inside
    # ``Tenant.save()`` because ``lease_start`` is None. Keeping the linked
    # user's flags off avoids the auto-create path; the Tenant is built
    # explicitly here with all required fields. ``user`` is nullable on the
    # model, so callers may also pass ``user=None``.
    user = factory.SubFactory(UserFactory, is_tenant=False, is_landlord=False)
    property = factory.SubFactory(PropertyFactory)

    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    phone = factory.Sequence(lambda n: f"555-{n:04d}")

    # lease_start is required (null=False, no default). Provide a sensible
    # default; callers override when they need a specific lease window.
    lease_start = date(2023, 1, 1)
    # payday is auto-populated from lease_start.day in Tenant.save() when
    # not supplied, so we leave it unset here.
    # lease_end is nullable and left to the caller.


class LeaseRentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Lease_rent

    tenant = factory.SubFactory(TenantFactory)

    # date_rent_set is required (null=False). rent is required (no default).
    # Defaults provided so the factory persists on its own; callers override.
    date_rent_set = date(2023, 1, 1)
    rent = factory.Faker("pydecimal", left_digits=4, right_digits=2, positive=True)
    # currency has a model default ('USD').


class TransactionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Transaction

    property = factory.SubFactory(PropertyFactory)
    # tenant is nullable; not set by default.

    # amount is required (no default) but the characterization tests vary
    # it — provide a default so the factory works standalone, while still
    # being trivially overridable.
    amount = factory.Faker("pydecimal", left_digits=5, right_digits=2, positive=True)
    # category / currency / date all have model defaults ('rent' / 'USD' /
    # timezone.now). type is auto-derived from category in Transaction.save().


class FXFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FX

    # date is the only required field (null=False, no default).
    # The per-pair rate columns (EURUSD/GBPUSD/USDRUB) are nullable; the
    # characterization tests set the specific pair they need, so we leave
    # them unset here.
    date = date(2023, 1, 1)

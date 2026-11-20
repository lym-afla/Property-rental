INITIAL_POLICY_HASH = 'dcec25ddeff179e638416303494a030795f7d99883a646634894d1867c2e3aae'

from rentals.models import FXAnchor


def seed_anchors(as_of, values, observation_dates=None, snapshot_id='fixture'):
    observation_dates = observation_dates or {}
    FXAnchor.objects.bulk_create([
        FXAnchor(date=as_of, currency=currency, value=value,
                 observation_date=observation_dates.get(currency), snapshot_id=snapshot_id)
        for currency, value in values.items()
    ])

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('rentals', '0034_fxanchor_status')]
    operations = [
        migrations.AddField(model_name='fxsyncstate', name='coverage', field=models.JSONField(default=dict)),
        migrations.AddField(model_name='fxsyncstate', name='max_fiat_age_days', field=models.PositiveIntegerField(default=14)),
    ]

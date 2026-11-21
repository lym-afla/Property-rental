from django.db import migrations, models


def carry_existing(apps, schema_editor):
    apps.get_model('rentals', 'FXAnchor').objects.filter(
        observation_date__lt=models.F('date')).update(status='carried')


class Migration(migrations.Migration):
    dependencies = [('rentals', '0033_fxanchor_fxsyncstate_and_more')]
    operations = [
        migrations.AddField(
            model_name='fxanchor', name='status',
            field=models.CharField(max_length=9, default='completed', choices=[
                ('completed', 'Completed'), ('carried', 'Carried'), ('held', 'Held')])),
        migrations.RunPython(carry_existing, migrations.RunPython.noop),
    ]

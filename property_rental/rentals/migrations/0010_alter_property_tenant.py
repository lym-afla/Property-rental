# Generated by Django 4.2.4 on 2023-10-01 10:07

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('rentals', '0009_remove_landlord_property_owned'),
    ]

    operations = [
        migrations.AlterField(
            model_name='property',
            name='tenant',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='property', to='rentals.tenant'),
        ),
    ]

# Generated by Django 4.2.4 on 2023-08-23 12:14

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('rentals', '0003_property_area_property_location_property_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='property',
            name='tenant',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='property', to='rentals.tenant'),
        ),
        migrations.AlterField(
            model_name='landlord',
            name='property_owned',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='property',
            name='value_currency',
            field=models.CharField(choices=[('US$', 'USD'), ('€', 'EUR'), ('£', 'GBP'), ('₽', 'RUB')], default='US$', max_length=3, null=True),
        ),
    ]

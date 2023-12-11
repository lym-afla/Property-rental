# Generated by Django 4.2.4 on 2023-12-10 10:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rentals', '0012_remove_property_property_value_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='property',
            name='currency',
        ),
        migrations.AddField(
            model_name='property_capital_structure',
            name='currency',
            field=models.CharField(choices=[('USD', '$'), ('EUR', '€'), ('GBP', '£'), ('RUB', '₽')], default='USD', max_length=3, null=True),
        ),
    ]

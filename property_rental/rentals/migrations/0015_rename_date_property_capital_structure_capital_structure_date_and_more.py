# Generated by Django 4.2.4 on 2023-12-16 22:45

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('rentals', '0014_remove_property_capital_structure_currency_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='property_capital_structure',
            old_name='date',
            new_name='capital_structure_date',
        ),
        migrations.RenameField(
            model_name='property_capital_structure',
            old_name='debt',
            new_name='capital_structure_debt',
        ),
        migrations.RenameField(
            model_name='property_capital_structure',
            old_name='value',
            new_name='capital_structure_value',
        ),
    ]

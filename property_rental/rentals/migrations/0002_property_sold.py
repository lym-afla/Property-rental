# Generated by Django 4.2.4 on 2023-10-12 14:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rentals', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='property',
            name='sold',
            field=models.DateField(blank=True, null=True),
        ),
    ]

# Generated by Django 4.2.4 on 2023-12-02 23:00

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rentals', '0009_alter_user_digits'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='digits',
            field=models.IntegerField(default=0, validators=[django.core.validators.MaxValueValidator(6)]),
        ),
    ]
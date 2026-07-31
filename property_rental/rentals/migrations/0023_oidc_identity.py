from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("rentals", "0022_migrate_legacy_other_income")]

    operations = [
        migrations.CreateModel(
            name="OIDCIdentity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("issuer", models.URLField(editable=False, max_length=500)),
                ("subject", models.CharField(editable=False, max_length=255)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="oidc_identity", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="oidcidentity",
            constraint=models.UniqueConstraint(fields=("issuer", "subject"), name="unique_oidc_issuer_subject"),
        ),
    ]

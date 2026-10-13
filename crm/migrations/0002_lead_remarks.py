from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="remarks",
            field=models.CharField(blank=True, max_length=2000),
        ),
    ]

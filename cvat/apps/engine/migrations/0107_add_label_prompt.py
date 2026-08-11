from django.db import migrations

import cvat.apps.engine.models


class Migration(migrations.Migration):

    dependencies = [
        ("engine", "0106_add_interval_annotations"),
    ]

    operations = [
        migrations.AddField(
            model_name="label",
            name="prompt",
            field=cvat.apps.engine.models.SafeCharField(blank=True, default="", max_length=1024),
        ),
    ]

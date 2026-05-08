from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_department_created_season'),
    ]

    operations = [
        migrations.AddField(
            model_name='department',
            name='ended_season',
            field=models.ForeignKey(
                blank=True,
                help_text='The last season this department participated in. '
                          'Set when the department is removed from the active season. '
                          'The department will not appear in seasons after this one, '
                          'but remains visible in all seasons up to and including this one.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='retired_departments',
                to='core.season',
            ),
        ),
    ]

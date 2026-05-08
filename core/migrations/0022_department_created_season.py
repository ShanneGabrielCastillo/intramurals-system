from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_department_group'),
    ]

    operations = [
        migrations.AddField(
            model_name='department',
            name='created_season',
            field=models.ForeignKey(
                blank=True,
                help_text='The first season this department officially exists in. '
                          'Auto-set to the active season when the department is created. '
                          'The department will not appear in seasons before this one.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='departments',
                to='core.season',
            ),
        ),
    ]

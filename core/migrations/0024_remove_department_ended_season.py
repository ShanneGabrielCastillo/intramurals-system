from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_department_ended_season'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='department',
            name='ended_season',
        ),
    ]

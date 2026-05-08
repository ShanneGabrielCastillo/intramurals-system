from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0019_cleanup_mixed_division'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='event',
            name='description',
        ),
    ]

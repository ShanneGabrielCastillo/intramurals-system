from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_remove_event_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='department',
            name='group',
            field=models.CharField(
                blank=True,
                choices=[('A', 'Group A'), ('B', 'Group B')],
                default=None,
                help_text='Assign to Group A or Group B for Group Knockout events. '
                          'Leave blank if this department does not participate in Group Knockout.',
                max_length=1,
                null=True,
            ),
        ),
    ]

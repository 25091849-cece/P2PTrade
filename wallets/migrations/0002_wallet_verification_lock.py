from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wallets', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='wallet',
            name='verification_failed_attempts',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='wallet',
            name='verification_locked_until',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

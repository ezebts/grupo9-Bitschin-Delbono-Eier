from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('chats', '0004_conversation_quote_request'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversation',
            name='client_notified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='conversation',
            name='pharmacy_notified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

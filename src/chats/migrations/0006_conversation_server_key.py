from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('chats', '0005_conversation_notice_times'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversation',
            name='server_public_key',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='conversation',
            name='server_key_fingerprint',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='conversation',
            name='server_private_key',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='message',
            name='body',
            field=models.TextField(),
        ),
    ]

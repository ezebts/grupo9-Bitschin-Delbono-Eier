import django.db.models.deletion
from django.db import migrations, models


def clear_conversations(apps, schema_editor):
    conversation_model = apps.get_model('chats', 'Conversation')
    conversation_model.objects.all().delete()


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('chats', '0003_align_conversation_with_author'),
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(clear_conversations, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='conversation',
            name='customer',
        ),
        migrations.RemoveField(
            model_name='conversation',
            name='pharmacy',
        ),
        migrations.AddField(
            model_name='conversation',
            name='quote_request',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='conversation',
                to='orders.quoterequest',
            ),
        ),
    ]

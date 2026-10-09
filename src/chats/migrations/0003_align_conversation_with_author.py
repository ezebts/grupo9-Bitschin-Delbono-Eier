import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

CUSTOMER = 'customer'


def copy_subject_into_title(apps, schema_editor):
    conversation_model = apps.get_model('chats', 'Conversation')
    for conversation in conversation_model.objects.all():
        conversation.title = conversation.subject
        conversation.save(update_fields=['title'])


def attach_customer_messages(apps, schema_editor):
    message_model = apps.get_model('chats', 'Message')
    user_message_model = apps.get_model('chats', 'UserMessage')
    for message in message_model.objects.filter(sender=CUSTOMER).select_related(
        'conversation'
    ):
        if message.conversation.customer_id is None:
            continue
        user_message = user_message_model(
            message_ptr_id=message.pk,
            author_id=message.conversation.customer_id,
            author_name=message.conversation.customer_name,
        )
        user_message.save_base(raw=True)


class Migration(migrations.Migration):
    dependencies = [
        ('chats', '0002_conversation_customer'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='conversation',
            name='title',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.RunPython(copy_subject_into_title, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='conversation',
            name='title',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='conversation',
            name='pharmacy',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='pharmacy_conversations',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='message',
            name='sender',
            field=models.CharField(
                choices=[
                    ('customer', 'Customer'),
                    ('pharmacy', 'Pharmacy'),
                    ('system', 'System'),
                ],
                max_length=8,
            ),
        ),
        migrations.CreateModel(
            name='UserMessage',
            fields=[
                (
                    'message_ptr',
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to='chats.message',
                    ),
                ),
                (
                    'author',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='chat_messages',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ('author_name', models.CharField(max_length=150)),
            ],
            bases=('chats.message',),
        ),
        migrations.RunPython(attach_customer_messages, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='conversation',
            name='customer_email',
        ),
        migrations.RemoveField(
            model_name='conversation',
            name='customer_name',
        ),
        migrations.RemoveField(
            model_name='conversation',
            name='customer_phone',
        ),
        migrations.RemoveField(
            model_name='conversation',
            name='subject',
        ),
        migrations.RemoveField(
            model_name='conversation',
            name='waiting_for_pharmacy',
        ),
        migrations.AlterModelOptions(
            name='conversation',
            options={'ordering': ('-updated_at',)},
        ),
        migrations.AlterModelOptions(
            name='message',
            options={'ordering': ('created_at', 'pk')},
        ),
    ]

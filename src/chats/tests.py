from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from chats.models import Conversation, Message

INITIAL_CONVERSATION_COUNT = 1
INITIAL_MESSAGE_COUNT = 1
CUSTOMER_REPLY_MESSAGE_COUNT = 3
PHARMACY_REPLY_MESSAGE_COUNT = 2


class InboxViewTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username='pharmacy-staff',
            email='staff@example.com',
            role='pharmacy',
        )
        self.client.force_login(user)
        self.customer = get_user_model().objects.create_user(
            username='customer',
            email='customer@example.com',
            first_name='Sofía',
            last_name='Martínez',
        )
        self.conversation = Conversation.objects.create(
            customer=self.customer,
            customer_name='Sofía Martínez',
            customer_email='sofia@example.com',
            subject='Consulta por crema',
        )
        Message.objects.create(
            conversation=self.conversation,
            sender=Message.Sender.CUSTOMER,
            body='¿Ya está lista mi crema?',
        )

    def test_inbox_requires_pharmacy_login(self):
        self.client.logout()

        response = self.client.get(reverse('chats:inbox'))

        self.assertRedirects(
            response,
            f'/accounts/login/?next={reverse("chats:inbox")}',
        )

    def test_customer_cannot_access_pharmacy_inbox(self):
        self.client.force_login(self.customer)

        response = self.client.get(reverse('chats:inbox'))

        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_inbox_reads_conversations_from_database(self):
        response = self.client.get(reverse('chats:inbox'))

        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, 'Bandeja de entrada')
        self.assertContains(response, 'Sofía Martínez')
        self.assertContains(response, '¿Ya está lista mi crema?')

    def test_search_filters_database_conversations(self):
        Conversation.objects.create(
            customer_name='Tomás Rodríguez',
            customer_email='tomas@example.com',
            subject='Consulta sobre receta',
        )

        response = self.client.get(reverse('chats:inbox'), {'search': 'Sofía'})

        self.assertContains(response, 'Sofía Martínez')
        self.assertNotContains(response, 'Tomás Rodríguez')

    def test_htmx_search_returns_only_inbox_content(self):
        response = self.client.get(
            reverse('chats:inbox'),
            {'search': 'Sofía'},
            HTTP_HX_REQUEST='true',
        )

        self.assertContains(response, '<div id="inbox-content">', html=False)
        self.assertNotContains(response, '<!DOCTYPE html>', html=False)

    def test_customer_inquiry_and_first_message_are_persisted(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('chats:new_inquiry'),
            {
                'customer_phone': '1122334455',
                'subject': 'Consulta por vitamina',
                'message': '¿Tienen vitamina D en gotas?',
            },
        )

        conversation = Conversation.objects.get(
            customer=self.customer,
            subject='Consulta por vitamina',
        )
        self.assertRedirects(
            response,
            f'{reverse("chats:customer_inbox")}?conversation_id={conversation.pk}',
        )
        message = conversation.messages.get()
        assert message.sender == Message.Sender.CUSTOMER
        assert message.body == '¿Tienen vitamina D en gotas?'
        assert conversation.waiting_for_pharmacy

    def test_customer_can_see_only_their_conversations(self):
        other_conversation = Conversation.objects.create(
            customer_name='Otra persona',
            customer_email='other@example.com',
            subject='Consulta privada',
        )
        self.client.force_login(self.customer)

        response = self.client.get(reverse('chats:customer_inbox'))

        self.assertContains(response, 'Sofía Martínez')
        self.assertNotContains(response, 'Consulta privada')
        response = self.client.get(
            reverse('chats:customer_inbox'),
            {'conversation_id': other_conversation.pk},
        )
        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_customer_can_read_pharmacy_reply_and_continue_conversation(self):
        Message.objects.create(
            conversation=self.conversation,
            sender=Message.Sender.PHARMACY,
            body='Sí, ya está lista para retirar.',
        )
        self.conversation.waiting_for_pharmacy = False
        self.conversation.save()
        self.client.force_login(self.customer)

        response = self.client.get(reverse('chats:customer_inbox'))

        self.assertContains(response, 'Sí, ya está lista para retirar.')
        self.assertContains(response, 'Respondida')
        response = self.client.post(
            reverse('chats:customer_reply', args=[self.conversation.pk]),
            {'message': 'Gracias, paso por la tarde.'},
        )

        self.assertRedirects(
            response,
            f'{reverse("chats:customer_inbox")}?conversation_id={self.conversation.pk}',
        )
        self.conversation.refresh_from_db()
        assert self.conversation.waiting_for_pharmacy
        assert self.conversation.messages.count() == CUSTOMER_REPLY_MESSAGE_COUNT

    def test_customer_cannot_reply_to_another_customers_conversation(self):
        other_conversation = Conversation.objects.create(
            customer_name='Otra persona',
            customer_email='other@example.com',
            subject='Consulta privada',
        )
        self.client.force_login(self.customer)

        response = self.client.post(
            reverse('chats:customer_reply', args=[other_conversation.pk]),
            {'message': 'Mensaje no autorizado'},
        )

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert other_conversation.messages.count() == 0

    def test_customer_views_require_login(self):
        self.client.logout()

        response = self.client.get(reverse('chats:customer_inbox'))

        assert response.status_code == HTTPStatus.FOUND
        assert '/accounts/login/' in response.url

    def test_pharmacy_reply_is_persisted_and_clears_pending_status(self):
        response = self.client.post(
            reverse('chats:send_message', args=[self.conversation.pk]),
            {'message': 'Sí, ya está lista para retirar.'},
            HTTP_HX_REQUEST='true',
        )

        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, 'Sí, ya está lista para retirar.')
        self.conversation.refresh_from_db()
        assert not self.conversation.waiting_for_pharmacy
        assert self.conversation.messages.count() == PHARMACY_REPLY_MESSAGE_COUNT

        response = self.client.get(reverse('chats:inbox'))
        self.assertContains(response, 'Sí, ya está lista para retirar.')

    def test_empty_pharmacy_reply_is_rejected_without_persisting(self):
        response = self.client.post(
            reverse('chats:send_message', args=[self.conversation.pk]),
            {'message': '   '},
            HTTP_HX_REQUEST='true',
        )

        assert self.conversation.messages.count() == INITIAL_MESSAGE_COUNT
        self.assertContains(response, 'Este campo es obligatorio.')

    def test_invalid_inquiry_does_not_create_conversation(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('chats:new_inquiry'),
            {
                'subject': '',
                'message': ' ',
            },
        )

        assert response.status_code == HTTPStatus.OK
        assert Conversation.objects.count() == INITIAL_CONVERSATION_COUNT

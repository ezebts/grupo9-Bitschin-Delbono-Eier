import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import ClientAccount, Pharmacy, User
from orders.commands.create_order import CreateOrderParams, create_order
from orders.commands.request_quote import request_quote
from orders.models import Order, QuoteRequestStatus
from orders.queries.client_orders import list_client_orders

pytestmark = pytest.mark.django_db


def _customer(email='sofia@example.com'):
    user = User(
        username=email,
        email=email,
        role=User.Role.CUSTOMER,
        first_name='Sofía',
        last_name='Martínez',
    )
    user.set_unusable_password()
    user.save()
    ClientAccount.objects.create(user=user)
    return user


def _params():
    return CreateOrderParams(
        preparation_tag='creams',
        presentation='Crema 30 g',
        formula='Hidroquinona 4%',
        urgency='no_rush',
        delivery_preferences=('pickup', 'home_delivery'),
        note='Sin alcohol',
    )


def test_order_code_pads_the_id_and_then_grows():
    sofia = _customer()
    narrow = Order.create(
        sofia.client_account,
        'Hidroquinona 4%',
        'Crema 30 g',
        'no_rush',
        ('pickup',),
        '',
        'creams',
    )
    narrow.id = 42
    narrow.save()
    wide = Order.create(
        sofia.client_account,
        'Hidroquinona 4%',
        'Crema 30 g',
        'no_rush',
        ('pickup',),
        '',
        'creams',
    )
    wide.id = 100000
    wide.save()

    assert narrow.code == 'MG-00042'
    assert wide.code == 'MG-100000'


def test_quote_requests_open_one_conversation_each():
    sofia = _customer()
    other = _customer('otra@example.com')
    first = Pharmacy.objects.create(trade_name='Abrate', visible=True)
    second = Pharmacy.objects.create(trade_name='Cagnotti', visible=True)

    order = create_order(sofia.id, _params())
    first_request = request_quote(order.id, first.id)
    second_request = request_quote(order.id, second.id)

    order.refresh_from_db()
    assert order.formula == 'Hidroquinona 4%'
    assert order.code == f'MG-{order.pk:05d}'
    assert first_request.status == QuoteRequestStatus.WAITING
    assert first_request.conversation.quote_request_id == first_request.id
    assert second_request.conversation.quote_request_id == second_request.id
    assert first_request.conversation.pk != second_request.conversation.pk

    listed = list_client_orders(sofia.id)
    assert listed.total == 1
    assert listed.waiting == 1
    assert listed.orders[0].formula == 'Hidroquinona 4%'
    assert listed.orders[0].presentation == 'Crema 30 g'
    assert listed.orders[0].code == order.code
    assert listed.orders[0].quotes_received == 0
    assert listed.orders[0].quotes_total == order.quote_requests.count()
    assert listed.orders[0].status_label == 'Esperando presupuestos'
    assert list_client_orders(other.id).total == 0


def test_order_keeps_the_prescription():
    sofia = _customer()
    receta = SimpleUploadedFile('receta.pdf', b'receta')

    order = create_order(
        sofia.id,
        CreateOrderParams(
            preparation_tag='creams',
            presentation='Crema 30 g',
            formula='Hidroquinona 4%',
            urgency='no_rush',
            delivery_preferences=('pickup',),
            note='',
            prescription=receta,
        ),
    )

    order.refresh_from_db()
    assert order.prescription.name.startswith(
        f'orders/prescriptions/{order.pk}/',
    )
    assert 'receta' in order.prescription.name
    assert order.prescription.read() == b'receta'
    order.prescription.close()

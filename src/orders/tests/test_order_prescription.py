from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import ClientAccount, User
from chats.queries.customer_inbox import get_customer_inbox
from chats.tests.support import open_conversation
from orders.commands.accept_quote import accept_quote
from orders.commands.change_prescription import (
    attach_order_prescription,
    remove_order_prescription,
)
from orders.commands.create_order import CreateOrderParams, create_order
from orders.commands.submit_quote import SubmitQuoteParams, submit_quote
from orders.exceptions import (
    PrescriptionAlreadyAttachedError,
    PrescriptionCannotChangeError,
)
from orders.forms import OrderPrescriptionForm
from orders.models import DeliveryPreference, Order
from shared.values import Money

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


def _order(customer):
    return create_order(
        customer.id,
        CreateOrderParams(
            preparation_tag='creams',
            presentation='Crema 30 g',
            formula='Hidroquinona 4%',
            urgency='no_rush',
            delivery_preferences=('pickup',),
            note='',
        ),
    )


def _file(name, content):
    return SimpleUploadedFile(name, content)


def _assert_raises(error_type, callback):
    try:
        callback()
    except error_type:
        return
    pytest.fail(f'Expected {error_type.__name__} to be raised.')


def test_client_attaches_a_prescription_and_can_replace_it():
    sofia = _customer()
    order = _order(sofia)

    attached = attach_order_prescription(
        sofia.id,
        order.id,
        _file('receta.pdf', b'una'),
    )
    assert attached.prescription.read() == b'una'
    attached.prescription.close()
    assert get_customer_inbox(sofia.id, order.id).can_change_prescription

    remove_order_prescription(sofia.id, order.id)
    order.refresh_from_db()
    assert not order.prescription

    replaced = attach_order_prescription(
        sofia.id,
        order.id,
        _file('otra.pdf', b'otra'),
    )
    assert replaced.prescription.read() == b'otra'
    replaced.prescription.close()


def test_a_second_file_does_not_replace_the_prescription():
    sofia = _customer()
    order = _order(sofia)
    attach_order_prescription(sofia.id, order.id, _file('receta.pdf', b'una'))

    _assert_raises(
        PrescriptionAlreadyAttachedError,
        lambda: attach_order_prescription(
            sofia.id,
            order.id,
            _file('otra.pdf', b'otra'),
        ),
    )

    order.refresh_from_db()
    assert order.prescription.read() == b'una'
    order.prescription.close()


def test_prescription_stays_once_a_quote_is_accepted():
    customer = _customer()
    pharmacy_user = User(
        username='farmacia@example.com',
        email='farmacia@example.com',
        role=User.Role.PHARMACY,
    )
    pharmacy_user.set_unusable_password()
    pharmacy_user.save()
    order, conversation = open_conversation(customer, pharmacy_user)
    attach_order_prescription(customer.id, order.id, _file('receta.pdf', b'una'))
    submit_quote(
        pharmacy_user.id,
        conversation.id,
        SubmitQuoteParams(
            price=Money.create('ARS', '18400'),
            preparation_time='48 h hábiles',
            delivery_preferences=(DeliveryPreference.PICKUP,),
            delivery_cost=Money.create('ARS', 0),
            valid_until=(
                datetime.now(ZoneInfo(User.defaulttz)).date() + timedelta(days=7)
            ),
        ),
    )
    accept_quote(customer.id, conversation.id)

    _assert_raises(
        PrescriptionCannotChangeError,
        lambda: remove_order_prescription(customer.id, order.id),
    )
    _assert_raises(
        PrescriptionCannotChangeError,
        lambda: attach_order_prescription(
            customer.id,
            order.id,
            _file('otra.pdf', b'otra'),
        ),
    )

    order.refresh_from_db()
    assert order.prescription.read() == b'una'
    order.prescription.close()
    assert not get_customer_inbox(customer.id, order.id).can_change_prescription


def test_another_client_cannot_change_the_prescription():
    sofia = _customer()
    other = _customer('otra@example.com')
    order = _order(sofia)

    with pytest.raises(Order.DoesNotExist):
        attach_order_prescription(other.id, order.id, _file('receta.pdf', b'una'))

    with pytest.raises(Order.DoesNotExist):
        remove_order_prescription(other.id, order.id)


def test_prescription_form_rejects_a_file_that_is_not_a_document():
    form = OrderPrescriptionForm(
        data={},
        files={'prescription_file': _file('receta.txt', b'hola')},
    )

    assert not form.is_valid()
    assert 'PDF, JPG o PNG' in form.errors['prescription_file'][0]

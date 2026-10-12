from accounts.models import ClientAccount, Pharmacy, PharmacyAccount
from orders.commands.create_order import CreateOrderParams, create_order
from orders.commands.request_quote import request_quote


def open_conversation(
    customer,
    pharmacy_user,
    *,
    formula='Crema',
    trade_name='Abrate',
):
    ClientAccount.objects.get_or_create(user=customer)
    account = PharmacyAccount.objects.filter(user=pharmacy_user).first()
    if account is None:
        pharmacy = Pharmacy.objects.create(trade_name=trade_name, visible=True)
        PharmacyAccount.objects.create(user=pharmacy_user, pharmacy=pharmacy)
    else:
        pharmacy = account.pharmacy
    order = create_order(
        customer.id,
        CreateOrderParams(
            preparation_tag='creams',
            presentation='30 g',
            formula=formula,
            urgency='no_rush',
            delivery_preferences=('pickup',),
            note='',
        ),
    )
    quote_request = request_quote(order.id, pharmacy.id)
    return order, quote_request.conversation

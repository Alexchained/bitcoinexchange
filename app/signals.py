from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.shortcuts import get_object_or_404
from .models import Order, Profile, Wallet, Transaction
from datetime import datetime

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    """
    Create a profile instance associated with the new user instance created.
    """

    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=Profile)
def create_wallet(sender, instance, created, **kwargs):
    """
    Create a wallet instance associated with the new profile instance created.
    """

    if created:
        Wallet.objects.create(profile=instance)


@receiver(post_save, sender=Wallet)
def set_bitcoin_net_balance(sender, instance, created, **kwargs):
    """
    Save the initial bitcoin amount in the net balance in order to calculate profits.
    """

    if created:
        instance.bitcoin_net_balance = instance.available_bitcoin
        instance.save()


@receiver(post_save, sender=Order)
def new_order(pk):
    for order in Order.objects.all():
        if str(order.pk) == pk:
            return order


def canSell(sell_order_wallet, frozen_bitcoin):
    if sell_order_wallet.bitcoin_net_balance < frozen_bitcoin:
        return False

    return True


def canBuy(buy_order_wallet, price, frozen_bitcoin):
    if buy_order_wallet.available_dollar < price * frozen_bitcoin:
        return False

    return True


def update_orders(sell_order, buy_order):
    # full fill sell and buy
    if sell_order.bitcoin_quantity == buy_order.bitcoin_quantity:
        sell_order.status = False
        buy_order.status = False

    # full fill sell and partially fill buy
    elif sell_order.bitcoin_quantity > buy_order.bitcoin_quantity:
        sell_order.bitcoin_quantity -= buy_order.bitcoin_quantity
        buy_order.status = False

        # full fill buy and partally fill sell
    elif sell_order.btc_quantity < buy_order.btc_quantity:
        buy_order.btc_quantity -= sell_order.btc_quantity
        sell_order.status = False

    sell_order.save()
    buy_order.save()


def transaction(sell_order, buy_order):
    seller_wallet = Wallet.objects.filter(user=sell_order.user).first()
    buyer_wallet = Wallet.objects.filter(user=buy_order.user).first()
    # save transaction
    transaction = Transaction(
        buyer=buyer_wallet.user,
        seller=seller_wallet.user,
        bitcoin_quantity=buy_order.btc_quantity,
        price=buy_order.price,
        datetime=datetime.now(),
    )

    transaction.save()


def match_buy_order(buy_order):
    sell_orders_list = Order.objects.filter(
        type="S", status=True, price=buy_order.price
    ).order_by("price")

    for sell_order in sell_orders_list:

        seller_wallet = Wallet.objects.filter(user=sell_order.user).first()
        buyer_wallet = Wallet.objects.filter(user=buy_order.user).first()

        buy_order.price = sell_order.price
        buy_order.save()

        update_orders(sell_order, buy_order)

        seller_wallet.money_balance += sell_order.btc_quantity * sell_order.price
        seller_wallet.save(update_fields=["dollar_balance"])

        buyer_wallet.btc_balance += sell_order.btc_quantity
        buyer_wallet.save(update_fields=["bitcoin_balance"])

        transaction(sell_order, buy_order)


def match_sell_order(sell_order):

    buy_orders_list = Order.objects.filter(
        type="B", status=True, price__gte=sell_order.price
    ).order_by("-price")

    for buy_order in buy_orders_list:

        seller_wallet = Wallet.objects.filter(user=sell_order.user).first()
        buyer_wallet = Wallet.objects.filter(user=buy_order.user).first()

        sell_order.price = buy_order.price
        sell_order.save()

        update_orders(sell_order, buy_order)

        seller_wallet.money_balance += buy_order.btc_quantity * buy_order.price
        seller_wallet.save(update_fields=["dollar_balance"])

        buyer_wallet.btc_balance += buy_order.btc_quantity
        buyer_wallet.save(update_fields=["bitcoin_balance"])

        transaction(sell_order, buy_order)


@receiver(pre_delete, sender=Order)
def delete_order(sender, instance, **kwargs):
    """
    Unfreeze the amount needed to fulfill the order when it is canceled.
    """

    instance_wallet = get_object_or_404(Wallet, profile=instance.profile)
    if instance.type == 'B':
        # Unfreeze the dollar amount if it is a buy order
        amount = instance.quantity * instance.price
        instance_wallet.available_dollar += amount
        instance_wallet.frozen_dollar -= amount
        instance_wallet.save()

    elif instance.type == 'S':
        # Unfreeze the bitcoin amount if it is a sell order
        amount = instance.quantity
        instance_wallet.available_bitcoin += amount
        instance_wallet.frozen_bitcoin -= amount
        instance_wallet.save()
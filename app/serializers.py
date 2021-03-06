from django.shortcuts import get_object_or_404
from .models import Order, Profile, Wallet
from rest_framework import serializers


class OrderSerializer(serializers.ModelSerializer):
    """
    Order serializer for OrderViewSet.
    Fields:
    - profile
    - price
    - quantity
    - type: Buy/Sell.
    - status: False=executed, True=active.
    - created_at: Date format '31/12/2022, 23:59:59'.
    - executed_at: Date format '31/12/2022, 23:59:59'.
    """

    profile = serializers.StringRelatedField(read_only=True)
    status = serializers.BooleanField(read_only=True)
    created_at = serializers.SerializerMethodField(read_only=True)
    executed_at = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Order
        exclude = ['transaction']

    def get_created_at(self, instance):
        return instance.created_at.strftime("%d/%m/%Y, %H:%M:%S")

    def get_executed_at(self, instance):
        if instance.transaction:
            return instance.transaction.executed_at.strftime("%d/%m/%Y, %H:%M:%S")
        return None

    def validate(self, data):
        # Validate the new order only if the amount needed to fulfill the order is available

        request_user = self.context.get('request').user
        user_wallet = get_object_or_404(Wallet, profile=request_user.profile)

        if data['type'] == 'B':
            # Check the dollar balance if it is a buy order
            required_dollar = data['price'] * data['quantity']
            if (user_wallet.available_dollar - required_dollar) < 0:
                raise serializers.ValidationError('insufficient balance')

        elif data['type'] == 'S':
            # Check the bitcoin balance if it is a sell order
            if (user_wallet.available_bitcoin - data['quantity']) < 0:
                raise serializers.ValidationError('insufficient balance')

        return data


class LatestOrdersSerializer(serializers.ModelSerializer):
    """
    Order serializer for LatestOrdersListAPIView.
    Fields:
    - price
    - quantity
    - type: Buy/Sell.
    - created_at: Date format '31/12/2022, 23:59:59'.
    """

    price = serializers.FloatField(read_only=True)
    quantity = serializers.FloatField(read_only=True)
    type = serializers.CharField(read_only=True)
    created_at = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Order
        exclude = ['profile', 'status', 'transaction']

    def get_created_at(self, instance):
        return instance.created_at.strftime("%d/%m/%Y, %H:%M:%S")


class ProfileSerializer(serializers.ModelSerializer):
    """
    Profile serializer for ProfileAPIView.
    Fields:
    - user
    - active_orders
    - executed_orders
    - dollar_balance
    - bitcoin_balance
    - bitcoin_profit_percent: Percentage profits based on bitcoin.
    """

    user = serializers.StringRelatedField(read_only=True)
    active_orders = serializers.SerializerMethodField(read_only=True)
    executed_orders = serializers.SerializerMethodField(read_only=True)
    dollar_balance = serializers.SerializerMethodField(read_only=True)
    bitcoin_balance = serializers.SerializerMethodField(read_only=True)
    bitcoin_profit_percent = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Profile
        fields = '__all__'

    def get_active_orders(self, instance):
        return instance.orders.filter(status=True).count()

    def get_executed_orders(self, instance):
        return instance.orders.filter(status=False).count()

    def get_dollar_balance(self, instance):
        return instance.wallet.available_dollar + instance.wallet.frozen_dollar

    def get_bitcoin_balance(self, instance):
        return instance.wallet.available_bitcoin + instance.wallet.frozen_bitcoin

    def get_bitcoin_profit_percent(self, instance):
        delta_percent = 0
        if instance.wallet.bitcoin_net_balance:
            net_bitcoin = instance.wallet.bitcoin_net_balance
            total_bitcoin = instance.wallet.available_bitcoin + instance.wallet.frozen_bitcoin
            delta_percent = ((total_bitcoin - net_bitcoin) / net_bitcoin) * 100

        return round(delta_percent, 2)

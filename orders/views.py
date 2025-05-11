# orders/views.py
import stripe
from django.conf import settings
from rest_framework import viewsets, permissions, status, generics, serializers
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAdminUser, AllowAny, IsAuthenticated
from django.db import transaction, models
from rest_framework.generics import GenericAPIView
from .models import Order, OrderItem, Coupon
from products.models import CartItem
from .serializers import OrderSerializer
from notifications.models import Notification
from django.utils import timezone
from decimal import Decimal
import random
import string
from .permissions import IsAdminOrStaff
from django.db.models import Q
from notifications.utils import create_and_push_notification



from django.views.decorators.csrf import csrf_exempt

from shipping.models import ShippingAddress, ShippingMethod

from shipping.serializers import ShippingAddressSerializer

import logging
logger = logging.getLogger(__name__)

class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'order_id'

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, "role") and user.role == "admin":
            return Order.objects.all().order_by('-created_at')
        return Order.objects.filter(user=user).order_by('-created_at')

    def perform_create(self, serializer):
        order = serializer.save(user=self.request.user)
        order.calculate_total()

    def perform_update(self, serializer):
        order = serializer.save()
        order.calculate_total()

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrStaff])
    def update_status(self, request, order_id=None):
        try:
            order = self.get_object()
            status = request.data.get('status')

            if not status:
                return Response({'error': 'Status is required'}, status=400)

            order.status = status
            order.save()

            # ✅ Create review reminder notification if delivered
            if status == "delivered":
                for item in order.items.all():
                    create_and_push_notification(
                        user=order.user,
                        title=f"Review your product: {item.product.name}",
                        message=f"You received {item.product.name}. Share your feedback!",
                        notification_type="review",
                        data={"product_slug": item.product.slug}
                    )


            return Response({'success': True, 'message': 'Order status updated successfully'})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        
    
    @action(detail=True, methods=['get'], permission_classes=[IsAdminOrStaff])
    def details(self, request, order_id=None):  # <- FIX HERE
        order = self.get_object()  # auto gets by order_id
        serializer = self.get_serializer(order)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrStaff], url_path='update_payment_status')
    def update_payment_status(self, request, order_id=None):
        order = self.get_object()
        new_payment_status = request.data.get('payment_status')

        if not new_payment_status:
            return Response({'error': 'payment_status is required'}, status=400)

        valid_choices = [choice[0] for choice in Order.PAYMENT_STATUS_CHOICES]

        if new_payment_status not in valid_choices:
            return Response({'error': 'Invalid payment status'}, status=400)

        order.payment_status = new_payment_status
        order.save()

        return Response({'success': True, 'message': 'Payment status updated'})

    def get_queryset(self):
        user = self.request.user
        queryset = Order.objects.all() if getattr(user, "role", "") == "admin" else Order.objects.filter(user=user)

        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)

        return queryset.order_by("-created_at")


    @action(detail=False, methods=['post'], permission_classes=[IsAdminOrStaff])
    def bulk_delete(self, request):
        ids = request.data.get("order_ids", [])

        if not ids or not isinstance(ids, list):
            return Response({"error": "order_ids must be a list"}, status=400)

        deleted = 0
        for oid in ids:
            try:
                order = Order.objects.get(order_id=oid)
                if order.status == 'shipped' and getattr(request.user, "role", "") != "admin":
                    continue
                order.delete()
                deleted += 1
            except Order.DoesNotExist:
                continue

        return Response({"success": True, "deleted": deleted}, status=200)
    
    def get_queryset(self):
        user = self.request.user
        queryset = Order.objects.all() if getattr(user, "role", "") == "admin" else Order.objects.filter(user=user)

        status = self.request.query_params.get("status")
        payment_status = self.request.query_params.get("payment_status")
        payment_method = self.request.query_params.get("payment_method")
        search = self.request.query_params.get("search")

        if status:
            queryset = queryset.filter(status=status)
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)
        if search:
            queryset = queryset.filter(
                models.Q(order_id__icontains=search) |
                models.Q(user__username__icontains=search) |
                models.Q(shipping_address__phone__icontains=search)
            )

        return queryset.order_by("-created_at")




class CheckoutView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderSerializer

    def create(self, request, *args, **kwargs):
        
        user = request.user
        cart_items = CartItem.objects.filter(user=user)
        if not cart_items.exists():
            return Response({"detail": "Cart is empty"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payment_method = serializer.validated_data['payment_method']
        coupon = serializer.validated_data.get('coupon_obj')

        # ✅ Extract shipping fields from raw data
        shipping_data = request.data.get('shipping', {})
        required_fields = ['address_line_1', 'city', 'state', 'postal_code', 'country', 'phone', 'shipping_method_id']
        missing = [f for f in required_fields if not shipping_data.get(f)]
        if missing:
            return Response({"shipping": [f"{field} is required" for field in missing]}, status=status.HTTP_400_BAD_REQUEST)

        shipping_method_id = shipping_data.get('shipping_method_id')

        with transaction.atomic():
            # ✅ Create Order
            order = Order.objects.create(
                user=user,
                payment_method=payment_method,
                status='processing',
                coupon=coupon if coupon and coupon.is_valid() else None,
                shipping_method_id=shipping_method_id
            )

            # ✅ Create ShippingAddress
            ShippingAddress.objects.create(
                user=user,
                order=order,
                address_line_1=shipping_data['address_line_1'],
                address_line_2=shipping_data.get('address_line_2', ''),
                city=shipping_data['city'],
                state=shipping_data['state'],
                postal_code=shipping_data['postal_code'],
                country=shipping_data['country'],
                phone=shipping_data['phone']
            )

            # ✅ Create OrderItems
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    variant=item.variant,
                    quantity=item.quantity,
                    price_at_purchase=item.variant.price if item.variant else item.product.price
                )

            order.calculate_total(coupon=coupon if coupon and coupon.is_valid() else None)

            # ✅ Stripe intent
            client_secret = None
            if payment_method == 'card':
                try:
                    intent = stripe.PaymentIntent.create(
                        amount=int(order.total_price * 100),
                        currency='usd',
                        metadata={'order_id': order.order_id},
                        description=f"Order #{order.order_id} for {user.username}",
                    )
                    order.payment_id = intent['id']
                    order.payment_status = 'pending'
                    order.save()
                    client_secret = intent['client_secret']
                except stripe.error.StripeError as e:
                    return Response({"detail": f"Payment error: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

            cart_items.delete()

        response_data = {
            "order_id": order.order_id,
            "status": order.status,
            "total_price": str(order.total_price),
            "shipping_method": order.shipping_method.name if order.shipping_method else None
        }
        if client_secret:
            response_data["client_secret"] = client_secret

        return Response(response_data, status=status.HTTP_201_CREATED)




class OrderPreviewView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get(self, request, *args, **kwargs):
        user = request.user
        cart_items = CartItem.objects.filter(user=user)
        if not cart_items.exists():
            return Response({"detail": "Cart is empty"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate query parameters
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        coupon = serializer.validated_data.get('coupon_obj')
        shipping_method_id = request.query_params.get('shipping_method_id')

        # Calculate subtotal
        subtotal = sum(
            Decimal(str(item.variant.price if item.variant else item.product.price)) * Decimal(str(item.quantity))
            for item in cart_items
        )

        # Get shipping cost
        shipping_cost = Decimal('0.00')
        if shipping_method_id:
            try:
                shipping_method = ShippingMethod.objects.get(id=shipping_method_id)
                shipping_cost = Decimal(str(shipping_method.price))
                logger.info(f"Preview: Shipping cost {shipping_cost} for method {shipping_method.name}")
            except ShippingMethod.DoesNotExist:
                logger.warning(f"Preview: Invalid shipping_method_id {shipping_method_id}")
                shipping_cost = Decimal('0.00')

        # Apply coupon discount
        discount_amount = Decimal('0.00')
        if coupon and coupon.is_valid():
            discount_amount = (Decimal(str(coupon.discount_percentage)) / Decimal('100')) * subtotal
            discount_amount = discount_amount.quantize(Decimal('0.01'))
            logger.info(f"Preview: Discount {discount_amount} applied for coupon {coupon.code}")

        # Calculate total price
        total_price = (subtotal + shipping_cost - discount_amount).quantize(Decimal('0.01'))
        if total_price < 0:
            total_price = Decimal('0.00')

        # Return response
        response_data = {
            "subtotal": str(subtotal),
            "shipping_cost": str(shipping_cost),
            "discount_amount": str(discount_amount),
            "total_price": str(total_price),
            "coupon_valid": bool(coupon)
        }
        logger.info(f"Preview response: {response_data}")
        return Response(response_data, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAdminUser])
def generate_coupon(request):
    discount = request.data.get('discount_percentage', 10.0)
    valid_days = request.data.get('valid_days', 30)
    code_length = request.data.get('code_length', 8)

    characters = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choice(characters) for _ in range(code_length))
        if not Coupon.objects.filter(code=code).exists():
            break

    coupon = Coupon.objects.create(
        code=code,
        discount_percentage=discount,
        valid_from=timezone.now(),
        valid_until=timezone.now() + timezone.timedelta(days=valid_days),
        is_active=True,
        max_uses=request.data.get('max_uses', 100)
    )
    return Response({"code": coupon.code, "message": "Coupon generated successfully"})

@api_view(['GET'])
@permission_classes([AllowAny])
def list_active_coupons(request):
    now = timezone.now()
    coupons = Coupon.objects.filter(
        is_active=True,
        valid_from__lte=now,
        valid_until__gte=now
    ).filter(
        models.Q(max_uses__isnull=True) |  # Include if max_uses is null (unlimited)
        models.Q(max_uses__gt=models.F('uses'))  # Include if max_uses > uses
    )
    
    data = [
        {
            "code": coupon.code,
            "discount_percentage": float(coupon.discount_percentage),
            "valid_until": coupon.valid_until,
            "is_active": coupon.is_active,
            "is_valid": coupon.is_valid(),
            "valid_from": coupon.valid_from,
            "uses": coupon.uses,
            "max_uses": coupon.max_uses
        }
        for coupon in coupons
    ]
    return Response(data)

@csrf_exempt  # Important for Stripe Webhook
@api_view(['POST'])
@permission_classes([AllowAny])
def stripe_webhook(request):
    import stripe
    from django.conf import settings
    from .models import Order

    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        return Response({'error': str(e)}, status=400)
    except stripe.error.SignatureVerificationError as e:
        return Response({'error': str(e)}, status=400)

    event_type = event['type']
    data = event['data']['object']

    print(f"Webhook Event Received: {event_type}")

    if event_type == 'payment_intent.succeeded':
        payment_intent_id = data['id']
        try:
            order = Order.objects.get(payment_id=payment_intent_id)
            order.payment_status = 'paid'
            order.status = 'processing'  # Optional
            order.save()
            print(f"Order {order.order_id} Payment Success Updated")
        except Order.DoesNotExist:
            print("Order Not Found")

    elif event_type == 'payment_intent.payment_failed':
        payment_intent_id = data['id']
        try:
            order = Order.objects.get(payment_id=payment_intent_id)
            order.payment_status = 'failed'
            order.save()
            print(f"Order {order.order_id} Payment Failed Updated")
        except Order.DoesNotExist:
            print("Order Not Found")

    return Response(status=200)
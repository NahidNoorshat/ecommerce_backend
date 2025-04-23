# shipping/views.py
from rest_framework import viewsets, status  # Added status import
from rest_framework.permissions import IsAuthenticated, IsAdminUser  # Corrected permissions import
from .models import ShippingAddress, ShippingMethod
from .serializers import ShippingAddressSerializer, ShippingMethodSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

class ShippingAddressViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing shipping addresses.
    """
    queryset = ShippingAddress.objects.all()
    serializer_class = ShippingAddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Show only shipping addresses for the logged-in user
        if self.request.user.is_staff:
            return ShippingAddress.objects.all()
        return ShippingAddress.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Automatically set the user for the shipping address
        serializer.save(user=self.request.user)

class ShippingMethodViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing shipping methods.
    """
    queryset = ShippingMethod.objects.all()
    serializer_class = ShippingMethodSerializer
    permission_classes = [IsAuthenticated]

@api_view(['POST'])
@permission_classes([IsAdminUser])  # Changed to IsAdminUser directly
def mark_order_delivered(request, order_id):
    try:
        shipping_address = ShippingAddress.objects.get(order__order_id=order_id)
        shipping_address.mark_delivered()
        return Response({
            "order_id": order_id,
            "status": shipping_address.order.status,
            "payment_status": shipping_address.order.payment_status
        })
    except ShippingAddress.DoesNotExist:
        return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)
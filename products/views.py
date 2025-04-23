from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .permissions import IsCustomerOnly
from .models import Category, Product, ProductVariant, VariantAttribute, VariantAttributeValue, CartItem
from .serializers import (
    CategorySerializer,
    ProductSerializer,
    ProductVariantSerializer,
    VariantAttributeSerializer,
    VariantAttributeValueSerializer,
    CartItemSerializer
)

import logging
logger = logging.getLogger(__name__)

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser) # Explicitly allow multipart/form-data

    @action(detail=True, methods=['post'])
    def reduce_stock(self, request, pk=None):
        product = self.get_object()
        quantity = request.data.get('quantity', 0)

        try:
            product.reduce_stock(quantity)
            return Response({"message": "Stock reduced successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ProductVariantViewSet(viewsets.ModelViewSet):
    queryset = ProductVariant.objects.all()
    serializer_class = ProductVariantSerializer


class VariantAttributeViewSet(viewsets.ModelViewSet):
    queryset = VariantAttribute.objects.all()
    serializer_class = VariantAttributeSerializer


class VariantAttributeValueViewSet(viewsets.ModelViewSet):
    queryset = VariantAttributeValue.objects.all()
    serializer_class = VariantAttributeValueSerializer

class CartViewSet(viewsets.ModelViewSet):
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated, IsCustomerOnly]

    def get_queryset(self):
        logger.info(f"GET /cart/ - User: {self.request.user}, Role: {self.request.user.role}, Token: {self.request.headers.get('Authorization')}")
        if self.request.user.role != 'customer':
            logger.warning(f"Permission denied for {self.request.user}")
            raise PermissionDenied("Only customers can access the cart.")
        logger.info("Returning cart items")
        return CartItem.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        product = serializer.validated_data['product']
        variant = serializer.validated_data.get('variant')
        quantity = serializer.validated_data.get('quantity', 1)
        existing_item = CartItem.objects.filter(
            user=self.request.user, product=product, variant=variant
        ).first()
        if existing_item:
            existing_item.quantity += quantity
            existing_item.save()
            serializer.instance = existing_item
        else:
            serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save()  # No stock reduction here

    def perform_destroy(self, instance):
        instance.delete()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
    

class BulkDeleteProductsView(APIView):
    def delete(self, request):
        ids = request.data.get("ids", [])
        if not isinstance(ids, list):
            return Response({"detail": "Invalid format. 'ids' should be a list."}, status=400)

        deleted, _ = Product.objects.filter(id__in=ids).delete()
        return Response({"deleted": deleted}, status=status.HTTP_200_OK)
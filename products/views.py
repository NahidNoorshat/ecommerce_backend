from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .permissions import IsCustomerOnly
from rest_framework import filters
import pandas as pd
import json
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from .pagination import CustomProductPagination

from .models import Category, Product, ProductVariant, VariantAttribute, VariantAttributeValue, CartItem, ProductImage
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
    pagination_class = CustomProductPagination 
    permission_classes = [AllowAny]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'category__name']
    ordering_fields = ['price', 'created_at']
    ordering = ['-created_at']
    lookup_field = 'slug'  # Default is slug, but we'll support ID too

    def get_object(self):
        """
        Override to support both slug and ID lookups.
        Tries slug first, falls back to ID if slug fails and pk is numeric.
        """
        try:
            return super().get_object()  # Default slug lookup
        except Http404:
            # Check if the lookup value is numeric (ID)
            lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
            pk = self.kwargs.get(lookup_url_kwarg)
            
            if pk and pk.isdigit():
                queryset = self.filter_queryset(self.get_queryset())
                try:
                    obj = queryset.get(id=pk)
                    self.check_object_permissions(self.request, obj)
                    return obj
                except Product.DoesNotExist:
                    raise Http404(f"No Product matches the given query (ID: {pk}).")
            raise  # Re-raise if not numeric or still not found

    def get_queryset(self):
        queryset = Product.objects.all()
        category_id = self.request.query_params.get('category')
        search_query = self.request.query_params.get('search')
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        on_sale = self.request.query_params.get('on_sale')
        slug = self.request.query_params.get('slug')

        if slug:
            logger.info(f"Filtering by slug: {slug}")
            queryset = queryset.filter(slug=slug)
            count = queryset.count()
            if count == 0:
                logger.warning(f"No product found for slug: {slug}")
                raise Http404(f"No product found for slug: {slug}")
            if count > 1:
                logger.warning(f"Multiple products found for slug: {slug}, count: {count}")
                slugs = list(queryset.values_list('slug', flat=True))
                logger.warning(f"Found slugs: {slugs}")

        if category_id:
            try:
                category = Category.objects.get(id=category_id)
                category_ids = self.get_category_and_subcategories(category)
                queryset = queryset.filter(category__id__in=category_ids)
            except Category.DoesNotExist:
                logger.warning(f"Category {category_id} not found")
                return Product.objects.none()

        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(category__name__icontains=search_query)
            )

        if min_price:
            queryset = queryset.filter(price__gte=min_price)

        if max_price:
            queryset = queryset.filter(price__lte=max_price)

        if on_sale and on_sale.lower() == 'true':
            queryset = queryset.filter(discount__gt=0)

        logger.debug(f"Queryset for slug {slug}: {queryset.values('id', 'slug', 'name')}")
        return queryset

    def get_category_and_subcategories(self, category):
        ids = [category.id]
        for subcat in category.subcategories.all():
            ids += self.get_category_and_subcategories(subcat)
        return ids

    # Keep this for explicit ID-based lookup (via /api/products/products/id/100/)
    @action(detail=True, methods=['get'], url_path='id/(?P<id>[^/.]+)', url_name='by-id')
    def retrieve_by_id(self, request, id=None):
        try:
            product = Product.objects.get(id=id)
            serializer = self.get_serializer(product)
            logger.info(f"Retrieved product by ID: {id}")
            return Response(serializer.data)
        except Product.DoesNotExist:
            logger.warning(f"No product found for ID: {id}")
            raise Http404(f"No product found for ID: {id}")

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
        serializer.save()

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

class BulkProductUploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request, *args, **kwargs):
        file = request.FILES.get('file')

        if not file:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            elif file.name.endswith('.xlsx'):
                df = pd.read_excel(file)
            else:
                return Response({"error": "Only CSV or Excel (.xlsx) files are supported"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Failed to read file: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        success_count = 0
        error_list = []

        with transaction.atomic():
            for idx, row in df.iterrows():
                try:
                    category_name = str(row.get('category')).strip()
                    if not category_name:
                        raise ValueError("Category name is missing")

                    category, _ = Category.objects.get_or_create(name=category_name)
                    has_variants = str(row.get('has_variants')).strip().lower() == 'true'

                    product_data = {
                        'name': str(row.get('name')).strip(),
                        'description': str(row.get('description', '')).strip(),
                        'price': None if has_variants else row.get('price'),
                        'stock': None if has_variants else int(row.get('stock')) if not pd.isna(row.get('stock')) else None,
                        'discount': float(row.get('discount')) if not pd.isna(row.get('discount')) else 0,
                        'unit': row.get('unit', 'PCS'),
                        'has_variants': has_variants,
                        'category': category,
                    }

                    product = Product.objects.create(**product_data)

                    ProductImage.objects.create(
                        product=product,
                        image='product_images/no-image.jpg',
                        is_main=True,
                        alt_text=product.name
                    )

                    if has_variants:
                        variants_json = row.get('variants')
                        default_variant = None
                        min_price = float('inf')

                        if variants_json:
                            try:
                                variants_data = json.loads(variants_json)
                                for variant_data in variants_data:
                                    attributes = variant_data.get('attributes', [])
                                    stock = variant_data.get('stock')
                                    price = float(variant_data.get('price'))

                                    variant = ProductVariant.objects.create(
                                        product=product,
                                        stock=stock,
                                        price=price
                                    )

                                    attribute_objs = []
                                    for attr_value_str in attributes:
                                        attr_name, attr_value = attr_value_str.split(':', 1)
                                        attr_name = attr_name.strip()
                                        attr_value = attr_value.strip()

                                        attribute_obj, _ = VariantAttribute.objects.get_or_create(name=attr_name)
                                        attr_obj, _ = VariantAttributeValue.objects.get_or_create(
                                            attribute=attribute_obj,
                                            value=attr_value
                                        )
                                        attribute_objs.append(attr_obj)

                                    variant.attributes.set(attribute_objs)

                                    if price < min_price:
                                        min_price = price
                                        default_variant = variant

                                if default_variant:
                                    product.default_variant = default_variant
                                    product.price = default_variant.price
                                    product.save(update_fields=["default_variant", "price"])

                            except json.JSONDecodeError:
                                raise ValueError(f"Invalid JSON format in 'variants' field (row {idx+2})")

                    success_count += 1

                except Exception as e:
                    error_list.append({
                        "row_number": idx + 2,
                        "error": str(e)
                    })

        return Response({
            "successfully_created": success_count,
            "errors": error_list
        }, status=status.HTTP_201_CREATED)
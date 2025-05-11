from rest_framework import serializers
import uuid
import json
from .models import Category, Product, ProductVariant, VariantAttribute, VariantAttributeValue, CartItem, ProductImage
import logging

logger = logging.getLogger(__name__)

def generate_sku(category):
    return f"{category.name[:3].upper()}-{uuid.uuid4().hex[:4]}"

class CategorySerializer(serializers.ModelSerializer):
    parent = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'parent']

    def get_parent(self, obj):
        if obj.parent:
            return CategorySerializer(obj.parent, context=self.context).data
        return None

class VariantAttributeValueSerializer(serializers.ModelSerializer):
    attribute = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = VariantAttributeValue
        fields = ['id', 'attribute', 'value']

class VariantAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VariantAttribute
        fields = '__all__'

class ProductVariantSerializer(serializers.ModelSerializer):
    attributes = VariantAttributeValueSerializer(many=True, read_only=True)
    attributes_ids = serializers.PrimaryKeyRelatedField(
        queryset=VariantAttributeValue.objects.all(),
        many=True,
        source='attributes',
        write_only=True
    )
    image = serializers.ImageField(required=False, allow_empty_file=False)
    final_price = serializers.SerializerMethodField()
    original_price = serializers.SerializerMethodField()
    variant_name = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = ['id', 'attributes', 'attributes_ids', 'stock', 'price', 'original_price', 'final_price', 'image', 'sku', 'variant_name']

    def get_final_price(self, obj):
        return obj.product.get_variant_final_price(obj)

    def get_original_price(self, obj):
        return obj.product.get_variant_original_price(obj)

    def get_variant_name(self, obj):
        return " ".join(attr.value for attr in obj.attributes.all())
    

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'is_main']


class ProductSerializer(serializers.ModelSerializer):
    final_price = serializers.SerializerMethodField()
    original_price = serializers.SerializerMethodField()
    default_variant = ProductVariantSerializer(read_only=True)
    default_variant_id = serializers.PrimaryKeyRelatedField(    # ✅ add this line
        queryset=ProductVariant.objects.all(),
        source='default_variant',
        write_only=True,
        required=False
    )
    variants = ProductVariantSerializer(many=True, required=False)
    main_image = serializers.SerializerMethodField()
    gallery_images = serializers.SerializerMethodField()
    images = ProductImageSerializer(many=True, read_only=True)  # All images (optional)

    # image = serializers.ImageField(required=False, allow_empty_file=False)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    category_data = CategorySerializer(source='category', read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    certificate_file = serializers.FileField(required=False, allow_null=True)
    certificate_description = serializers.CharField(required=False, allow_blank=True)
    is_verified = serializers.ReadOnlyField()
    class Meta:
        model = Product
        fields = [
        'id', 'name', 'slug', 'description', 'price', 'stock', 'discount', 'category', 'category_data',
        'unit', 'custom_unit', 'label', 'status', 'has_variants', 'default_variant', 'variants','default_variant_id',
        'sku', 'created_at', 'updated_at', 'final_price', 'original_price',
        'main_image', 'gallery_images', 'images', 'average_rating','certificate_file', 'certificate_description', 'is_verified',  # ✅ new fields
        ]   
        extra_kwargs = {
            'category_data': {'source': 'category'}
        }

    def get_main_image(self, obj):
        main_img = obj.images.filter(is_main=True).first()
        return ProductImageSerializer(main_img, context=self.context).data if main_img else None

    def get_gallery_images(self, obj):
        gallery_imgs = obj.images.filter(is_main=False)
        return ProductImageSerializer(gallery_imgs, many=True, context=self.context).data


    def get_final_price(self, obj):
        final_price = obj.get_final_price()
        return final_price if final_price is not None else "Price not available"

    def get_original_price(self, obj):
        original_price = obj.get_original_price()
        return original_price if original_price is not None else "Price not available"

    def to_internal_value(self, data):
        logger.debug(f"Raw data received: {data}")
        mutable_data = data.copy() if hasattr(data, 'copy') else data

        processed_data = {}
        for key, value in mutable_data.items():
            if key.startswith('variants['):
                continue
            if isinstance(value, list) and len(value) == 1 and not hasattr(value[0], 'file'):
                processed_data[key] = value[0]
            else:
                processed_data[key] = value

        if 'data' in mutable_data:
            try:
                json_data = json.loads(mutable_data['data'])
                if 'variants' in json_data:
                    processed_data['variants'] = []
                    for i, variant in enumerate(json_data['variants']):
                        variant_data = variant.copy()
                        if 'attributes' in variant_data:
                            variant_data['attributes_ids'] = variant_data.pop('attributes')
                        image_key = f'variants[{i}][image]'
                        if image_key in mutable_data:
                            variant_data['image'] = mutable_data[image_key]
                            logger.debug(f"Variant {i} image: {variant_data['image']}")
                        processed_data['variants'].append(variant_data)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse 'data': {str(e)}")
                raise serializers.ValidationError({"data": "Invalid JSON format"})

        logger.debug(f"Processed data: {processed_data}")
        try:
            internal_value = super().to_internal_value(processed_data)
            logger.debug(f"Internal value: {internal_value}")
            return internal_value
        except serializers.ValidationError as e:
            logger.error(f"Validation error: {e.detail}")
            raise

    def create(self, validated_data):
        logger.debug(f"Creating with validated_data: {validated_data}")
        request = self.context.get('request')
        variants_data = validated_data.pop('variants', [])
        has_variants = validated_data.get('has_variants', False)

        # Handle has_variants
        if has_variants and variants_data:
            validated_data['price'] = None
            validated_data['stock'] = None

        # Handle SKU
        category = validated_data['category']
        if 'sku' not in validated_data or not validated_data['sku']:
            validated_data['sku'] = generate_sku(category)

        # Create Product
        product = Product.objects.create(**validated_data)

        # Handle variants
        for variant_data in variants_data:
            variant_image = variant_data.pop('image', None)
            attributes = variant_data.pop('attributes', [])
            variant = ProductVariant.objects.create(product=product, **variant_data)
            if variant_image:
                variant.image = variant_image
                variant.save(update_fields=['image'])
            variant.attributes.set(attributes)

        # Handle uploaded product images
        uploaded_images = request.FILES.getlist('uploaded_images')
        main_image_index = int(request.data.get('main_image_index', 0))

        for idx, img in enumerate(uploaded_images):
            ProductImage.objects.create(
                product=product,
                image=img,
                is_main=(idx == main_image_index),  # ✅ Set true for selected main image
                alt_text=product.name
            )

        logger.debug(f"Product created with ID {product.id}")
        # ✅ Assign default variant after creating all variants
        if product.has_variants and not product.default_variant:
            cheapest = product.variants.order_by("price").first()
            if cheapest:
                product.default_variant = cheapest
                product.save(update_fields=["default_variant"])

        return product



    def update(self, instance, validated_data):
        logger.debug(f"Updating with validated_data: {validated_data}")
        request = self.context.get('request')
        variants_data = validated_data.pop('variants', None)

        # Update basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Update cert fields (NEW)
        certificate_file = request.FILES.get('certificate_file')
        if certificate_file:
            instance.certificate_file = certificate_file

        certificate_description = request.data.get('certificate_description')
        if certificate_description is not None:
            instance.certificate_description = certificate_description

        instance.save()

        # Handle variants update (existing logic)
        if variants_data is not None:
            existing_variants = {variant.id: variant for variant in instance.variants.all()}
            updated_variant_ids = set()

            for variant_data in variants_data:
                variant_id = variant_data.get('id')
                variant_image = variant_data.pop('image', None)
                attributes = variant_data.pop('attributes', [])

                if variant_id and variant_id in existing_variants:
                    variant = existing_variants[variant_id]
                    for attr, value in variant_data.items():
                        setattr(variant, attr, value)
                    if variant_image:
                        variant.image = variant_image
                    variant.save()
                    variant.attributes.set(attributes)
                    updated_variant_ids.add(variant_id)
                else:
                    variant = ProductVariant.objects.create(product=instance, **variant_data)
                    if variant_image:
                        variant.image = variant_image
                        variant.save(update_fields=['image'])
                    variant.attributes.set(attributes)

            for variant_id, variant in existing_variants.items():
                if variant_id not in updated_variant_ids:
                    variant.delete()

        # 🔥 New Logic: Update uploaded images (optional)
        uploaded_images = request.FILES.getlist('uploaded_images')
        main_image_index = request.data.get('main_image_index')

        if uploaded_images:
            # If new images uploaded, delete previous images
            instance.images.all().delete()

            # Save new images
            main_index = int(main_image_index) if main_image_index is not None else 0
            for idx, img in enumerate(uploaded_images):
                ProductImage.objects.create(
                    product=instance,
                    image=img,
                    is_main=(idx == main_index),
                    alt_text=instance.name
                )

        logger.debug(f"Updated instance: {instance}")
        
        if instance.has_variants and not instance.default_variant:
            cheapest = instance.variants.order_by("price").first()
            if cheapest:
                instance.default_variant = cheapest
                instance.save(update_fields=["default_variant"])


        return instance



    def to_representation(self, instance):
        representation = super().to_representation(instance)
        category_data = representation.pop('category_data', None)
        if category_data:
            representation['category'] = category_data
        else:
            representation['category'] = None
        return representation

class CartItemSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )
    variant_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.all(), source='variant', write_only=True, required=False
    )
    user = serializers.StringRelatedField(read_only=True)
    product = ProductSerializer(read_only=True)  # Nested product details
    variant = ProductVariantSerializer(read_only=True)  # Nested variant details

    class Meta:
        model = CartItem
        fields = ['id', 'user', 'product', 'product_id', 'variant', 'variant_id', 'quantity']
        read_only_fields = ['id', 'user']

    def validate(self, data):
        if self.instance and 'product' not in data:
            product = self.instance.product
        else:
            product = data.get('product')
        if not product and not self.instance:
            raise serializers.ValidationError("Product is required.")
        quantity = data.get('quantity', self.instance.quantity if self.instance else 1)
        variant = data.get('variant', self.instance.variant if self.instance else None)
        available_stock = variant.stock if variant else product.stock
        if quantity > available_stock:
            raise serializers.ValidationError(f"Quantity {quantity} exceeds stock {available_stock}.")
        data['product'] = product
        return data
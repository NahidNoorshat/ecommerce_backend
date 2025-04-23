from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.conf import settings

import uuid
from decimal import Decimal

UNIT_CHOICES = [
    ('PCS', 'Pieces'),
    ('KG', 'Kilogram'),
    ('L', 'Liter'),
    ('M', 'Meter'),
    ('G', 'Gram'),
    ('BOX', 'Box'),
    ('OTHER', 'Other'),
]


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='subcategories'
    )

    def validate_parent(self):
        if self.parent:
            if self.parent == self:
                raise ValidationError("A category cannot be its own parent.")
            ancestor = self.parent
            while ancestor is not None:
                if ancestor == self:
                    raise ValidationError("Circular category hierarchy detected!")
                ancestor = ancestor.parent

    def save(self, *args, **kwargs):
        self.validate_parent()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('HOT', 'Hot'),
        ('SALE', 'On Sale'),
        ('OUT_OF_STOCK', 'Out of Stock'),
    ]

    name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(unique=True, blank=True, null=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    stock = models.IntegerField(validators=[MinValueValidator(0)], null=True, blank=True)
    category = models.ForeignKey('Category', on_delete=models.PROTECT, db_index=True)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='PCS')
    custom_unit = models.CharField(
        max_length=50, blank=True, null=True, help_text="Enter custom unit if 'Other' is selected"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NEW')
    label = models.CharField(max_length=50, blank=True, null=True)
    image = models.ImageField(upload_to='product_images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    has_variants = models.BooleanField(default=False, help_text="Does this product have variants?")
    sku = models.CharField(max_length=100, unique=True, blank=True, null=True, help_text="Stock Keeping Unit (SKU)")

    def clean(self):
        if not self.has_variants:
            if self.price is None:
                raise ValidationError({'price': "Price is required for products without variants."})
            if self.stock is None:
                raise ValidationError({'stock': "Stock is required for products without variants."})
        if self.unit == 'OTHER' and not self.custom_unit:
            raise ValidationError({'custom_unit': "Please specify a unit if 'Other' is selected."})
        if self.unit != 'OTHER' and self.custom_unit:
            self.custom_unit = None

    def save(self, *args, **kwargs):
            # Generate slug if not set
            if not self.slug:
                base_slug = slugify(self.name)
                unique_slug = base_slug
                counter = 1
                while Product.objects.filter(slug=unique_slug).exists():
                    unique_slug = f"{base_slug}-{counter}"
                    counter += 1
                self.slug = unique_slug

            # Generate SKU if not set
            if not self.sku:
                cat_prefix = self.category.name[:3].upper()
                if self.id:
                    self.sku = f"{cat_prefix}-{self.id:04d}"
                else:
                    # Use a temporary unique SKU to avoid conflicts
                    temp_suffix = uuid.uuid4().hex[:8]  # e.g., "CLO-1a2b3c4d"
                    self.sku = f"{cat_prefix}-{temp_suffix}"
                    super().save(*args, **kwargs)
                    # Update SKU with id after save
                    self.sku = f"{cat_prefix}-{self.id:04d}"
                    super().save(update_fields=['sku'])
            else:
                super().save(*args, **kwargs)

    def update_stock(self):
        if self.has_variants:
            total_stock = self.variants.aggregate(total=models.Sum('stock'))['total'] or 0
            self.stock = total_stock
            self.save(update_fields=['stock'])

    def reduce_stock(self, quantity, variant=None):
        if self.has_variants:
            if not variant:
                raise ValidationError("A variant must be specified for products with variants.")
            variant.stock -= quantity
            if variant.stock < 0:
                raise ValidationError(f"Insufficient stock for {variant}")
            variant.save()
        else:
            self.stock -= quantity
            if self.stock < 0:
                raise ValidationError(f"Insufficient stock for {self}")
            self.save()

    def get_final_price(self):
            # Price is the final price after discount
            return self.price if self.price is not None else None

    def get_original_price(self):
        # Reverse-calculate original price based on final price and discount
        if self.price is not None and self.discount > 0:
            return self.price / (1 - self.discount / Decimal(100))
        return self.price if self.price is not None else None

    def get_variant_final_price(self, variant):
        return variant.price if variant else None

    def get_variant_original_price(self, variant):
        if variant and self.discount > 0:
            return variant.price / (1 - self.discount / Decimal(100))
        return variant.price if variant else None

    def __str__(self):
        return self.name or "Unnamed Product"

    class Meta:
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['category', 'status']),
        ]


class VariantAttribute(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name


class VariantAttributeValue(models.Model):
    attribute = models.ForeignKey(VariantAttribute, on_delete=models.CASCADE)
    value = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, related_name='variants', on_delete=models.CASCADE)
    attributes = models.ManyToManyField(VariantAttributeValue, related_name='variants')
    stock = models.IntegerField(validators=[MinValueValidator(0)])
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Final price
    image = models.ImageField(upload_to='product_variants/', blank=True, null=True)
    sku = models.CharField(max_length=100, unique=True, blank=True, null=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.sku and self.pk:
            attrs_short = "".join(attr.value[:2] for attr in self.attributes.all()).upper()
            base_sku = f"{self.product.sku}-{attrs_short}"
            unique_sku = base_sku
            counter = 1
            while ProductVariant.objects.filter(sku=unique_sku).exclude(pk=self.pk).exists():
                unique_sku = f"{base_sku}-{counter}"
                counter += 1
            self.sku = unique_sku
            super().save(update_fields=['sku'])

    def __str__(self):
        return f"{self.product.name} - Variant {self.id}"

    class Meta:
        indexes = [models.Index(fields=['product'])]
        unique_together = ('product', 'sku')


@receiver(post_save, sender=ProductVariant)
def update_product_stock_on_variant_save(sender, instance, **kwargs):
    if instance.product.has_variants:
        instance.product.update_stock()


@receiver(pre_delete, sender=ProductVariant)
def update_product_stock_on_variant_delete(sender, instance, **kwargs):
    if instance.product.has_variants:
        instance.product.update_stock()



class CartItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        limit_choices_to={'role': 'customer'}
    )
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    variant = models.ForeignKey(
        'ProductVariant', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)  # New: Track when added

    def clean(self):
        if self.product.has_variants and not self.variant:
            raise ValidationError("A variant must be specified for products with variants.")
        if not self.product.has_variants and self.variant:
            raise ValidationError("Variants cannot be specified for products without variants.")
        # Optional stock check (redundant with serializer, but adds model-level safety)
        available_stock = self.variant.stock if self.product.has_variants else self.product.stock
        if self.quantity > available_stock:
            raise ValidationError(f"Only {available_stock} items available in stock.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def reduce_stock(self):
        if self.product.has_variants:
            self.product.reduce_stock(self.quantity, self.variant)
        else:
            self.product.reduce_stock(self.quantity)

    def get_total_price(self):
        if self.product.has_variants:
            return self.variant.price * self.quantity
        return self.product.get_final_price() * self.quantity

    class Meta:
        unique_together = (
            ('user', 'product', 'variant'),
        )

    def __str__(self):
        return f"{self.product.name} ({self.variant or 'No Variant'}) - Qty: {self.quantity}"
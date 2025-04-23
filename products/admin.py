from django.contrib import admin
from .models import Category, Product, VariantAttribute, VariantAttributeValue, ProductVariant, CartItem

# Admin for Category
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent')
    list_filter = ('parent',)
    search_fields = ('name',)

# Inline for ProductVariant (to edit variants within Product admin)
class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1  # Number of empty variant forms to show by default
    fields = ('sku', 'price', 'stock', 'image', 'attributes')
    filter_horizontal = ('attributes',)  # Makes ManyToMany field easier to manage

# Admin for Product
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'stock', 'has_variants', 'status', 'sku')
    list_filter = ('category', 'status', 'has_variants')
    search_fields = ('name', 'sku')
    inlines = [ProductVariantInline]  # Allows adding/editing variants within Product
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'description', 'category', 'status', 'label', 'image', 'sku')
        }),
        ('Pricing and Stock', {
            'fields': ('price', 'discount', 'stock', 'has_variants'),
            'description': 'Price and stock are required only if the product has no variants.'
        }),
        ('Units', {
            'fields': ('unit', 'custom_unit'),
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('created_at', 'updated_at')

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj and obj.has_variants:
            # Optionally make price and stock readonly or hidden when has_variants is True
            form.base_fields['price'].required = False
            form.base_fields['stock'].required = False
        return form

# Admin for VariantAttribute
@admin.register(VariantAttribute)
class VariantAttributeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

# Admin for VariantAttributeValue
@admin.register(VariantAttributeValue)
class VariantAttributeValueAdmin(admin.ModelAdmin):
    list_display = ('attribute', 'value')
    list_filter = ('attribute',)
    search_fields = ('value',)

# Admin for ProductVariant (optional standalone admin page)
@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('product', 'sku', 'price', 'stock')
    list_filter = ('product',)
    search_fields = ('sku', 'product__name')
    filter_horizontal = ('attributes',)



@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'variant', 'quantity', 'added_at', 'get_total_price')
    list_filter = ('user', 'added_at')
    search_fields = ('user__username', 'product__name')
    readonly_fields = ('added_at', 'get_total_price')
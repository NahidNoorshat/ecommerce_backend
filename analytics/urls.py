from rest_framework.routers import DefaultRouter
from .views import (
    ProductAnalyticsViewSet,
    UserAnalyticsViewSet,
    GeneralAnalyticsViewSet,
    SalesTrendAPIView,  # ✅ import this
    CategorySalesBarChartAPIView,
    OrderStatusPieChartAPIView,
    TrendsAPIView,
)
from django.urls import path

# Register ViewSets with router
router = DefaultRouter()
router.register(r'product', ProductAnalyticsViewSet, basename='product-analytics')
router.register(r'user', UserAnalyticsViewSet, basename='user-analytics')
router.register(r'general', GeneralAnalyticsViewSet, basename='general-analytics')

# Add APIView manually
urlpatterns = router.urls + [
    path('sales-trend/', SalesTrendAPIView.as_view(), name='sales-trend'),  # ✅ added
    path("category-sales-bar/", CategorySalesBarChartAPIView.as_view(), name="category-sales-bar"),
    path("order-status-pie/", OrderStatusPieChartAPIView.as_view(), name="order-status-pie"),
    path("trends/", TrendsAPIView.as_view(), name="trend-api"),
]

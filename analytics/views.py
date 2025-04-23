from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, Count
from .models import ProductAnalytics, UserAnalytics
from users.models import CustomUser
from .serializers import ProductAnalyticsSerializer, UserAnalyticsSerializer
from orders.models import Order, OrderItem
from django.db.models import F, Sum, ExpressionWrapper, FloatField
from analytics.permissions import IsAdminOrStaff  # ✅ custom role-based permission
from django.utils.timezone import now
from datetime import timedelta


class ProductAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing product analytics.
    Access restricted to role=admin or is_staff.
    """
    queryset = ProductAnalytics.objects.all()
    serializer_class = ProductAnalyticsSerializer
    permission_classes = [IsAdminOrStaff]


class UserAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing user analytics.
    Access restricted to role=admin or is_staff.
    """
    queryset = UserAnalytics.objects.all()
    serializer_class = UserAnalyticsSerializer
    permission_classes = [IsAdminOrStaff]


class GeneralAnalyticsViewSet(viewsets.ViewSet):
    """
    API endpoint for general summary analytics (orders, revenue, users).
    Access restricted to role=admin or is_staff.
    """
    permission_classes = [IsAdminOrStaff]

    def list(self, request):
        total_orders = Order.objects.count()
        total_revenue = Order.objects.aggregate(total_revenue=Sum('total_price'))['total_revenue'] or 0
        total_users = CustomUser.objects.filter(role="customer").count()

        data = {
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "total_users": total_users,
        }
        return Response(data)


class SalesTrendAPIView(APIView):
    permission_classes = [IsAdminOrStaff]

    def get(self, request):
        filter_by = request.GET.get("filter", "weekly")  # daily, weekly, monthly
        today = now().date()

        if filter_by == "daily":
            start_date = today
        elif filter_by == "monthly":
            start_date = today - timedelta(days=30)
        else:  # weekly (default)
            start_date = today - timedelta(days=6)

        days_range = (today - start_date).days + 1
        sales_data = []

        for i in range(days_range):
            day = start_date + timedelta(days=i)
            orders = Order.objects.filter(created_at__date=day)
            total_sales = orders.aggregate(sales=Sum("total_price"))["sales"] or 0
            total_orders = orders.aggregate(count=Count("id"))["count"] or 0

            sales_data.append({
                "date": str(day),
                "sales": float(total_sales),
                "orders": total_orders
            })

        return Response({"sales_data": sales_data})
    

class CategorySalesBarChartAPIView(APIView):
    permission_classes = [IsAdminOrStaff]

    def get(self, request):
        range_filter = request.GET.get("range", "all")
        start_datetime = None

        if range_filter == "weekly":
            start_datetime = now() - timedelta(days=7)
        elif range_filter == "monthly":
            start_datetime = now() - timedelta(days=30)

        order_items = OrderItem.objects.select_related("product__category")

        if start_datetime:
            order_items = order_items.filter(order__created_at__gte=start_datetime)

        # Calculate line total
        order_items = order_items.annotate(
            line_total=ExpressionWrapper(
                F("price_at_purchase") * F("quantity"),
                output_field=FloatField()
            )
        )

        # Aggregate sales by top-level category
        category_map = {}
        for item in order_items:
            category = item.product.category
            cat_name = category.name if category else "Uncategorized"
            category_map[cat_name] = category_map.get(cat_name, 0) + item.line_total

        # Build, sort, and slice top 5
        result = sorted(
            [{"category": k, "sales": round(v, 2)} for k, v in category_map.items()],
            key=lambda x: x["sales"],
            reverse=True
        )[:5]  # 🔥 TOP 5 ONLY

        return Response({"category_sales": result})
    

class OrderStatusPieChartAPIView(APIView):
    permission_classes = [IsAdminOrStaff]

    def get(self, request):
        range_filter = request.GET.get("range", "all")
        start_datetime = None

        if range_filter == "weekly":
            start_datetime = now() - timedelta(days=7)
        elif range_filter == "monthly":
            start_datetime = now() - timedelta(days=30)

        orders = Order.objects.all()

        if start_datetime:
            orders = orders.filter(created_at__gte=start_datetime)

        # Group by status
        status_counts = (
            orders.values("status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        result = [
            {"status": item["status"].capitalize(), "value": item["count"]}
            for item in status_counts
        ]

        return Response({"status_data": result})
    

class TrendsAPIView(APIView):
    def get(self, request):
        today = now().date()
        days = [today - timedelta(days=i) for i in range(6, -1, -1)]

        revenue_trend = []
        order_trend = []
        user_trend = []

        for day in days:
            orders_on_day = Order.objects.filter(created_at__date=day)
            revenue = orders_on_day.aggregate(sum=Sum("total_price"))["sum"] or 0
            order_count = orders_on_day.count()
            user_count = CustomUser.objects.filter(role="customer", date_joined__date=day).count()

            revenue_trend.append(revenue)
            order_trend.append(order_count)
            user_trend.append(user_count)

        return Response({
            "revenue_trend": revenue_trend,
            "order_trend": order_trend,
            "user_trend": user_trend,
        })
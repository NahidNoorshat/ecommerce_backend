# Generated by Django 5.1.4 on 2025-04-25 10:07

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("orders", "0011_order_shipping_method"),
    ]

    operations = [
        migrations.CreateModel(
            name="Banner",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("subtitle", models.TextField(blank=True, null=True)),
                (
                    "discount_text",
                    models.CharField(blank=True, max_length=50, null=True),
                ),
                ("image", models.ImageField(upload_to="banners/")),
                ("is_active", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "coupon",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="orders.coupon",
                    ),
                ),
            ],
            options={
                "ordering": ["order"],
            },
        ),
    ]

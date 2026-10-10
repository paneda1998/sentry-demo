from django.db import models

class Product(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)

class Coupon(models.Model):
    code = models.CharField(max_length=30, unique=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2)

class Order(models.Model):
    reference = models.CharField(max_length=40, unique=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    demo_user = models.CharField(max_length=30)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

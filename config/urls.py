from django.urls import path
from shop import views

urlpatterns = [
    path('', views.index, name='checkout-page'),
    path('api/checkout/', views.checkout, name='checkout'),
    path('api/health/', views.health, name='health'),
]
handler500 = 'shop.views.server_error'

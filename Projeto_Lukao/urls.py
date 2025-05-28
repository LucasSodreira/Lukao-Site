"""
URL configuration for Projeto_Lukao project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from core.views import *
from user.views import *
from dashboard.views import *
from checkout.views import *


urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('produto/<int:pk>/', ItemView.as_view(), name='item-view'),
    path('add-to-cart/<int:pk>/', AddToCartView.as_view(), name='add-to-cart'),
    path('produtos/', Product_Listing.as_view(), name='product-listing'),
    path('carrinho/', CartView.as_view(), name='carrinho'),
    path('carrinho/aumentar/<str:chave>/', AumentarItemView.as_view(), name='aumentar-item'),
    path('carrinho/diminuir/<str:chave>/', DiminuirItemView.as_view(), name='diminuir-item'),
    path('carrinho/remover/<str:chave>/', RemoverItemView.as_view(), name='remover-item'),
    path('salvar-cep/', salvar_cep_usuario, name='salvar_cep_usuario'),
    path('calcular-frete/', calcular_frete, name='calcular_frete'),    
    path('api/cart/count/', cart_count, name='cart_count'),
    
    path('checkout/', include('checkout.urls', namespace='checkout')),
    path('user/', include('user.urls', namespace='user')),

    # path('dashboard/', include('dashboard.urls', namespace='dashboard')),
    
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
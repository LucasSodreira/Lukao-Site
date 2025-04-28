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
from django.urls import path
from core.views import IndexView, ItemView, ReviewCart, AddressView, LoginView, RegisterView, ThanksView, AddToCartView, CartView, RemoverItemCarrinho

urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('produto/<int:pk>/', ItemView.as_view(), name='item-view'),
    path('add-to-cart/<int:pk>/', AddToCartView.as_view(), name='add-to-cart'),
    path('carrinho/', CartView.as_view(), name='carrinho'),
    path('carrinho/remover/', RemoverItemCarrinho.as_view(), name='remover_item_carrinho'),
    path('revisar-carrinho/', ReviewCart.as_view(), name='review-cart'),
    path('endereco/', AddressView.as_view(), name='address'),
    path('login/', LoginView.as_view(), name='login'),
    path('registrar/', RegisterView.as_view(), name='register'),
    path('obrigado/', ThanksView.as_view(), name='thanks'),
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
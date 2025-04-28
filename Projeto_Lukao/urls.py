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
from django.urls import path
from core.views import IndexView, Item_View, Cart, ReviewCart, AddressView, LoginView, RegisterView, ThanksView

urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('item/', Item_View.as_view(), name='item_view'),
    path('carrinho/', Cart.as_view(), name='carrinho'),
    path('review_cart/', ReviewCart.as_view(), name='review_cart'),
    path('address/', AddressView.as_view(), name='address'),
    path('login/', LoginView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('thanks/', ThanksView.as_view(), name='thanks'),
    path('admin/', admin.site.urls),
]

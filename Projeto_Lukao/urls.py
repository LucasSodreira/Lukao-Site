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
from core.views import *

urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('produto/<int:pk>/', ItemView.as_view(), name='item-view'),
    path('add-to-cart/<int:pk>/', AddToCartView.as_view(), name='add-to-cart'),
    path('carrinho/', CartView.as_view(), name='carrinho'),
    path('carrinho/aumentar/<str:chave>/', AumentarItemView.as_view(), name='aumentar-item'),
    path('carrinho/diminuir/<str:chave>/', DiminuirItemView.as_view(), name='diminuir-item'),
    path('carrinho/remover/<str:chave>/', RemoverItemView.as_view(), name='remover-item'),
    path('revisar-carrinho/', ReviewCart.as_view(), name='review-cart'),
    path('endereco/', EnderecoCreateView.as_view(), name='endereco'),  
    path('endereco/<int:pk>/editar/', EnderecoEditView.as_view(), name='editar-endereco'),
    path('endereco/<int:pk>/excluir/', ExcluirEnderecoView.as_view(), name='excluir-endereco'),
    path('endereco/<int:pk>/principal/', DefinirEnderecoPrincipal.as_view(), name='definir-endereco-principal'),
    path('enderecoview/', AddressSelection.as_view(), name='endereco-view'),
    
    path('envio/', ShipmentMethodView.as_view(), name='shipment-method'),
    
    path('login/', LoginView.as_view(), name='login'),
    path('registrar/', RegisterView.as_view(), name='register'),
    path('obrigado/', ThanksView.as_view(), name='thanks'),
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
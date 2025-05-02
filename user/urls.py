from django.urls import path
from django.conf import settings
from django.contrib.auth.views import LogoutView
from user.views import *

app_name = 'user'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page=settings.LOGOUT_REDIRECT_URL), name='logout'),
    path('registrar/', RegisterView.as_view(), name='register'),
    path('order-detail/', OrderDetailView.as_view(), name='order_detail'),
    path('purchase-history/', PurchaseHistoryView.as_view(), name='purchase_history'),
    
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/edit/', ProfileUpdateView.as_view(), name='edit_profile'),
    
    path('address-management/', AddresManagementView.as_view(), name='address_management'),
    path('endereco/', EnderecoCreateView.as_view(), name='endereco'),
    path('endereco/<int:pk>/editar/', EnderecoEditView.as_view(), name='editar-endereco'),
    path('endereco/<int:pk>/excluir/', ExcluirEnderecoView.as_view(), name='excluir-endereco'),
    path('endereco/<int:pk>/principal/', DefinirEnderecoPrincipal.as_view(), name='definir-endereco-principal'),
    
]

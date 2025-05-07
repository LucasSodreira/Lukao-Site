from django.urls import path
from django.conf import settings
from django.contrib.auth.views import LogoutView
from django.contrib.auth import views as auth_views
from user.views import *
from . import views
from .views import salvar_checkout_rapido

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
    path('notificacao/<int:notificacao_id>/lida/', views.marcar_notificacao_lida, name='marcar_notificacao_lida'),
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='password_reset.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'), name='password_reset_complete'),
    path('change_email/', views.EmailChangeView.as_view(), name='change_email'),
    path('salvar_checkout_rapido/', salvar_checkout_rapido, name='salvar_checkout_rapido'),
]

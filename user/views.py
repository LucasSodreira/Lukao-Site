from django.views.generic import TemplateView, UpdateView, FormView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView as BaseLoginView
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, get_object_or_404, resolve_url
from django.conf import settings

from checkout.views import (
    DefinirEnderecoPrincipal as BaseDefinirEnderecoPrincipal,
    ExcluirEnderecoView as BaseExcluirEnderecoView,
    AddressSelection as BaseAddressSelection,
    EnderecoEditView as BaseEnderecoEditView,
    EnderecoCreateView as BaseEnderecoCreateView
)
from user.forms import CustomUserChangeForm
from .models import Notificacao

# ==========================
# Views relacionadas à autenticação
# ==========================

class LoginView(BaseLoginView):
    template_name = 'login.html'

    def get_success_url(self):
        return resolve_url(settings.LOGIN_REDIRECT_URL)

    def form_valid(self, form):
        messages.success(self.request, "Login realizado com sucesso!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Credenciais inválidas. Tente novamente.")
        return super().form_invalid(form)

class RegisterView(FormView):
    template_name = 'register.html'
    form_class = UserCreationForm
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        try:
            form.save()
            messages.success(self.request, "Cadastro realizado com sucesso! Você já pode fazer login.")
        except Exception as e:
            messages.error(self.request, "Ocorreu um erro ao processar seu cadastro. Tente novamente.")
            raise e
        return super().form_valid(form)

# ==========================
# Views relacionadas ao perfil do usuário
# ==========================

@method_decorator(login_required, name='dispatch')
class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'personal_info.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if not user.is_authenticated:
            messages.error(self.request, "Você precisa estar logado para acessar esta página.")
            return redirect('login')
        context['user'] = user
        return context

@method_decorator(login_required, name='dispatch')
class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = CustomUserChangeForm
    template_name = 'edit_profile.html'
    success_url = reverse_lazy('profile')

    def get_object(self):
        obj = super().get_object()
        if obj != self.request.user:
            raise PermissionDenied("Você não tem permissão para editar este perfil.")
        return obj

    def form_valid(self, form):
        new_password = form.cleaned_data.get('new_password')
        if new_password:
            user = form.save(commit=False)
            user.set_password(new_password)
            user.save()
            update_session_auth_hash(self.request, user)
            messages.success(self.request, "Senha alterada com sucesso!")
        else:
            form.save()
            messages.success(self.request, "Perfil atualizado com sucesso!")
        return super().form_valid(form)

# ==========================
# Views relacionadas ao histórico de compras
# ==========================

class OrderDetailView(TemplateView):
    template_name = 'order_details.html'

class PurchaseHistoryView(TemplateView):
    template_name = 'purchase_history.html'

# ==========================
# Views relacionadas ao gerenciamento de endereços
# ==========================

class AddresManagementView(BaseAddressSelection):
    template_name = 'address_management.html'

@method_decorator(login_required, name='dispatch')
class DefinirEnderecoPrincipal(BaseDefinirEnderecoPrincipal):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            raise PermissionDenied("Você não tem permissão para realizar esta ação.")
        response = super().post(request, pk)
        return redirect('user:address_management')

@method_decorator(login_required, name='dispatch')
class ExcluirEnderecoView(BaseExcluirEnderecoView):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            raise PermissionDenied("Você não tem permissão para realizar esta ação.")
        response = super().post(request, pk)
        return redirect('user:address_management')

class EnderecoEditView(BaseEnderecoEditView):
    success_url = reverse_lazy('user:address_management')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['eh_user_app'] = True
        return context

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied("Você não tem permissão para editar este endereço.")
        return super().dispatch(request, *args, **kwargs)

class EnderecoCreateView(BaseEnderecoCreateView):
    success_url = reverse_lazy('user:address_management')

def marcar_notificacao_lida(request, notificacao_id):
    notificacao = get_object_or_404(Notificacao, id=notificacao_id, usuario=request.user)
    notificacao.lida = True
    notificacao.save()
    return redirect(request.META.get('HTTP_REFERER', '/'))
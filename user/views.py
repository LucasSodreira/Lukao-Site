import logging
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
from django.views import View
from django.contrib.auth.views import (
    PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
)
from django import forms
from django.views.decorators.http import require_POST

from checkout.views import (
    DefinirEnderecoPrincipal as BaseDefinirEnderecoPrincipal,
    ExcluirEnderecoView as BaseExcluirEnderecoView,
    AddressSelection as BaseAddressSelection,
    EnderecoEditView as BaseEnderecoEditView,
    EnderecoCreateView as BaseEnderecoCreateView
)
from user.forms import CustomUserChangeForm
from .models import Notificacao
from core.models import Pedido, Endereco

logger = logging.getLogger(__name__)

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
        # Log de alteração crítica: atualização de perfil
        logger.info(f"Usuário {self.request.user.id} atualizou o perfil.")
        return super().form_valid(form)

class EmailChangeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email']

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Este e-mail já está em uso.")
        return email

@method_decorator(login_required, name='dispatch')
class EmailChangeView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = EmailChangeForm
    template_name = 'change_email.html'
    success_url = reverse_lazy('user:profile')

    def get_object(self):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "E-mail alterado com sucesso!")
        return super().form_valid(form)

# ==========================
# Views relacionadas ao histórico de compras
# ==========================

class OrderDetailView(TemplateView):
    template_name = 'order_details.html'

class PurchaseHistoryView(TemplateView):
    template_name = 'purchase_history.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Integração com sistema de recomendação: produtos vistos/comprados juntos
        # Exemplo de ponto de integração:
        # produtos_vistos = RecommendationService.get_recently_viewed(self.request.user)
        # produtos_recomendados = RecommendationService.get_bought_together(self.request.user)
        # context['produtos_vistos'] = produtos_vistos
        # context['produtos_recomendados'] = produtos_recomendados 
        return context

@method_decorator(login_required, name='dispatch')
class CancelarPedidoView(View):
    def post(self, request, *args, **kwargs):
        pedido_id = kwargs.get('pedido_id')
        try:
            pedido = Pedido.objects.get(id=pedido_id, usuario=request.user)
        except Pedido.DoesNotExist:
            raise PermissionDenied("Pedido não encontrado.")

        if pedido.status != "X":  # Se ainda não está cancelado
            status_antigo = pedido.status
            pedido.status = "X"
            pedido.save()
            # Log de alteração crítica: cancelamento de pedido e possível devolução de estoque
            logger.info(f"Pedido {pedido.id} cancelado pelo usuário {request.user.id}. Status anterior: {status_antigo}")
            # Garante devolução de estoque se estava concluído
            if status_antigo == "C":
                pedido.atualizar_estoque("aumentar")
                logger.info(f"Estoque devolvido para pedido {pedido.id} (cancelamento).")
        messages.success(request, "Pedido cancelado com sucesso.")
        return redirect('user:purchase_history')

@method_decorator(login_required, name='dispatch')
class DevolverPedidoView(View):
    def post(self, request, *args, **kwargs):
        pedido_id = kwargs.get('pedido_id')
        try:
            pedido = Pedido.objects.get(id=pedido_id, usuario=request.user)
        except Pedido.DoesNotExist:
            raise PermissionDenied("Pedido não encontrado.")

        # Exemplo: status "D" para devolvido
        status_antigo = pedido.status
        pedido.status = "D"
        pedido.save()
        # Log de alteração crítica: devolução de pedido e estoque
        logger.info(f"Pedido {pedido.id} devolvido pelo usuário {request.user.id}. Status anterior: {status_antigo}")
        # Garante devolução de estoque se estava concluído
        if status_antigo == "C":
            pedido.atualizar_estoque("aumentar")
            logger.info(f"Estoque devolvido para pedido {pedido.id} (devolução).")
        messages.success(request, "Pedido devolvido com sucesso.")
        return redirect('user:purchase_history')

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

@require_POST
@login_required
def salvar_checkout_rapido(request):
    perfil = request.user.perfil
    endereco_id = request.POST.get('endereco_rapido')
    metodo = request.POST.get('metodo_pagamento_rapido')
    if endereco_id:
        try:
            endereco = Endereco.objects.get(id=endereco_id, usuario=request.user)
            perfil.endereco_rapido = endereco
        except Endereco.DoesNotExist:
            perfil.endereco_rapido = None
    else:
        perfil.endereco_rapido = None
    perfil.metodo_pagamento_rapido = metodo or None
    perfil.save()
    messages.success(request, "Preferências de checkout rápido salvas!")
    return redirect('profile')
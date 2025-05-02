from django.views.generic import TemplateView, UpdateView, CreateView, FormView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.conf import settings
from decimal import Decimal
from checkout.forms import EnderecoForm
from checkout.utils import obter_itens_do_carrinho, cotar_frete_melhor_envio
from core.models import Endereco, Produto
from django.shortcuts import redirect, get_object_or_404
from django import forms
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required


# ==========================
# Formulários auxiliares
# ==========================

class FreteForm(forms.Form):
    frete_escolhido = forms.ChoiceField(widget=forms.RadioSelect)

    def __init__(self, *args, **kwargs):
        fretes = kwargs.pop('fretes', [])
        super().__init__(*args, **kwargs)
        choices = []

        for frete in fretes:
            try:
                nome = frete['company']['name']
                servico = frete['name']
                preco = frete['price']
                dias = frete['delivery_time']
                choices.append((frete['id'], f"{nome} - {servico} - R$ {preco} - {dias} dias úteis"))
            except (KeyError, TypeError):
                continue  # Ignora entradas inválidas

        self.fields['frete_escolhido'].choices = choices



# ==========================
# Views relacionadas ao endereço
# ==========================

@method_decorator(login_required, name='dispatch')
class EnderecoEditView(UpdateView):
    model = Endereco
    form_class = EnderecoForm
    template_name = 'address.html'
    success_url = reverse_lazy('checkout:select_address')

    def get_queryset(self):
        return Endereco.objects.filter(usuario=self.request.user)

    def form_invalid(self, form):
        messages.error(self.request, "Erro ao atualizar o endereço. Verifique os dados.")
        return super().form_invalid(form)

@method_decorator(login_required, name='dispatch')
class EnderecoCreateView(CreateView):
    model = Endereco
    form_class = EnderecoForm
    template_name = 'address.html'
    success_url = reverse_lazy('checkout:select_address')

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Erro ao criar o endereço. Verifique os dados.")
        return super().form_invalid(form)

@method_decorator(login_required, name='dispatch')
class DefinirEnderecoPrincipal(View):
    def post(self, request, pk):
        endereco = get_object_or_404(Endereco, pk=pk, usuario=request.user)

        # Desativa os outros como principal
        Endereco.objects.filter(usuario=request.user, principal=True).update(principal=False)

        # Ativa este como principal
        endereco.principal = True
        endereco.save()

        return redirect('checkout:select_address')

@method_decorator(login_required, name='dispatch')
class ExcluirEnderecoView(View):
    def post(self, request, pk):
        endereco = get_object_or_404(Endereco, pk=pk, usuario=request.user)
        endereco.delete()
        return redirect('checkout:select_address')

class AddressSelection(LoginRequiredMixin, TemplateView):
    template_name = 'address_selection.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        enderecos = Endereco.objects.filter(usuario=self.request.user)
        context['enderecos'] = enderecos

        return context

# ==========================
# Views relacionadas ao pedido
# ==========================

class OrderSummaryView(LoginRequiredMixin, TemplateView):
    template_name = 'order_summary.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        validation_errors = self.validate_order()
        if validation_errors:
            messages.error(self.request, validation_errors)
            return redirect('review-cart')

        itens_carrinho, subtotal = obter_itens_do_carrinho(self.request)

        frete_info = self.request.session.get('frete_escolhido')
        frete_valor = Decimal(str(frete_info.get('price'))) if frete_info else Decimal('0.00')
        total = subtotal + frete_valor

        endereco = Endereco.objects.filter(usuario=self.request.user, principal=True).first()

        context.update({
            'itens_carrinho': itens_carrinho,
            'subtotal': subtotal,
            'frete': frete_valor,
            'total': total,
            'frete_escolhido': frete_info,
            'endereco': endereco,
        })

        return context

    def validate_order(self):
        errors = []
        carrinho = self.request.session.get('carrinho', {})
        if not carrinho:
            return "Seu carrinho está vazio."

        for item_id, item in carrinho.items():
            try:
                produto = Produto.objects.get(id=item['produto_id'])
                if produto.estoque < item['quantidade']:
                    errors.append(f"{produto.nome}: estoque insuficiente")
            except Produto.DoesNotExist:
                errors.append(f"Produto {item_id} não encontrado")

        endereco = Endereco.objects.filter(usuario=self.request.user, principal=True).first()
        if not endereco:
            errors.append("Endereço principal não encontrado")
        else:
            errors.extend(self.validate_address(endereco))

        if not self.request.session.get('frete_escolhido'):
            errors.append("Método de envio não selecionado")

        return "\n".join(errors) if errors else None

    def validate_address(self, endereco):
        errors = []
        campos_obrigatorios = [
            'nome_completo', 'rua', 'numero', 'bairro',
            'cidade', 'estado', 'cep', 'telefone'
        ]
        for campo in campos_obrigatorios:
            if not getattr(endereco, campo, None):
                errors.append(f"Campo obrigatório: {campo}")
        return errors

class ShipmentMethodView(LoginRequiredMixin, FormView):
    template_name = 'shipping_method.html'
    form_class = FreteForm
    success_url = reverse_lazy('checkout:order-summary')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['fretes'] = self.get_fretes()
        return kwargs

    def get_fretes(self):
        endereco = Endereco.objects.filter(usuario=self.request.user, principal=True).first()
        if endereco:
            return cotar_frete_melhor_envio(endereco.cep, settings.MELHOR_ENVIO_TOKEN)
        return []

    def form_valid(self, form):
        frete_id = form.cleaned_data['frete_escolhido']
        frete_escolhido = next(
            (f for f in self.get_fretes() if str(f['id']) == frete_id),
            None
        )

        if frete_escolhido:
            self.request.session['frete_escolhido'] = {
                'id': frete_escolhido['id'],
                'name': frete_escolhido['name'],
                'price': float(frete_escolhido['price']),
                'company': frete_escolhido['company'],
                'delivery_time': frete_escolhido['delivery_time'],
            }
            self.request.session.modified = True
            return super().form_valid(form)

        messages.error(self.request, "Método de envio inválido")
        return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['fretes'] = self.get_fretes()
        return context

class ThanksView(LoginRequiredMixin, TemplateView):
    template_name = 'thanks.html'

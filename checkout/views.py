import stripe
import json
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView, UpdateView, CreateView, FormView, View

from checkout.forms import EnderecoForm
from checkout.utils import obter_itens_do_carrinho, cotar_frete_melhor_envio
from core.models import Endereco, Produto, Pedido, ItemPedido

# ==========================
# Formulários auxiliares
# ==========================

from django import forms

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
                continue
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['from_index'] = self.request.GET.get('from_index') == '1'
        return context

    def get_success_url(self):
        if self.request.GET.get('from_index') == '1':
            return reverse_lazy('index')
        return str(self.success_url)

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['from_index'] = self.request.GET.get('from_index') == '1'
        return context

    def get_success_url(self):
        if self.request.GET.get('from_index') == '1':
            return reverse_lazy('index')
        return str(self.success_url)

@method_decorator(login_required, name='dispatch')
class DefinirEnderecoPrincipal(View):
    def post(self, request, pk):
        endereco = get_object_or_404(Endereco, pk=pk, usuario=request.user)
        Endereco.objects.filter(usuario=request.user, principal=True).update(principal=False)
        endereco.principal = True
        endereco.save()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'sucesso': True, 'cep': endereco.cep})
        # Redireciona para index se veio do index
        if request.GET.get('from_index') == '1':
            return HttpResponseRedirect(reverse_lazy('index'))
        return redirect('checkout:select_address')

@method_decorator(login_required, name='dispatch')
class ExcluirEnderecoView(View):
    def post(self, request, pk):
        endereco = get_object_or_404(Endereco, pk=pk, usuario=request.user)
        endereco.delete()
        # Redireciona para index se veio do index
        if request.GET.get('from_index') == '1':
            return HttpResponseRedirect(reverse_lazy('index'))
        return redirect('checkout:select_address')

class AddressSelection(LoginRequiredMixin, TemplateView):
    template_name = 'address_selection.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['enderecos'] = Endereco.objects.filter(usuario=self.request.user)
        return context

# ==========================
# Views relacionadas ao pedido
# ==========================

class OrderSummaryView(LoginRequiredMixin, TemplateView):
    template_name = 'order_summary.html'

    def dispatch(self, request, *args, **kwargs):
        validation_errors = self.validate_order()
        if validation_errors:
            messages.error(self.request, validation_errors)
            return redirect('carrinho')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        itens_carrinho, subtotal = obter_itens_do_carrinho(self.request)
        frete_info = self.request.session.get('frete_escolhido')
        frete_valor = Decimal(str(frete_info.get('price'))) if frete_info else Decimal('0.00')
        total = subtotal + frete_valor
        endereco = Endereco.objects.filter(usuario=self.request.user, principal=True).first()
        pedido = Pedido.objects.filter(usuario=self.request.user, status='P').last()
        if not pedido:
            pedido = Pedido.objects.create(
                usuario=self.request.user,
                status='P',
                endereco_entrega=endereco,
                total=total
            )
            for item in itens_carrinho:
                ItemPedido.objects.create(
                    pedido=pedido,
                    produto=item['produto'],
                    quantidade=item['quantidade'],
                    preco_unitario=item['produto'].preco,
                    tamanho=item.get('size')
                )
        context.update({
            'itens_carrinho': itens_carrinho,
            'subtotal': subtotal,
            'frete': frete_valor,
            'total': total,
            'frete_escolhido': frete_info,
            'endereco': endereco,
        })
        context['stripe_public_key'] = settings.STRIPE_PUBLIC_KEY
        return context

    def validate_order(self):
        errors = []
        itens_carrinho, _ = obter_itens_do_carrinho(self.request)
        if not itens_carrinho:
            return "Seu carrinho está vazio."
        for item in itens_carrinho:
            produto = item['produto']
            if produto.estoque < item['quantidade']:
                errors.append(f"{produto.nome}: estoque insuficiente")
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
            itens_carrinho, _ = obter_itens_do_carrinho(self.request)
            produtos = []
            for item in itens_carrinho:
                produtos.append({
                    "weight": float(item['produto'].peso or 1),
                    "width": 15,
                    "height": 10,
                    "length": 20,
                    "insurance_value": float(item['subtotal']),
                    "quantity": item['quantidade']
                })
            return cotar_frete_melhor_envio(
                endereco.cep,
                settings.MELHOR_ENVIO_TOKEN,
                produtos
            )
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
        itens_carrinho, subtotal = obter_itens_do_carrinho(self.request)
        context['itens_carrinho'] = itens_carrinho
        context['subtotal'] = subtotal
        context['fretes'] = self.get_fretes()
        return context

class ThanksView(LoginRequiredMixin, TemplateView):
    template_name = 'thanks.html'

# ==========================
# Stripe Payment
# ==========================

@login_required
def checkout_stripe(request):
    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        itens_carrinho, subtotal = obter_itens_do_carrinho(request)
        if not itens_carrinho:
            messages.error(request, "Seu carrinho está vazio.")
            return redirect('checkout:order-summary')
        frete_info = request.session.get('frete_escolhido')
        frete_valor = Decimal(str(frete_info.get('price'))) if frete_info else Decimal('0.00')
        total = subtotal + frete_valor
        line_items = []
        for item in itens_carrinho:
            line_items.append({
                'price_data': {
                    'currency': 'brl',
                    'product_data': {
                        'name': item['produto'].nome,
                    },
                    'unit_amount': int(item['produto'].preco * 100),
                },
                'quantity': int(item['quantidade']),
            })
        if frete_valor > 0:
            line_items.append({
                'price_data': {
                    'currency': 'brl',
                    'product_data': {
                        'name': 'Frete',
                    },
                    'unit_amount': int(frete_valor * 100),
                },
                'quantity': 1,
            })
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=request.build_absolute_uri(reverse_lazy('checkout:thanks')),
            cancel_url=request.build_absolute_uri(reverse_lazy('checkout:order-summary')),
        )
        return redirect(session.url)
    except Exception as e:
        messages.error(request, f"Erro ao processar pagamento: {str(e)}")
        return redirect('checkout:order-summary')

@require_POST
@login_required
def stripe_create_payment_intent(request):
    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        itens_carrinho, subtotal = obter_itens_do_carrinho(request)
        frete_info = request.session.get('frete_escolhido')
        frete_valor = Decimal(str(frete_info.get('price'))) if frete_info else Decimal('0.00')
        total = subtotal + frete_valor
        amount = int(total * 100) # O valor deve ser em centavos

        # Validação mínima do valor
        if amount < 50: # Stripe geralmente tem um valor mínimo (ex: R$ 0.50)
             return JsonResponse({'error': 'O valor total do pedido é muito baixo para processamento.'}, status=400)

        # Obter ou criar o pedido pendente
        endereco = Endereco.objects.filter(usuario=request.user, principal=True).first()
        pedido, created = Pedido.objects.get_or_create(
            usuario=request.user,
            status='P',
            defaults={
                'endereco_entrega': endereco,
                'total': total,
                'metodo_pagamento': 'stripe' # Pré-define o método
            }
        )
        # Se o pedido já existia, atualiza o total e itens se necessário (pode ser complexo, simplificando aqui)
        if not created:
            pedido.total = total
            pedido.endereco_entrega = endereco
            # Opcional: Limpar itens antigos e adicionar os atuais do carrinho
            # pedido.itens.all().delete()
            # ... (lógica para adicionar itens do carrinho ao pedido) ...
            pedido.save()


        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency='brl', # Moeda brasileira
            automatic_payment_methods={'enabled': True}, # Habilita métodos automáticos (Pix, Cartão, etc.)
            metadata={
                'user_id': request.user.id,
                'pedido_id': pedido.id # Adiciona o ID do pedido aos metadados
                }
        )
        return JsonResponse({'clientSecret': intent.client_secret})
    except Exception as e:
        # Log do erro é recomendado aqui
        return JsonResponse({'error': f'Erro ao criar intenção de pagamento: {str(e)}'}, status=400)

@login_required
def salvar_cep_usuario(request):
    if request.method == 'POST':
        cep = request.POST.get('cep', '').replace('-', '').strip()
        if len(cep) == 8 and cep.isdigit():
            # Salva no endereço principal, se existir
            endereco = Endereco.objects.filter(usuario=request.user, principal=True).first()
            if endereco:
                if endereco.cep != cep:
                    endereco.cep = cep
                    endereco.save(update_fields=['cep'])
            else:
                # Ou salva no user, se preferir
                request.user.cep = cep
                request.user.save(update_fields=['cep'])
            return JsonResponse({'sucesso': True, 'cep': cep})
        return JsonResponse({'sucesso': False, 'erro': 'CEP inválido'})
    return JsonResponse({'sucesso': False, 'erro': 'Requisição inválida'})

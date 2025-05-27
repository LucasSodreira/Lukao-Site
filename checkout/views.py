from decimal import Decimal
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView, UpdateView, CreateView, FormView, View
from django.db import transaction

from checkout.forms import EnderecoForm
from .utils import (
    obter_itens_do_carrinho, 
    cotar_frete_melhor_envio, 
    criar_payment_intent_stripe,
    preparar_produtos_para_frete
)
from core.models import Endereco, Produto, Pedido, ItemPedido, LogAcao, ProdutoVariacao

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

    def form_valid(self, form):
        LogAcao.objects.create(
            usuario=self.request.user,
            acao="Editou endereço",
            detalhes=f"Endereço ID: {self.object.id}"
        )
        return super().form_valid(form)

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
        response = super().form_valid(form)
        LogAcao.objects.create(
            usuario=self.request.user,
            acao="Criou endereço",
            detalhes=f"Endereço ID: {self.object.id}"
        )
        return response

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
        from django.db import transaction
        try:
            with transaction.atomic():
                endereco = get_object_or_404(Endereco, pk=pk, usuario=request.user)
                if endereco.principal:
                    # Já é principal, não faz update desnecessário
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return JsonResponse({'sucesso': True, 'cep': endereco.cep})
                    if request.GET.get('from_index') == '1':
                        return HttpResponseRedirect(reverse_lazy('index'))
                    return redirect('checkout:select_address')
                Endereco.objects.filter(usuario=request.user, principal=True).update(principal=False)
                endereco.principal = True
                endereco.save()
                LogAcao.objects.create(
                    usuario=request.user,
                    acao="Definiu endereço principal",
                    detalhes=f"Endereço ID: {endereco.id} | IP: {request.META.get('REMOTE_ADDR')}"
                )
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'sucesso': True, 'cep': endereco.cep})
            if request.GET.get('from_index') == '1':
                return HttpResponseRedirect(reverse_lazy('index'))
            return redirect('checkout:select_address')
        except Exception as e:
            LogAcao.objects.create(
                usuario=request.user,
                acao="Falha ao definir endereço principal",
                detalhes=f"Erro: {str(e)} | IP: {request.META.get('REMOTE_ADDR')}"
            )
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'sucesso': False, 'erro': 'Erro ao definir principal'}, status=500)
            messages.error(request, "Erro ao definir endereço principal.")
            return redirect('checkout:select_address')

@method_decorator(login_required, name='dispatch')
class ExcluirEnderecoView(View):
    def post(self, request, pk):
        try:
            with transaction.atomic():
                endereco = Endereco.objects.select_for_update().filter(pk=pk, usuario=request.user).first()
                if not endereco:
                    LogAcao.objects.create(
                        usuario=request.user,
                        acao="Tentativa de excluir endereço inexistente",
                        detalhes=f"Endereço ID: {pk} | IP: {request.META.get('REMOTE_ADDR')} | UA: {request.META.get('HTTP_USER_AGENT', '')}"
                    )
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return JsonResponse({'sucesso': False, 'erro': 'Endereço não encontrado.'}, status=404)
                    messages.error(request, "Endereço não encontrado.")
                    return redirect('checkout:select_address')
                if Endereco.objects.filter(usuario=request.user).count() == 1:
                    LogAcao.objects.create(
                        usuario=request.user,
                        acao="Tentativa de excluir único endereço",
                        detalhes=f"Endereço ID: {endereco.id} | IP: {request.META.get('REMOTE_ADDR')} | UA: {request.META.get('HTTP_USER_AGENT', '')}"
                    )
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return JsonResponse({'sucesso': False, 'erro': 'Não é possível excluir o único endereço.'}, status=400)
                    messages.error(request, "Não é possível excluir o único endereço cadastrado.")
                    return redirect('checkout:select_address')
                endereco_id = endereco.id
                endereco.delete()
                LogAcao.objects.create(
                    usuario=request.user,
                    acao="Excluiu endereço",
                    detalhes=f"Endereço ID: {endereco_id} | IP: {request.META.get('REMOTE_ADDR')} | UA: {request.META.get('HTTP_USER_AGENT', '')}"
                )
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'sucesso': True}, status=200)
            if request.GET.get('from_index') == '1':
                return HttpResponseRedirect(reverse_lazy('index'))
            return redirect('checkout:select_address')
        except Exception as e:
            LogAcao.objects.create(
                usuario=request.user,
                acao="Falha ao excluir endereço",
                detalhes=f"Erro: {str(e)} | IP: {request.META.get('REMOTE_ADDR')} | UA: {request.META.get('HTTP_USER_AGENT', '')}"
            )
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'sucesso': False, 'erro': 'Erro ao excluir endereço'}, status=500)
            messages.error(request, "Erro ao excluir endereço.")
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

    def get_endereco_para_pedido(self):
        """Determina qual endereço usar: checkout rápido ou principal"""
        endereco_rapido_id = self.request.session.get('endereco_rapido_id')
        if endereco_rapido_id:
            endereco = Endereco.objects.filter(
                id=endereco_rapido_id, 
                usuario=self.request.user
            ).first()
            if endereco:
                return endereco
            # Se endereço rápido não existe mais, remove da sessão
            self.request.session.pop('endereco_rapido_id', None)
        
        # Fallback para endereço principal
        return Endereco.objects.filter(
            usuario=self.request.user, 
            principal=True
        ).first()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtém itens do carrinho (já com produtos/variações populados)
        itens_carrinho, subtotal = obter_itens_do_carrinho(self.request)
        
        # Informações de frete
        frete_info = self.request.session.get('frete_escolhido')
        frete_valor = Decimal(str(frete_info.get('price'))) if frete_info else Decimal('0.00')
        total = subtotal + frete_valor

        # Cupom
        cupom_codigo = self.request.session.get('cupom')
        cupom = None
        desconto = Decimal('0.00')
        if cupom_codigo:
            try:
                from core.models import Cupom
                cupom = Cupom.objects.get(codigo__iexact=cupom_codigo)
                if cupom.is_valido(self.request.user):
                    total_com_cupom = cupom.aplicar(total)
                    desconto = total - total_com_cupom
                    total = total_com_cupom
                else:
                    self.request.session.pop('cupom', None)
                    cupom = None
            except Exception as e:
                LogAcao.objects.create(
                    usuario=self.request.user,
                    acao="Falha ao validar cupom",
                    detalhes=f"Erro: {str(e)} | IP: {self.request.META.get('REMOTE_ADDR')}"
                )
                self.request.session.pop('cupom', None)
                cupom = None

        # Endereço (considerando checkout rápido)
        endereco = self.get_endereco_para_pedido()
        if not endereco:
            messages.error(self.request, "Cadastre um endereço principal para finalizar a compra.")
            return context

        # Busca ou cria pedido pendente
        pedido = Pedido.objects.filter(
            usuario=self.request.user, 
            status='P'
        ).select_related('endereco_entrega').prefetch_related('itens').last()
        
        if pedido:
            # Atualiza pedido existente se necessário
            if pedido.total != total or pedido.endereco_entrega_id != endereco.id:
                with transaction.atomic():
                    pedido.total = total
                    pedido.endereco_entrega = endereco
                    pedido.save(update_fields=['total', 'endereco_entrega'])
        else:
            # Cria novo pedido
            with transaction.atomic():
                pedido = Pedido.objects.create(
                    usuario=self.request.user,
                    status='P',
                    endereco_entrega=endereco,
                    total=total
                )
                LogAcao.objects.create(
                    usuario=self.request.user,
                    acao="Criou pedido",
                    detalhes=f"Pedido ID: {pedido.id} | IP: {self.request.META.get('REMOTE_ADDR')}"
                )
                
                # Cria itens do pedido usando dados já validados do carrinho
                for item in itens_carrinho:
                    produto = item['produto']
                    variacao = item.get('variacao')
                    quantidade = item['quantidade']
                    preco_unitario = item['subtotal'] / quantidade  # Usa preço já calculado
                    
                    # Revalida estoque antes de criar
                    if variacao:
                        if variacao.estoque < quantidade:
                            messages.error(self.request, f"{produto.nome} - Estoque insuficiente para a variação selecionada.")
                            continue
                    else:
                        if hasattr(produto, 'variacoes') and produto.variacoes.exists():
                            messages.error(self.request, f"{produto.nome} exige seleção de variação.")
                            continue
                        if hasattr(produto, 'estoque') and produto.estoque < quantidade:
                            messages.error(self.request, f"{produto.nome} - Estoque insuficiente.")
                            continue
                    
                    ItemPedido.objects.create(
                        pedido=pedido,
                        produto=produto,
                        quantidade=quantidade,
                        preco_unitario=preco_unitario,
                        variacao=variacao
                    )

        # Configurações do checkout rápido
        perfil = getattr(self.request.user, 'perfil', None)
        checkout_rapido_ativo = bool(self.request.session.get('endereco_rapido_id'))
        
        context.update({
            'itens_carrinho': itens_carrinho,
            'subtotal': subtotal,
            'frete': frete_valor,
            'total': total,
            'frete_escolhido': frete_info,
            'endereco': endereco,
            'cupom': cupom,
            'desconto': desconto,
            'total_com_cupom': total,
            'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
            'checkout_rapido': bool(perfil and perfil.endereco_rapido and perfil.metodo_pagamento_rapido),
            'checkout_rapido_ativo': checkout_rapido_ativo,
            'endereco_rapido': perfil.endereco_rapido if perfil else None,
            'metodo_pagamento_rapido': perfil.metodo_pagamento_rapido if perfil else None,
        })
        
        return context

    def validate_order(self):
        errors = []
        itens_carrinho, _ = obter_itens_do_carrinho(self.request)
        if not itens_carrinho:
            return "Seu carrinho está vazio."
        
        for item in itens_carrinho:
            produto = item['produto']
            variacao = item.get('variacao')
            quantidade = item['quantidade']
            if variacao:
                if variacao.estoque < quantidade:
                    errors.append(f"{produto.nome}: estoque insuficiente para a variação selecionada")
            else:
                if hasattr(produto, 'variacoes') and produto.variacoes.exists():
                    errors.append(f"{produto.nome}: selecione uma variação")
                elif hasattr(produto, 'estoque') and produto.estoque < quantidade:
                    errors.append(f"{produto.nome}: estoque insuficiente")
        
        endereco = self.get_endereco_para_pedido()
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
        """Obtém cotações de frete usando a função centralizada de utils.py"""
        try:
            endereco = Endereco.objects.filter(usuario=self.request.user, principal=True).first()
            if not endereco:
                messages.error(self.request, "Cadastre um endereço principal para cotar o frete.")
                return []
            
            itens_carrinho, _ = obter_itens_do_carrinho(self.request)
            if not itens_carrinho:
                messages.error(self.request, "Seu carrinho está vazio.")
                return []
            
            # Usa a função centralizada de preparação de produtos
            produtos = preparar_produtos_para_frete(itens_carrinho)
            
            return cotar_frete_melhor_envio(
                endereco.cep,
                settings.MELHOR_ENVIO_TOKEN,
                produtos
            )
        except Exception as e:
            LogAcao.objects.create(
                usuario=self.request.user,
                acao="Falha ao cotar frete",
                detalhes=f"Erro: {str(e)} | IP: {self.request.META.get('REMOTE_ADDR')}"
            )
            messages.error(self.request, "Erro ao cotar frete. Tente novamente mais tarde.")
            return []

    def form_valid(self, form):
        try:
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
                LogAcao.objects.create(
                    usuario=self.request.user,
                    acao="Selecionou método de envio",
                    detalhes=f"Frete ID: {frete_escolhido['id']} | IP: {self.request.META.get('REMOTE_ADDR')}"
                )
                return super().form_valid(form)
            messages.error(self.request, "Método de envio inválido")
            return self.form_invalid(form)
        except Exception as e:
            LogAcao.objects.create(
                usuario=self.request.user,
                acao="Falha ao selecionar método de envio",
                detalhes=f"Erro: {str(e)} | IP: {self.request.META.get('REMOTE_ADDR')}"
            )
            messages.error(self.request, "Erro ao selecionar método de envio.")
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

@require_POST
@login_required
def stripe_create_payment_intent(request):
    """Cria PaymentIntent do Stripe via AJAX"""
    try:
        itens_carrinho, _ = obter_itens_do_carrinho(request)
        frete_info = request.session.get('frete_escolhido')
        frete_valor = Decimal(str(frete_info.get('price'))) if frete_info else Decimal('0.00')
        pedido = Pedido.objects.filter(usuario=request.user, status='P').last()
        
        cupom = None
        cupom_codigo = request.session.get('cupom')
        if cupom_codigo:
            try:
                from core.models import Cupom
                cupom = Cupom.objects.get(codigo__iexact=cupom_codigo)
            except Exception:
                cupom = None
        
        client_secret = criar_payment_intent_stripe(
            user=request.user,
            pedido=pedido,
            itens_carrinho=itens_carrinho,
            frete_valor=frete_valor,
            cupom=cupom
        )
        return JsonResponse({'clientSecret': client_secret})
    except Exception as e:
        LogAcao.objects.create(
            usuario=request.user,
            acao="Falha ao criar PaymentIntent Stripe",
            detalhes=f"Erro: {str(e)} | IP: {request.META.get('REMOTE_ADDR')}"
        )
        return JsonResponse({'error': f'Erro ao criar intenção de pagamento: {str(e)}'}, status=400)

@login_required
def salvar_cep_usuario(request):
    """Salva CEP no perfil do usuário ou endereço principal"""
    if request.method == 'POST':
        cep = request.POST.get('cep', '').replace('-', '').strip()
        if len(cep) == 8 and cep.isdigit():
            try:
                endereco = Endereco.objects.filter(usuario=request.user, principal=True).first()
                if endereco:
                    if endereco.cep != cep:
                        endereco.cep = cep
                        endereco.save(update_fields=['cep'])
                        LogAcao.objects.create(
                            usuario=request.user,
                            acao="Atualizou CEP do endereço principal",
                            detalhes=f"Novo CEP: {cep} | Endereço ID: {endereco.id} | IP: {request.META.get('REMOTE_ADDR')}"
                        )
                else:
                    # Tenta salvar no perfil do usuário
                    perfil = getattr(request.user, 'perfil', None)
                    if perfil and hasattr(perfil, 'cep'):
                        perfil.cep = cep
                        perfil.save(update_fields=['cep'])
                        LogAcao.objects.create(
                            usuario=request.user,
                            acao="Atualizou CEP do perfil",
                            detalhes=f"Novo CEP: {cep} | IP: {request.META.get('REMOTE_ADDR')}"
                        )
                    else:
                        # Se não existe perfil com campo CEP, salva na sessão temporariamente
                        request.session['cep_temporario'] = cep
                        request.session.modified = True
                        LogAcao.objects.create(
                            usuario=request.user,
                            acao="Salvou CEP temporário na sessão",
                            detalhes=f"CEP: {cep} | IP: {request.META.get('REMOTE_ADDR')}"
                        )
                
                return JsonResponse({'sucesso': True, 'cep': cep})
            except Exception as e:
                LogAcao.objects.create(
                    usuario=request.user,
                    acao="Falha ao atualizar CEP",
                    detalhes=f"Erro: {str(e)} | IP: {request.META.get('REMOTE_ADDR')}"
                )
                return JsonResponse({'sucesso': False, 'erro': 'Erro ao salvar CEP.'})
        return JsonResponse({'sucesso': False, 'erro': 'CEP inválido'})
    return JsonResponse({'sucesso': False, 'erro': 'Requisição inválida'})

@login_required
def usar_checkout_rapido(request):
    """Ativa o checkout rápido usando endereço e método de pagamento salvos"""
    try:
        if not request.user.is_authenticated:
            return redirect('user:login')
        
        perfil = getattr(request.user, 'perfil', None)
        if perfil and perfil.endereco_rapido:
            # Ativa o checkout rápido salvando o ID do endereço na sessão
            request.session['endereco_rapido_id'] = perfil.endereco_rapido.id
            request.session.modified = True
            
            LogAcao.objects.create(
                usuario=request.user,
                acao="Ativou checkout rápido",
                detalhes=f"Endereço rápido ID: {perfil.endereco_rapido.id} | IP: {request.META.get('REMOTE_ADDR')}"
            )
            messages.success(request, "Checkout rápido ativado! Usando seu endereço salvo.")
            return redirect('checkout:order-summary')
        
        messages.error(request, "Configure um endereço e método de pagamento rápido no seu perfil.")
        return redirect('checkout:order-summary')
    except Exception as e:
        LogAcao.objects.create(
            usuario=request.user,
            acao="Falha ao usar checkout rápido",
            detalhes=f"Erro: {str(e)} | IP: {request.META.get('REMOTE_ADDR')}"
        )
        messages.error(request, "Erro ao ativar checkout rápido.")
        return redirect('checkout:order-summary')

@login_required
def desativar_checkout_rapido(request):
    """Desativa o checkout rápido, voltando ao endereço principal"""
    try:
        if 'endereco_rapido_id' in request.session:
            request.session.pop('endereco_rapido_id')
            request.session.modified = True
            
            LogAcao.objects.create(
                usuario=request.user,
                acao="Desativou checkout rápido",
                detalhes=f"IP: {request.META.get('REMOTE_ADDR')}"
            )
            messages.success(request, "Checkout rápido desativado. Usando endereço principal.")
        
        return redirect('checkout:order-summary')
    except Exception as e:
        LogAcao.objects.create(
            usuario=request.user,
            acao="Falha ao desativar checkout rápido",
            detalhes=f"Erro: {str(e)} | IP: {request.META.get('REMOTE_ADDR')}"
        )
        messages.error(request, "Erro ao desativar checkout rápido.")
        return redirect('checkout:order-summary')

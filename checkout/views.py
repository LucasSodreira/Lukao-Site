from decimal import Decimal
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponseRedirect, HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView, UpdateView, CreateView, FormView, View
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from functools import wraps, lru_cache
import logging
import hashlib

from checkout.forms import EnderecoForm
from .utils import (
    obter_itens_do_carrinho, 
    cotar_frete_melhor_envio, 
    criar_payment_intent_stripe,
    preparar_produtos_para_frete,
    verificar_protecao_carrinho,
    atualizar_protecao_carrinho,
    sanitizar_input,
    get_cache_key
)
from core.models import Endereco, Pedido, ItemPedido, LogAcao, ProdutoVariacao, ReservaEstoque, LogEstoque, Cupom


# Configuração do logger
logger = logging.getLogger(__name__)

# Constantes
CACHE_TIMEOUT = 3600  # 1 hora
RATE_LIMIT_TIMEOUT = 60  # 1 minuto
MAX_REQUESTS_PER_MINUTE = 60
CACHE_PREFIX = 'checkout_'

def _create_or_update_pedido(request, endereco, total, frete_valor, cupom, itens_carrinho):
    """Cria ou atualiza pedido com transação atômica"""
    with transaction.atomic():
        pedido, created = Pedido.objects.select_related(
            'usuario', 
            'endereco_entrega', 
            'cupom'
        ).prefetch_related(
            'itens',
            'itens__produto',
            'itens__variacao'
        ).get_or_create(
            usuario=request.user,
            status='P',
            defaults={
                'endereco_entrega': endereco,
                'total': total,
                'frete_valor': frete_valor,
                'cupom': cupom
            }
        )

        if not created:
            pedido.endereco_entrega = endereco
            pedido.total = total
            pedido.frete_valor = frete_valor
            pedido.cupom = cupom
            pedido.save()

        # Atualiza itens do pedido em bulk
        pedido.itens.all().delete()
        itens_pedido = [
            ItemPedido(
                pedido=pedido,
                produto=item['produto'],
                variacao=item.get('variacao'),
                quantidade=item['quantidade'],
                preco_unitario=item['subtotal'] / item['quantidade']
            ) for item in itens_carrinho
        ]
        ItemPedido.objects.bulk_create(itens_pedido)
        
        return pedido

def _validate_carrinho(request):
    itens_carrinho, _ = obter_itens_do_carrinho(request)
    if not itens_carrinho:
        return False
    return True

def _validate_estoque(request):
    errors = []
    itens_carrinho, _ = obter_itens_do_carrinho(request)
    
    for item in itens_carrinho:
        produto = item['produto']
        variacao = item.get('variacao')
        quantidade = item['quantidade']
        
        if not produto.ativo:
            errors.append(f"{produto.nome}: produto não está mais disponível")
            continue
            
        if variacao:
            if not variacao.ativo:
                errors.append(f"{produto.nome}: variação não está mais disponível")
                continue
                
            try:
                with transaction.atomic():
                    variacao_atual = ProdutoVariacao.objects.select_for_update().get(pk=variacao.pk)
                    if variacao_atual.estoque < quantidade:
                        errors.append(f"{produto.nome}: estoque insuficiente para a variação selecionada")
                    else:
                        request.session[f'reserva_estoque_{variacao.pk}'] = {
                            'quantidade': quantidade,
                            'timestamp': timezone.now().timestamp()
                        }
            except ProdutoVariacao.DoesNotExist:
                errors.append(f"{produto.nome}: variação não encontrada")
        else:
            if hasattr(produto, 'variacoes') and produto.variacoes.exists():
                errors.append(f"{produto.nome}: selecione uma variação")
    
    return len(errors) == 0

def _validate_endereco(request):
    endereco_id = request.session.get('endereco_id')
    if not endereco_id:
        return False
    
    endereco = Endereco.objects.filter(id=endereco_id, usuario=request.user).first()
    if not endereco:
        return False
        
    campos_obrigatorios = [
        'nome_completo', 'rua', 'numero', 'bairro',
        'cidade', 'estado', 'cep', 'telefone'
    ]
    
    for campo in campos_obrigatorios:
        if not getattr(endereco, campo, None):
            return False
            
    return True

def _validate_frete(request):
    if not request.session.get('frete_escolhido'):
        return False
    return True

def get_cache_key(request, prefix):
    """Gera chave de cache segura baseada no usuário"""
    if request.user.is_authenticated:
        return f"{CACHE_PREFIX}{prefix}_{request.user.id}"
    return f"{CACHE_PREFIX}{prefix}_{hashlib.md5(request.META.get('REMOTE_ADDR', '').encode()).hexdigest()}"

def rate_limit(view_func):
    """Decorator para limitar requisições por minuto"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
            
        key = get_cache_key(request, f'rate_limit_{view_func.__name__}')
        current_requests = cache.get(key, 0)
        
        if current_requests >= MAX_REQUESTS_PER_MINUTE:
            logger.warning(f"Rate limit excedido para usuário {request.user.id}")
            return HttpResponse(status=429)
            
        cache.set(key, current_requests + 1, RATE_LIMIT_TIMEOUT)
        return view_func(request, *args, **kwargs)
    return wrapper

# Cache para endereços
@lru_cache(maxsize=100)
def get_endereco_cache(user_id):
    return Endereco.objects.select_related('usuario').filter(usuario_id=user_id)

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
@method_decorator(rate_limit, name='dispatch')
class EnderecoEditView(UpdateView):
    model = Endereco
    form_class = EnderecoForm
    template_name = 'address.html'
    success_url = reverse_lazy('checkout:select_address')

    def get_queryset(self):
        return get_endereco_cache(self.request.user.id)

    def form_valid(self, form):
        try:
            with transaction.atomic():
                response = super().form_valid(form)
                LogAcao.objects.create(
                    usuario=self.request.user,
                    acao="Editou endereço",
                    detalhes=f"Endereço ID: {self.object.id}"
                )
                # Limpa cache relacionado ao endereço
                cache_keys = [
                    f'endereco_{self.object.id}',
                    f'enderecos_usuario_{self.request.user.id}',
                    f'endereco_pedido_{self.request.user.id}'
                ]
                cache.delete_many(cache_keys)
                return response
        except Exception as e:
            logger.error(f"Erro ao editar endereço: {str(e)}")
            messages.error(self.request, "Erro ao atualizar o endereço.")
            return self.form_invalid(form)

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
@method_decorator(rate_limit, name='dispatch')
class EnderecoCreateView(CreateView):
    model = Endereco
    form_class = EnderecoForm
    template_name = 'address.html'
    success_url = reverse_lazy('checkout:select_address')

    def form_valid(self, form):
        with transaction.atomic():
            form.instance.usuario = self.request.user
            response = super().form_valid(form)
            LogAcao.objects.create(
                usuario=self.request.user,
                acao="Criou endereço",
                detalhes=f"Endereço ID: {self.object.id}"
            )
            # Limpa cache relacionado aos endereços do usuário
            cache.delete(f'enderecos_usuario_{self.request.user.id}')
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
        cache_key = get_cache_key(self.request, 'endereco_pedido')
        endereco = cache.get(cache_key)
        
        if endereco is None:
            endereco_rapido_id = self.request.session.get('endereco_rapido_id')
            if endereco_rapido_id:
                endereco = Endereco.objects.select_related('usuario').filter(
                    id=endereco_rapido_id, 
                    usuario=self.request.user
                ).first()
                if endereco:
                    cache.set(cache_key, endereco, CACHE_TIMEOUT)
                    return endereco
                self.request.session.pop('endereco_rapido_id', None)
            
            endereco = Endereco.objects.select_related('usuario').filter(
                usuario=self.request.user, 
                principal=True
            ).first()
            if endereco:
                cache.set(cache_key, endereco, CACHE_TIMEOUT)
        
        return endereco

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            # Obtém itens do carrinho com cache
            cache_key = get_cache_key(self.request, 'itens_carrinho')
            cached_data = cache.get(cache_key)
            
            if cached_data is None:
                itens_carrinho, subtotal = obter_itens_do_carrinho(self.request)
                cached_data = {'itens': itens_carrinho, 'subtotal': subtotal}
                cache.set(cache_key, cached_data, CACHE_TIMEOUT)
            else:
                itens_carrinho = cached_data['itens']
                subtotal = cached_data['subtotal']
            
            # Informações de frete
            frete_info = self.request.session.get('frete_escolhido')
            frete_valor = Decimal(str(frete_info.get('price'))) if frete_info else Decimal('0.00')
            total = subtotal + frete_valor

            # Cupom com cache
            cupom_data = self._get_cupom_data(total)
            total = cupom_data['total']
            desconto = cupom_data['desconto']
            cupom = cupom_data['cupom']

            # Endereço
            endereco = self.get_endereco_para_pedido()
            if not endereco:
                messages.error(self.request, "Cadastre um endereço principal para finalizar a compra.")
                return context

            # Cria ou atualiza o pedido
            pedido = self._create_or_update_pedido(
                self.request, endereco, total, frete_valor, cupom, itens_carrinho
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
                'pedido': pedido
            })
            
        except Exception as e:
            logger.error(f"Erro ao gerar contexto do pedido: {str(e)}")
            messages.error(self.request, "Erro ao carregar dados do pedido.")
            
        return context

    def _get_cupom_data(self, total):
        """Obtém dados do cupom com cache"""
        cupom_codigo = self.request.session.get('cupom')
        cupom = None
        desconto = Decimal('0.00')
        
        if cupom_codigo:
            cache_key = f'cupom_{cupom_codigo}'
            cupom_data = cache.get(cache_key)
            
            if cupom_data is None:
                try:
                    cupom = Cupom.objects.select_related('usuario').get(codigo__iexact=cupom_codigo)
                    if cupom.is_valido(self.request.user):
                        total_com_cupom = cupom.aplicar(total)
                        desconto = total - total_com_cupom
                        total = total_com_cupom
                    else:
                        self.request.session.pop('cupom', None)
                        cupom = None
                except Exception as e:
                    logger.error(f"Erro ao validar cupom: {str(e)}")
                    self.request.session.pop('cupom', None)
                    cupom = None
                    
                cupom_data = {
                    'cupom': cupom,
                    'desconto': desconto,
                    'total': total
                }
                cache.set(cache_key, cupom_data, CACHE_TIMEOUT)
            else:
                cupom = cupom_data['cupom']
                desconto = cupom_data['desconto']
                total = cupom_data['total']
                
        return {
            'cupom': cupom,
            'desconto': desconto,
            'total': total
        }

    def _validate_endereco(self):
        endereco = self.get_endereco_para_pedido()
        if not endereco:
            return "Endereço principal não encontrado"
        
        errors = []
        campos_obrigatorios = [
            'nome_completo', 'rua', 'numero', 'bairro',
            'cidade', 'estado', 'cep', 'telefone'
        ]
        for campo in campos_obrigatorios:
            if not getattr(endereco, campo, None):
                errors.append(f"Campo obrigatório: {campo}")
        return "\n".join(errors) if errors else None

    def _validate_frete(self):
        if not self.request.session.get('frete_escolhido'):
            return "Método de envio não selecionado"
        return None

    def validate_order(self):
        validators = [
            self._validate_carrinho,
            self._validate_estoque,
            self._validate_endereco,
            self._validate_frete
        ]
        errors = []
        for validator in validators:
            if error := validator():
                errors.append(error)
        return "\n".join(errors) if errors else None

@method_decorator(rate_limit, name='dispatch')
class ShipmentMethodView(LoginRequiredMixin, FormView):
    template_name = 'shipping_method.html'
    form_class = FreteForm
    success_url = reverse_lazy('checkout:order-summary')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['fretes'] = self.get_fretes()
        return kwargs

    def get_fretes(self):
        """Obtém cotações de frete com cache"""
        cache_key = get_cache_key(self.request, 'fretes')
        fretes = cache.get(cache_key)
        
        if fretes is not None:
            return fretes
            
        try:
            endereco = Endereco.objects.select_related('usuario').filter(
                usuario=self.request.user, 
                principal=True
            ).first()
            
            if not endereco:
                messages.error(self.request, "Cadastre um endereço principal para cotar o frete.")
                return []
            
            itens_carrinho, _ = obter_itens_do_carrinho(self.request)
            if not itens_carrinho:
                messages.error(self.request, "Seu carrinho está vazio.")
                return []
            
            produtos = preparar_produtos_para_frete(itens_carrinho)
            
            fretes = cotar_frete_melhor_envio(
                endereco.cep,
                settings.MELHOR_ENVIO_TOKEN,
                produtos
            )
            
            cache.set(cache_key, fretes, CACHE_TIMEOUT)
            return fretes
            
        except Exception as e:
            logger.error(f"Erro ao cotar frete: {str(e)}")
            messages.error(self.request, "Erro ao cotar frete. Tente novamente mais tarde.")
            return []

    def form_valid(self, form):
        try:
            with transaction.atomic():
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
                    
                    # Limpa cache de fretes após seleção
                    cache.delete(f'fretes_{self.request.user.id}')
                    
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
@rate_limit
def stripe_create_payment_intent(request):
    """Cria PaymentIntent do Stripe via AJAX"""
    try:
        with transaction.atomic():
            itens_carrinho, _ = obter_itens_do_carrinho(request)
            frete_info = request.session.get('frete_escolhido')
            frete_valor = Decimal(str(frete_info.get('price'))) if frete_info else Decimal('0.00')
            
            pedido = Pedido.objects.select_related(
                'usuario',
                'endereco_entrega',
                'cupom'
            ).prefetch_related(
                'itens',
                'itens__produto',
                'itens__variacao'
            ).filter(usuario=request.user, status='P').last()
            
            cupom = None
            cupom_codigo = request.session.get('cupom')
            if cupom_codigo:
                try:
                    cupom = Cupom.objects.select_related('usuario').get(codigo__iexact=cupom_codigo)
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
@rate_limit
def salvar_cep_usuario(request):
    """Salva CEP no perfil do usuário ou endereço principal"""
    if request.method == 'POST':
        cep = request.POST.get('cep', '').replace('-', '').strip()
        if len(cep) == 8 and cep.isdigit():
            try:
                with transaction.atomic():
                    endereco = Endereco.objects.select_related('usuario').filter(
                        usuario=request.user, 
                        principal=True
                    ).first()
                    
                    if endereco:
                        if endereco.cep != cep:
                            endereco.cep = cep
                            endereco.save(update_fields=['cep'])
                            # Limpa cache relacionado ao endereço
                            cache.delete(f'endereco_{endereco.id}')
                            cache.delete(f'enderecos_usuario_{request.user.id}')
                            cache.delete(f'endereco_pedido_{request.user.id}')
                            
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
@rate_limit
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
            
            # Limpa cache relacionado ao endereço
            cache.delete(f'endereco_pedido_{request.user.id}')
            
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
@rate_limit
def desativar_checkout_rapido(request):
    """Desativa o checkout rápido, voltando ao endereço principal"""
    try:
        if 'endereco_rapido_id' in request.session:
            request.session.pop('endereco_rapido_id')
            request.session.modified = True
            
            # Limpa cache relacionado ao endereço
            cache.delete(f'endereco_pedido_{request.user.id}')
            
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

@require_POST
@login_required
@rate_limit
def finalizar_pedido(request):
    """Finaliza o pedido e cria reservas de estoque"""
    try:
        with transaction.atomic():
            # Obtém dados do pedido
            carrinho = request.user.carrinho
            itens_carrinho = carrinho.itens.all()

            if not itens_carrinho.exists():
                return JsonResponse({'error': 'Carrinho vazio'}, status=400)

            # Validação de segurança: proteção do carrinho
            if not verificar_protecao_carrinho(request, itens_carrinho):
                return JsonResponse({'error': 'Tentativa de manipulação detectada'}, status=403)

            # Validações
            if not _validate_carrinho(request):
                return JsonResponse({'error': 'Carrinho inválido'}, status=400)

            if not _validate_estoque(request):
                return JsonResponse({'error': 'Estoque insuficiente'}, status=400)

            if not _validate_endereco(request):
                return JsonResponse({'error': 'Endereço não selecionado'}, status=400)

            if not _validate_frete(request):
                return JsonResponse({'error': 'Frete não selecionado'}, status=400)

            # Cria reservas de estoque
            reservas = []
            for item in itens_carrinho:
                if item.variacao:
                    reserva = ReservaEstoque.reservar_estoque(
                        variacao_id=item.variacao.id,
                        quantidade=item.quantidade,
                        sessao_id=request.session.session_key
                    )
                    reservas.append(reserva)

            # Cria pedido
            pedido = _create_or_update_pedido(
                request, request.session.get('endereco_id'), request.session.get('total'), request.session.get('frete_valor'), request.session.get('cupom_id'), itens_carrinho
            )

            # Associa reservas ao pedido
            for reserva in reservas:
                reserva.pedido = pedido
                reserva.save()

            # Atualiza proteção após finalizar pedido
            atualizar_protecao_carrinho(request, carrinho.itens.all())

            # Limpa sessão
            request.session.pop('endereco_id', None)
            request.session.pop('frete_valor', None)
            request.session.pop('cupom_id', None)

            return JsonResponse({
                'success': True,
                'pedido_id': pedido.id,
                'redirect_url': reverse('checkout:thanks')
            })

    except Exception as e:
        logger.error(f"Erro ao finalizar pedido: {str(e)}")
        return JsonResponse({'error': 'Erro ao finalizar pedido'}, status=500)

@login_required
def cancelar_pedido(request, pedido_id):
    try:
        # Validação de segurança
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Usuário não autenticado'}, status=401)
            
        # Sanitização de input
        pedido_id = sanitizar_input(str(pedido_id))
        
        # Verifica proteção do carrinho
        carrinho = request.user.carrinho
        if not verificar_protecao_carrinho(request, carrinho.itens.all()):
            return JsonResponse({'error': 'Tentativa de manipulação detectada'}, status=403)
            
        pedido = Pedido.objects.get(id=pedido_id, usuario=request.user)
        
        if pedido.status not in ['P', 'PA']:
            messages.error(request, "Este pedido não pode ser cancelado")
            return redirect('meus_pedidos')
            
        with transaction.atomic():
            # Libera reservas e devolve estoque
            for item in pedido.itens.all():
                if item.variacao:
                    # Libera reservas
                    ReservaEstoque.objects.filter(
                        variacao=item.variacao,
                        pedido=pedido,
                        status__in=['P', 'C']
                    ).update(status='L')
                    
                    # Devolve estoque
                    item.variacao.estoque += item.quantidade
                    item.variacao.save()
                    
                    # Registra log
                    LogEstoque.objects.create(
                        variacao=item.variacao,
                        quantidade=item.quantidade,
                        motivo=f"Cancelamento manual - Pedido {pedido.codigo}",
                        pedido=pedido
                    )
            
            pedido.status = 'X'
            pedido.save()
            
            # Atualiza proteção após cancelar pedido
            atualizar_protecao_carrinho(request, carrinho.itens.all())
            
            # Invalida cache
            cache.delete(get_cache_key(request, 'carrinho'))
            
            messages.success(request, "Pedido cancelado com sucesso")
            return JsonResponse({'success': True})
            
    except Pedido.DoesNotExist:
        messages.error(request, "Pedido não encontrado")
        return redirect('meus_pedidos')
    except Exception as e:
        logger.error(f"Erro ao cancelar pedido: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)

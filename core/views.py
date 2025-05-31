from django.shortcuts import redirect
from django.conf import settings
from django.http import JsonResponse, Http404
from django.views.generic import TemplateView, ListView, DetailView, View
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from core.models import (
    Produto, Endereco, ProdutoVariacao, Cupom, LogAcao, 
    AtributoValor, ItemCarrinho, Categoria
)
from checkout.utils import adicionar_ao_carrinho, cotar_frete_melhor_envio, obter_itens_do_carrinho, obter_carrinho_usuario
from decimal import Decimal
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.cache import cache
from django.views.decorators.cache import cache_page, never_cache
from django.utils.decorators import method_decorator
from functools import lru_cache, wraps
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.utils.html import strip_tags
import re
from django.utils.cache import patch_cache_control
import hashlib
import logging

# Configuração do logger
logger = logging.getLogger(__name__)

# Cache para categorias
@lru_cache(maxsize=128)
def obter_categorias_hierarquicas():
    """
    Retorna categorias organizadas hierarquicamente com subcategorias
    """
    cache_key = 'categorias_hierarquicas'
    result = cache.get(cache_key)
    
    if result is None:
        # Buscar todas as categorias com informações dos produtos
        categorias_principais = Categoria.objects.filter(categoria_pai=None).prefetch_related(
            'subcategorias', 
            'produtos'
        ).annotate(
            total_produtos=models.Count('produtos', distinct=True)
        ).order_by('nome')
        
        categorias_hierarquicas = []
        
        for categoria in categorias_principais:
            # Contar produtos da categoria principal e subcategorias
            produtos_categoria = categoria.total_produtos
            produtos_subcategorias = sum(
                sub.produtos.count() for sub in categoria.subcategorias.all()
            )
            total_produtos = produtos_categoria + produtos_subcategorias
            
            categoria_data = {
                'categoria': categoria,
                'total_produtos': total_produtos,
                'subcategorias': []
            }
            
            # Adicionar subcategorias ordenadas
            for subcategoria in categoria.subcategorias.annotate(
                total_produtos=models.Count('produtos', distinct=True)
            ).order_by('nome'):
                categoria_data['subcategorias'].append({
                    'categoria': subcategoria,
                    'total_produtos': subcategoria.total_produtos
                })
            
            categorias_hierarquicas.append(categoria_data)
            
        cache.set(cache_key, categorias_hierarquicas, timeout=3600)  # Cache por 1 hora
        result = categorias_hierarquicas
    
    return result

# ==========================
# Views relacionadas aos produtos
# ==========================

# Cache para views
@method_decorator(cache_page(60 * 15), name='dispatch')  # Cache por 15 minutos
class IndexView(ListView):
    model = Produto
    template_name = 'index.html'
    context_object_name = 'produtos'
    
    def get_queryset(self):
        return super().get_queryset().filter(ativo=True).select_related(
            'categoria',
            'marca'
        ).prefetch_related(
            'variacoes',
            'variacoes__atributos',
            'variacoes__atributos__tipo',
            'imagens',
            'tags'
        )

def cart_count(request):
    count = 0
    if request.user.is_authenticated:
        carrinho = getattr(request.user, 'carrinho', None)
        if carrinho:
            count = carrinho.itens.count()
    else:
        cart = request.session.get('carrinho', {})
        count = sum(item.get('quantidade', 0) for item in cart.values())
    return JsonResponse({'count': count})

# Cache para views
@method_decorator(cache_page(60 * 15), name='dispatch')  # Cache por 15 minutos
class ItemView(DetailView):
    model = Produto
    template_name = 'item_view.html'
    context_object_name = 'produto'
    
    def get_queryset(self):
        return super().get_queryset().select_related(
            'categoria',
            'marca'
        ).prefetch_related(
            'variacoes',
            'variacoes__atributos',
            'variacoes__atributos__tipo',
            'imagens',
            'avaliacoes'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        produto = self.object
        
        # Cache para dados do produto
        cache_key = f'produto_{produto.id}_context'
        cached_context = cache.get(cache_key)
        
        if cached_context is None:
            # Dados básicos do produto
            context['preco_vigente'] = produto.preco_vigente()
            context['desconto'] = produto.calcular_desconto()
            context['media_avaliacoes'] = produto.media_avaliacoes()
            
            # Buscar cores e tamanhos disponíveis usando prefetch_related
            cores_disponiveis = AtributoValor.objects.filter(
                tipo__nome="Cor",
                variacoes__produto=produto,
                variacoes__estoque__gt=0,
                variacoes__ativo=True
            ).distinct().order_by('ordem', 'valor')
            
            tamanhos_disponiveis = AtributoValor.objects.filter(
                tipo__nome="Tamanho",
                variacoes__produto=produto,
                variacoes__estoque__gt=0,
                variacoes__ativo=True
            ).distinct().order_by('ordem', 'valor')
            
            context.update({
                'cores_disponiveis': cores_disponiveis,
                'tamanhos_disponiveis': tamanhos_disponiveis,
                'variacoes': produto.variacoes.all(),
            })
            
            cache.set(cache_key, context, timeout=3600)  # Cache por 1 hora
            cached_context = context
        
        return cached_context

@method_decorator(cache_page(60 * 15), name='dispatch')  # Cache por 15 minutos
class Product_Listing(ListView):
    model = Produto
    template_name = 'product_listing.html'
    context_object_name = 'produtos'
    paginate_by = 12

    def get_queryset(self):
        queryset = super().get_queryset().filter(ativo=True).select_related(
            'categoria',
            'marca'
        ).prefetch_related(
            'variacoes',
            'variacoes__atributos',
            'variacoes__atributos__tipo',
            'tags'
        )
        
        # Cache para faixas de preço
        cache_key = 'faixas_preco'
        faixas = cache.get(cache_key)
        
        if faixas is None:
            if queryset.exists():
                preco_min_qs = queryset.order_by('preco').first().preco
                preco_max_qs = queryset.order_by('-preco').first().preco
                faixa1 = preco_min_qs + (preco_max_qs - preco_min_qs) * Decimal('0.33')
                faixa2 = preco_min_qs + (preco_max_qs - preco_min_qs) * Decimal('0.66')
                faixa1 = int(faixa1)
                faixa2 = int(faixa2)
            else:
                faixa1 = faixa2 = 0
                
            faixas = {'faixa1': faixa1, 'faixa2': faixa2}
            cache.set(cache_key, faixas, timeout=3600)  # Cache por 1 hora
        
        # Sanitização de parâmetros de busca
        q = self.request.GET.get('q', '').strip()
        categoria = self.request.GET.get('categoria')
        tag = self.request.GET.get('tag')
        
        # Validação de faixas de preço
        try:
            preco_min = float(self.request.GET.get('preco_min', 0))
            preco_max = float(self.request.GET.get('preco_max', float('inf')))
            if preco_min > preco_max:
                preco_min, preco_max = preco_max, preco_min
        except (TypeError, ValueError):
            preco_min, preco_max = 0, float('inf')
            
        # Validação de IDs
        cores_ids = [int(id) for id in self.request.GET.getlist('cores') if id.isdigit()]
        tamanhos_ids = [int(id) for id in self.request.GET.getlist('tamanhos') if id.isdigit()]
        
        # Aplicar filtros com dados sanitizados
        if q:
            queryset = queryset.filter(
                models.Q(nome__icontains=q) |
                models.Q(descricao__icontains=q) |
                models.Q(categoria__nome__icontains=q) |
                models.Q(marca__nome__icontains=q) |
                models.Q(tags__nome__icontains=q)
            ).distinct()
            
        if categoria:
            queryset = queryset.filter(categoria__nome__icontains=categoria)
        if tag:
            queryset = queryset.filter(tags__nome__iexact=tag)
            
        # Filtros de preço com valores validados
        queryset = queryset.filter(preco__gte=preco_min, preco__lte=preco_max)
        
        # Filtros de atributos com IDs validados
        if cores_ids:
            queryset = queryset.filter(
                variacoes__atributos__id__in=cores_ids,
                variacoes__atributos__tipo__nome="Cor",
                variacoes__ativo=True
            ).distinct()
            
        if tamanhos_ids:
            queryset = queryset.filter(
                variacoes__atributos__id__in=tamanhos_ids,
                variacoes__atributos__tipo__nome="Tamanho",
                variacoes__ativo=True
            ).distinct()

        # Ordenação
        sort = self.request.GET.get('sort')
        if sort == 'price_asc':
            queryset = queryset.order_by('preco')
        elif sort == 'price_desc':
            queryset = queryset.order_by('-preco')
        elif sort == 'newest':
            queryset = queryset.order_by('-created_at')
        else:
            queryset = queryset.order_by('-created_at')

        return queryset
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Cache para filtros
        cache_key = 'filtros_produtos'
        filtros = cache.get(cache_key)
        
        if filtros is None:
            cores = AtributoValor.objects.filter(
                tipo__nome="Cor",
                variacoes__produto__ativo=True,
                variacoes__estoque__gt=0,
                variacoes__ativo=True
            ).distinct().order_by('ordem', 'valor')
            
            tamanhos = AtributoValor.objects.filter(
                tipo__nome="Tamanho",
                variacoes__produto__ativo=True,
                variacoes__estoque__gt=0,
                variacoes__ativo=True
            ).distinct().order_by('ordem', 'valor')
            
            filtros = {
                'cores': cores,
                'tamanhos': tamanhos
            }
            cache.set(cache_key, filtros, timeout=3600)  # Cache por 1 hora
            
        context.update(filtros)
        return context

# ==========================
# Views relacionadas ao carrinho
# ==========================

# Decorador personalizado para verificação de permissões
def require_permission(permission):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.has_perm(permission):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def get_cache_key(request, prefix):
    """Gera chave de cache segura baseada no usuário"""
    if request.user.is_authenticated:
        return f"{prefix}_{request.user.id}"
    return f"{prefix}_{hashlib.md5(request.META.get('REMOTE_ADDR', '').encode()).hexdigest()}"

# Proteção contra CSRF em todas as views que manipulam dados
@method_decorator(csrf_protect, name='dispatch')
@method_decorator(never_cache, name='dispatch')
class CartView(LoginRequiredMixin, TemplateView):
    template_name = 'carrinho.html'
    login_url = '/login/'
    
    def get_context_data(self, **kwargs):
        # Sanitização de dados
        context = super().get_context_data(**kwargs)
        if not self.request.user.is_authenticated:
            raise PermissionDenied("Acesso negado")
            
        # Cache seguro para itens do carrinho
        cache_key = get_cache_key(self.request, 'carrinho')
        cached_data = cache.get(cache_key)
        
        if cached_data is None:
            # Obtém itens do carrinho (já com produtos/variações populados)
            itens_carrinho, total = obter_itens_do_carrinho(self.request)
            
            # Lógica de chaves para permitir ações de remover/alterar quantidade
            if self.request.user.is_authenticated:
                carrinho = obter_carrinho_usuario(self.request)
                if carrinho:
                    itens_banco = carrinho.itens.select_related(
                        'produto', 
                        'variacao'
                    ).prefetch_related(
                        'variacao__atributos__tipo'
                    ).all()
                    
                    chave_map = {}
                    id_map = {}
                    
                    for item in itens_banco:
                        variacao = item.variacao
                        if variacao:
                            atributos_str = "-".join([
                                f"{attr.tipo.nome}:{attr.valor}" 
                                for attr in variacao.atributos.all().order_by('tipo__nome')
                            ])
                            chave = f"{item.produto.id}-{atributos_str}"
                            chave_map[chave] = item.id
                            id_map[chave] = item.id
                        else:
                            chave = str(item.produto.id)
                            chave_map[chave] = item.id
                            id_map[chave] = item.id
                            
                    for item in itens_carrinho:
                        variacao = item.get('variacao')
                        if variacao:
                            atributos_str = "-".join([
                                f"{attr.tipo.nome}:{attr.valor}" 
                                for attr in variacao.atributos.all().order_by('tipo__nome')
                            ])
                            chave = f"{item['produto'].id}-{atributos_str}"
                            item['chave'] = chave                        
                            item['chave_id'] = id_map.get(chave, '')
                        else:
                            chave = str(item['produto'].id)
                            item['chave'] = chave
                            item['chave_id'] = id_map.get(chave, '')
                else:
                    for item in itens_carrinho:
                        item['chave'] = ''
                        item['chave_id'] = ''
            else:
                # Para usuários não autenticados
                carrinho_sessao = self.request.session.get('carrinho', {})
                for item in itens_carrinho:
                    variacao = item.get('variacao')
                    if variacao:
                        chave = f"{item['produto'].id}-{variacao.id}"
                        item['chave'] = chave
                        item['chave_id'] = chave
                    else:
                        chave = str(item['produto'].id)
                        item['chave'] = chave
                        item['chave_id'] = chave

            # Garantir que cada item tenha variação carregada com atributos
            for item in itens_carrinho:
                if not item.get('variacao') and 'variacao_id' in item:
                    try:
                        item['variacao'] = ProdutoVariacao.objects.prefetch_related(
                            'atributos__tipo'
                        ).get(id=item['variacao_id'])
                    except ProdutoVariacao.DoesNotExist:
                        item['variacao'] = None
                        
            # Validação: remover itens inválidos
            itens_carrinho = [item for item in itens_carrinho if item['quantidade'] > 0]
            
            # Lógica do cupom
            cupom_codigo = self.request.session.get('cupom')
            cupom = None
            desconto = 0
            
            if cupom_codigo:
                try:
                    cupom = Cupom.objects.get(codigo__iexact=cupom_codigo)
                    if cupom.is_valido(self.request.user):
                        total_com_cupom = cupom.aplicar(total)
                        desconto = total - total_com_cupom
                        total = total_com_cupom
                    else:
                        self.request.session.pop('cupom', None)
                        cupom = None
                except Cupom.DoesNotExist:
                    self.request.session.pop('cupom', None)
                    cupom = None

            # CEP do usuário para cálculo de frete
            if self.request.user.is_authenticated:
                endereco_principal = Endereco.objects.filter(
                    usuario=self.request.user, 
                    principal=True
                ).first()
                cep_usuario = endereco_principal.cep if endereco_principal else None
            else:
                cep_usuario = None
                
            cached_data = {
                'itens_carrinho': itens_carrinho,
                'total_carrinho': total,
                'cupom': cupom,
                'desconto': desconto,
                'total_carrinho_com_cupom': total,
                'cep_usuario': cep_usuario
            }
            
            # Configurar headers de cache
            response = self.render_to_response(context)
            patch_cache_control(response, no_cache=True, no_store=True, must_revalidate=True)
            
            cache.set(cache_key, cached_data, timeout=300)  # 5 minutos
            
        context.update(cached_data)
        return context

    def post(self, request, *args, **kwargs):
        # Lógica do cupom (mantida igual)
        cupom_codigo = request.POST.get('cupom', '').strip()
        if cupom_codigo:
            try:
                cupom = Cupom.objects.get(codigo__iexact=cupom_codigo)
                if not cupom.is_valido(request.user):
                    raise ValidationError("Cupom inválido ou expirado.")
                request.session['cupom'] = cupom.codigo
                messages.success(request, "Cupom aplicado com sucesso!")
                LogAcao.objects.create(
                    usuario=request.user if request.user.is_authenticated else None,
                    acao="Aplicou cupom",
                    detalhes=f"Cupom: {cupom.codigo}"
                )
            except Cupom.DoesNotExist:
                request.session.pop('cupom', None)
                messages.error(request, "Cupom não encontrado.")
            except ValidationError as e:
                request.session.pop('cupom', None)
                messages.error(request, str(e))
        elif 'remover_cupom' in request.POST:
            request.session.pop('cupom', None)
            messages.success(request, "Cupom removido.")
            LogAcao.objects.create(
                usuario=request.user if request.user.is_authenticated else None,
                acao="Removeu cupom",
                detalhes=""
            )
        return redirect('carrinho')

# Classes de manipulação do carrinho (mantidas iguais)
@method_decorator(csrf_protect, name='dispatch')
@method_decorator(never_cache, name='dispatch')
class ManipularItemCarrinho(LoginRequiredMixin, View):
    login_url = '/login/'
    
    def post(self, request, *args, **kwargs):
        # Validação de entrada
        chave = kwargs.get('chave_id')
        if not chave or not chave.isdigit():
            return JsonResponse({'error': 'Chave inválida'}, status=400)
            
        # Verificação de propriedade
        if request.user.is_authenticated:
            try:
                item = ItemCarrinho.objects.get(
                    id=chave, 
                    carrinho__usuario=request.user
                )
            except ItemCarrinho.DoesNotExist:
                raise PermissionDenied("Item não pertence ao usuário")
                
        self.manipular_quantidade_db(item)
        if item.quantidade <= 0:
            item.delete()
        else:
            item.save()
            
        # Invalidar cache do carrinho
        cache_key = get_cache_key(request, 'carrinho')
        cache.delete(cache_key)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            itens_carrinho, subtotal = obter_itens_do_carrinho(request)
            
            # Aplicar cupom se existir
            cupom_codigo = request.session.get('cupom')
            total_com_cupom = subtotal
            desconto = 0
            
            if cupom_codigo:
                try:
                    from core.models import Cupom
                    cupom = Cupom.objects.get(codigo__iexact=cupom_codigo)
                    if cupom.is_valido(request.user):
                        total_com_cupom = cupom.aplicar(subtotal)
                        desconto = subtotal - total_com_cupom
                except Cupom.DoesNotExist:
                    pass
            
            return JsonResponse({
                'success': True,
                'subtotal': float(subtotal),
                'total_com_cupom': float(total_com_cupom),
                'desconto': float(desconto),
                'itens_count': len(itens_carrinho)
            })
        return redirect('carrinho')

    def manipular_quantidade_db(self, item):
        pass

    def manipular_quantidade(self, item):
        pass

class AumentarItemView(ManipularItemCarrinho):
    def manipular_quantidade_db(self, item):
        item.quantidade += 1
    def manipular_quantidade(self, item):
        item['quantidade'] += 1

class DiminuirItemView(ManipularItemCarrinho):
    def manipular_quantidade_db(self, item):
        item.quantidade -= 1
    def manipular_quantidade(self, item):
        item['quantidade'] -= 1

class RemoverItemView(ManipularItemCarrinho):
    def manipular_quantidade_db(self, item):
        item.quantidade = 0
    def manipular_quantidade(self, item):
        item['quantidade'] = 0

def sanitize_input(value):
    """Sanitiza entrada de dados"""
    if isinstance(value, str):
        return strip_tags(value.strip())
    return value

def validate_cep(cep):
    """Valida formato do CEP"""
    cep = re.sub(r'[^0-9]', '', cep)
    return len(cep) == 8 and cep.isdigit()

def validate_quantity(quantity):
    """Valida quantidade"""
    try:
        qty = int(quantity)
        return 1 <= qty <= 99
    except (TypeError, ValueError):
        return False

@method_decorator(csrf_protect, name='dispatch')
@method_decorator(never_cache, name='dispatch')
class AddToCartView(LoginRequiredMixin, View):
    login_url = '/login/'
    
    def post(self, request, *args, **kwargs):
        # Sanitização e validação de entrada
        variacao_id = sanitize_input(request.POST.get('variacao_id'))
        quantity = sanitize_input(request.POST.get('quantity'))
        
        # Validações
        if not variacao_id or not validate_quantity(quantity):
            return JsonResponse({'error': 'Dados inválidos'}, status=400)
            
        try:
            variacao = ProdutoVariacao.objects.select_related('produto').get(
                pk=variacao_id,
                ativo=True
            )
        except (ValueError, ProdutoVariacao.DoesNotExist):
            return JsonResponse({'error': 'Variação inválida'}, status=400)
            
        # Validação de estoque
        if variacao.estoque < int(quantity):
            return JsonResponse({
                'error': 'Estoque insuficiente',
                'disponivel': variacao.estoque
            }, status=400)
            
        # Validação de propriedade
        if not variacao.produto.ativo:
            return JsonResponse({'error': 'Produto inativo'}, status=400)
            
        # Adicionar ao carrinho com dados validados
        try:
            resultado = adicionar_ao_carrinho(
                request,
                variacao.produto.id,
                variacao_id=variacao.id,
                quantidade=int(quantity)
            )
            
            if resultado:
                # Invalidar cache do carrinho
                cache_key = get_cache_key(request, 'carrinho')
                cache.delete(cache_key)
                
                LogAcao.objects.create(
                    usuario=request.user,
                    acao="Adicionou ao carrinho",
                    detalhes=f"Produto: {variacao.produto.id}, Variação: {variacao.id}, Quantidade: {quantity}"
                )
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'error': 'Erro ao adicionar ao carrinho'}, status=400)
                
        except Exception as e:
            logger.error(f"Erro ao adicionar ao carrinho: {str(e)}")
            return JsonResponse({'error': 'Erro interno'}, status=500)

class RemoverItemCarrinho(View):
    def post(self, request, *args, **kwargs):
        chave = kwargs.get('chave_id')  # Corrigido para usar chave_id da URL
        
        if request.user.is_authenticated:
            try:
                item = ItemCarrinho.objects.get(id=chave, carrinho__usuario=request.user)
                item.delete()
                response_data = {'success': True, 'message': 'Item removido com sucesso!'}
            except ItemCarrinho.DoesNotExist:
                raise Http404("Item não encontrado no carrinho.")
        else:
            carrinho = request.session.get('carrinho', {})
            if chave in carrinho:
                del carrinho[chave]
                request.session['carrinho'] = carrinho
                request.session.modified = True
                response_data = {'success': True, 'message': 'Item removido com sucesso!'}
            else:
                raise Http404("Item não encontrado no carrinho.")

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            itens_carrinho, subtotal = obter_itens_do_carrinho(request)
            
            # Aplicar cupom se existir
            cupom_codigo = request.session.get('cupom')
            total_com_cupom = subtotal
            desconto = 0
            
            if cupom_codigo:
                try:
                    from core.models import Cupom
                    cupom = Cupom.objects.get(codigo__iexact=cupom_codigo)
                    if cupom.is_valido(request.user):
                        total_com_cupom = cupom.aplicar(subtotal)
                        desconto = subtotal - total_com_cupom
                except Cupom.DoesNotExist:
                    pass
            
            response_data.update({
                'subtotal': float(subtotal),
                'total_com_cupom': float(total_com_cupom),
                'desconto': float(desconto),
                'itens_count': len(itens_carrinho)
            })
            
            LogAcao.objects.create(
                usuario=request.user if request.user.is_authenticated else None,
                acao="Removeu item do carrinho (AJAX)",
                detalhes=f"Chave: {chave}"
            )
            return JsonResponse(response_data)
        else:
            LogAcao.objects.create(
                usuario=request.user if request.user.is_authenticated else None,
                acao="Removeu item do carrinho",
                detalhes=f"Chave: {chave}"
            )
            messages.success(request, response_data['message'])
            return redirect('carrinho')

# Proteção contra CSRF e validação de método HTTP
@require_http_methods(["POST"])
@csrf_protect
@login_required
def salvar_cep_usuario(request):
    if request.method == 'POST':
        # Sanitização do CEP
        cep = request.POST.get('cep', '').replace('-', '').strip()
        if not cep.isdigit() or len(cep) != 8:
            return JsonResponse({'error': 'CEP inválido'}, status=400)
            
        # Validação de propriedade
        endereco = Endereco.objects.filter(
            usuario=request.user, 
            principal=True
        ).first()
        
        if endereco and endereco.usuario != request.user:
            raise PermissionDenied("Endereço não pertence ao usuário")
            
        if endereco:
            if endereco.cep != cep:
                endereco.cep = cep
                endereco.save(update_fields=['cep'])
        else:
            # Criar novo endereço principal se não existir
            Endereco.objects.create(
                usuario=request.user,
                cep=cep,
                principal=True
            )
        return JsonResponse({'sucesso': True, 'cep': cep})
    return JsonResponse({'sucesso': False, 'erro': 'Requisição inválida'})

# Proteção contra CSRF e validação de método HTTP
@require_http_methods(["GET"])
@csrf_protect
@never_cache
def calcular_frete(request):
    # Rate limiting com IP/usuário
    cache_key = get_cache_key(request, 'frete_calc')
    if cache.get(cache_key):
        return JsonResponse({'error': 'Muitas requisições'}, status=429)
    cache.set(cache_key, True, timeout=60)  # 1 minuto
    
    # Sanitização do CEP
    cep = request.GET.get('cep', '').replace('-', '').strip()
    if not cep.isdigit() or len(cep) != 8:
        return JsonResponse({'error': 'CEP inválido'}, status=400)
        
    try:
        itens_carrinho, subtotal = obter_itens_do_carrinho(request)
        if not itens_carrinho:
            return JsonResponse({'sucesso': False, 'erro': 'Carrinho vazio'})
            
        produtos = []
        
        for item in itens_carrinho:
            variacao = item.get('variacao')
            produto = item['produto']
            
            # Usar dados da variação se disponível, senão do produto
            peso = float(variacao.peso) if variacao and variacao.peso else float(produto.peso or 1)
            width = getattr(variacao, 'width', 15) if variacao else 15
            height = getattr(variacao, 'height', 10) if variacao else 10
            length = getattr(variacao, 'length', 20) if variacao else 20
            
            produtos.append({
                "weight": peso,
                "width": width,
                "height": height,
                "length": length,
                "insurance_value": float(item['subtotal']),
                "quantity": item['quantidade']
            })
            
        token = getattr(settings, 'MELHOR_ENVIO_TOKEN', '')
        fretes = cotar_frete_melhor_envio(cep, token, produtos)
        
        if isinstance(fretes, dict) and 'error' in fretes:
            return JsonResponse({'sucesso': False, 'erro': 'Erro ao consultar frete'})
            
        if not fretes:
            return JsonResponse({'sucesso': False, 'erro': 'Nenhum frete encontrado'})
            
        melhor = min(fretes, key=lambda f: float(f.get('price', 9999)))
        
        # Configurar headers de cache
        response = JsonResponse({
            'sucesso': True,
            'valor': float(melhor['price']),
            'descricao': f"{melhor['company']['name']} - {melhor['name']} ({melhor['delivery_time']} dias úteis)"
        })
        patch_cache_control(response, no_cache=True, no_store=True, must_revalidate=True)
        return response
        
    except Exception as e:        return JsonResponse({'sucesso': False, 'erro': 'Erro ao calcular frete'})



from .models import Endereco, Categoria, Tag
from user.models import Notificacao
from django.core.cache import cache
from django.db.models import Prefetch, Count
from functools import lru_cache
import logging


logger = logging.getLogger(__name__)

# Cache para notificações
@lru_cache(maxsize=100)
def get_notificacoes_cache(user_id):
    return Notificacao.objects.filter(usuario_id=user_id, lida=False).count()

def notificacoes_nao_lidas(request):
    """
    Context processor para notificações não lidas.
    Usa cache para melhor performance.
    """
    if request.user.is_authenticated:
        try:
            # Cache por usuário
            cache_key = f'notificacoes_nao_lidas_{request.user.id}'
            count = cache.get(cache_key)
            
            if count is None:
                count = get_notificacoes_cache(request.user.id)
                cache.set(cache_key, count, timeout=300)  # 5 minutos
                
            return {'notificacoes_nao_lidas': count}
        except Exception as e:
            logger.error(f"Erro ao buscar notificações: {str(e)}")
            return {'notificacoes_nao_lidas': 0}
    return {'notificacoes_nao_lidas': 0}

# Cache para endereços
@lru_cache(maxsize=100)
def get_enderecos_cache(user_id):
    return list(Endereco.objects.filter(usuario_id=user_id).select_related('usuario'))

def endereco_do_usuario(request):
    """
    Retorna nome do usuário, CEP e lista de endereços para exibição em base.html.
    Usa cache e queries otimizadas.
    """
    nome_usuario = None
    cep_usuario = None
    enderecos = []

    if request.user.is_authenticated:
        try:
            # Cache por usuário
            cache_key = f'enderecos_usuario_{request.user.id}'
            cached_data = cache.get(cache_key)
            
            if cached_data is None:
                nome_usuario = request.user.first_name or request.user.username
                enderecos = get_enderecos_cache(request.user.id)
                
                # Encontrar endereço principal
                endereco_principal = next((e for e in enderecos if e.principal), None)
                cep_usuario = endereco_principal.cep if endereco_principal else None
                
                cached_data = {
                    'nome_usuario': nome_usuario,
                    'cep_usuario': cep_usuario,
                    'enderecos': enderecos
                }
                cache.set(cache_key, cached_data, timeout=3600)  # 1 hora
            else:
                nome_usuario = cached_data['nome_usuario']
                cep_usuario = cached_data['cep_usuario']
                enderecos = cached_data['enderecos']
                
        except Exception as e:
            logger.error(f"Erro ao buscar endereços: {str(e)}")
            
    return {
        'nome_usuario': nome_usuario,
        'cep_usuario': cep_usuario,
        'enderecos': enderecos,
    }

# Cache para categorias e tags
@lru_cache(maxsize=1)
def get_categorias_tags_cache():
    return {
        'categorias': list(Categoria.objects.values_list('nome', flat=True).distinct()),
        'tags': list(Tag.objects.values_list('nome', flat=True).distinct())
    }

def categorias_e_tags(request):
    """
    Context processor para categorias e tags.
    Usa cache global para melhor performance.
    """
    try:
        cache_key = 'categorias_tags_global'
        cached_data = cache.get(cache_key)
        
        if cached_data is None:
            cached_data = get_categorias_tags_cache()
            cache.set(cache_key, cached_data, timeout=3600)  # 1 hora
            
        return cached_data
    except Exception as e:
        logger.error(f"Erro ao buscar categorias e tags: {str(e)}")
        return {'categorias': [], 'tags': []}

# Cache para categorias globais
@lru_cache(maxsize=1)
def get_categorias_globais_cache():
    return list(Categoria.objects.filter(
        categoria_pai=None
    ).prefetch_related(
        Prefetch(
            'subcategorias',
            queryset=Categoria.objects.annotate(
                total_produtos=Count('produtos', distinct=True)
            )
        )
    ).annotate(
        total_produtos=Count('produtos', distinct=True)
    ).order_by('nome'))

def categorias_globais(request):
    """
    Context processor para disponibilizar apenas categorias principais no base.html.
    Usa cache e queries otimizadas.
    """
    try:
        cache_key = 'categorias_globais_menu'
        categorias_menu = cache.get(cache_key)
        
        if categorias_menu is None:
            categorias_principais = get_categorias_globais_cache()
            
            categorias_menu = []
            for categoria in categorias_principais:
                # Calcular total de produtos
                produtos_categoria = categoria.total_produtos
                produtos_subcategorias = sum(
                    sub.total_produtos for sub in categoria.subcategorias.all()
                )
                total_produtos = produtos_categoria + produtos_subcategorias
                
                categorias_menu.append({
                    'nome': categoria.nome,
                    'total_produtos': total_produtos
                })
                
            cache.set(cache_key, categorias_menu, timeout=3600)  # 1 hora
            
        return {'categorias_menu': categorias_menu}
    except Exception as e:
        logger.error(f"Erro ao buscar categorias globais: {str(e)}")
        return {'categorias_menu': []}



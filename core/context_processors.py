from .models import Endereco, Categoria, Tag
from user.models import Notificacao
from django.db import models


def notificacoes_nao_lidas(request):
    if request.user.is_authenticated:
        return {
            'notificacoes_nao_lidas': Notificacao.objects.filter(usuario=request.user, lida=False)
        }
    return {}


def endereco_do_usuario(request):
    """
    Retorna nome do usuário, CEP e lista de endereços para exibição em base.html.
    Disponível em todos os templates automaticamente.
    """
    nome_usuario = None
    cep_usuario = None
    enderecos = []

    if request.user.is_authenticated:
        nome_usuario = request.user.first_name or request.user.username
        enderecos = list(Endereco.objects.filter(usuario=request.user))
        endereco = next((e for e in enderecos if e.principal), None)
        if endereco:
            cep_usuario = endereco.cep

    return {
        'nome_usuario': nome_usuario,
        'cep_usuario': cep_usuario,
        'enderecos': enderecos,
    }


def categorias_e_tags(request):
    return {
        'categorias': Categoria.objects.values_list('nome', flat=True).distinct(),
        'tags': Tag.objects.values_list('nome', flat=True).distinct(),
    }


def categorias_globais(request):
    """
    Context processor para disponibilizar apenas categorias principais no base.html
    """
    categorias_principais = Categoria.objects.filter(categoria_pai=None).annotate(
        total_produtos=models.Count('produtos', distinct=True)
    ).order_by('nome')
    
    categorias_menu = []
    
    for categoria in categorias_principais:
        # Contar produtos da categoria principal e suas subcategorias
        produtos_categoria = categoria.total_produtos
        produtos_subcategorias = sum(
            sub.produtos.count() for sub in categoria.subcategorias.all()
        )
        total_produtos = produtos_categoria + produtos_subcategorias
        
        categorias_menu.append({
            'nome': categoria.nome,
            'total_produtos': total_produtos
        })
    
    return {
        'categorias_menu': categorias_menu
    }



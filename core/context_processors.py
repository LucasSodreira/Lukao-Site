from .models import Endereco, Categoria, Tag
from user.models import Notificacao


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



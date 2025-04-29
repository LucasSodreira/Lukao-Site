def limpar_carrinho(request):
    """Limpa completamente o carrinho da sessão."""
    request.session['carrinho'] = {}
    request.session.modified = True


def adicionar_ao_carrinho(request, produto_id, quantidade=1):
    """Adiciona um produto ao carrinho, ou aumenta a quantidade."""
    carrinho = request.session.get('carrinho', {})

    produto_id = str(produto_id)  # Sempre garantir que a chave é string

    if produto_id in carrinho:
        carrinho[produto_id] += quantidade
    else:
        carrinho[produto_id] = quantidade

    request.session['carrinho'] = carrinho
    request.session.modified = True


def remover_do_carrinho(request, produto_id):
    """Remove um produto do carrinho."""
    carrinho = request.session.get('carrinho', {})

    produto_id = str(produto_id)

    if produto_id in carrinho:
        del carrinho[produto_id]
        request.session['carrinho'] = carrinho
        request.session.modified = True


def calcular_total_carrinho(request):
    """Calcula o total geral dos produtos no carrinho."""
    from .models import Produto  # Importa aqui dentro para evitar loops circulares

    carrinho = request.session.get('carrinho', {})
    total = 0

    produtos = Produto.objects.filter(id__in=carrinho.keys())

    for produto in produtos:
        quantidade = carrinho.get(str(produto.id), 0)
        total += produto.preco * quantidade

    return total

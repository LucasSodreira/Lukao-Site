from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from core.models import Produto

def debug_variacoes_json(request, produto_id):
    """Debug endpoint para ver os dados das variações"""
    produto = get_object_or_404(Produto, id=produto_id)
    
    # Reproduzir exatamente a lógica da ItemView
    variacoes = list(produto.variacoes.filter(estoque__gt=0).prefetch_related('atributos__tipo'))
    variacoes_por_cor = {}
    cores_disponiveis = []
    
    for variacao in variacoes:
        cor_obj = None
        tamanho_obj = None
        
        for attr in variacao.atributos.all():
            if attr.tipo.nome.lower() == 'cor':
                cor_obj = attr
            elif attr.tipo.nome.lower() == 'tamanho':
                tamanho_obj = attr
        
        if cor_obj and tamanho_obj:
            if cor_obj.id not in variacoes_por_cor:
                variacoes_por_cor[cor_obj.id] = {
                    'cor': {
                        'id': cor_obj.id,
                        'valor': cor_obj.valor,
                        'codigo': cor_obj.codigo
                    },
                    'tamanhos': {}
                }
                cores_disponiveis.append({
                    'id': cor_obj.id,
                    'valor': cor_obj.valor,
                    'codigo': cor_obj.codigo
                })
            
            variacoes_por_cor[cor_obj.id]['tamanhos'][tamanho_obj.id] = {
                'tamanho': {
                    'id': tamanho_obj.id,
                    'valor': tamanho_obj.valor,
                },
                'variacao': {
                    'id': variacao.id,
                    'estoque': variacao.estoque
                }
            }
    
    return JsonResponse({
        'produto_id': produto.id,
        'produto_nome': produto.nome,
        'variacoes_por_cor': variacoes_por_cor,
        'cores_disponiveis': cores_disponiveis,
        'total_variacoes': len(variacoes)
    }, json_dumps_params={'indent': 2})

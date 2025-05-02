import requests
from core.models import Produto

# ==========================
# Funções relacionadas ao carrinho
# ==========================

def obter_itens_do_carrinho(request):
    """Obtém os itens do carrinho e calcula o subtotal."""
    carrinho = request.session.get('carrinho', {})
    itens_carrinho = []
    subtotal = 0

    # Coletar todos os IDs de produtos usados no carrinho
    produto_ids = []
    for item in carrinho.values():
        if isinstance(item, dict) and 'produto_id' in item:
            
            produto_ids.append(item['produto_id'])

    produtos = Produto.objects.filter(id__in=produto_ids)
    produto_dict = {p.id: p for p in produtos}

    for chave, item in carrinho.items():
        produto = produto_dict.get(item['produto_id'])
        if produto:
            quantidade = item['quantidade']
            tamanho = item.get('size')
            subtotal_item = produto.preco * quantidade
            subtotal += subtotal_item

            itens_carrinho.append({
                'produto': produto,
                'quantidade': quantidade,
                'size': tamanho,
                'subtotal': subtotal_item,
            })

    return itens_carrinho, subtotal


def limpar_carrinho(request):
    """Limpa completamente o carrinho da sessão."""
    request.session['carrinho'] = {}
    request.session.modified = True


def adicionar_ao_carrinho(request, produto_id, size=None, quantidade=1):
    """Adiciona um produto ao carrinho."""
    carrinho = request.session.get('carrinho', {})
    
    # Migra carrinho antigo para novo formato se necessário
    if any(isinstance(v, int) for v in carrinho.values()):
        carrinho = migrar_carrinho_antigo(carrinho)
    
    # Cria uma chave única combinando ID e tamanho
    chave_item = f"{produto_id}-{size}" if size else str(produto_id)
    
    if chave_item in carrinho:
        carrinho[chave_item]['quantidade'] += quantidade
    else:
        carrinho[chave_item] = {
            'produto_id': produto_id,
            'quantidade': quantidade,
            'size': size
        }
    
    request.session['carrinho'] = carrinho
    request.session.modified = True
    return carrinho


def remover_do_carrinho(request, produto_key):
    """Remove um item do carrinho."""
    carrinho = request.session.get('carrinho', {})
    
    # Migra carrinho antigo para novo formato se necessário
    if any(isinstance(v, int) for v in carrinho.values()):
        carrinho = migrar_carrinho_antigo(carrinho)
        request.session['carrinho'] = carrinho
        request.session.modified = True
    
    if produto_key in carrinho:
        del carrinho[produto_key]
        request.session['carrinho'] = carrinho
        request.session.modified = True
    
    return len(carrinho)


def calcular_total_carrinho(request):
    """Calcula o total geral dos produtos no carrinho."""
    from ..core.models import Produto
    
    carrinho = request.session.get('carrinho', {})
    total = 0
    
    # Migra carrinho antigo para novo formato se necessário
    if any(isinstance(v, int) for v in carrinho.values()):
        carrinho = migrar_carrinho_antigo(carrinho)
        request.session['carrinho'] = carrinho
        request.session.modified = True
    
    # Obtém todos os IDs de produtos únicos
    produto_ids = []
    for item in carrinho.values():
        if isinstance(item, dict) and 'produto_id' in item:
            produto_ids.append(item['produto_id'])
    
    produtos = Produto.objects.filter(id__in=produto_ids)
    produto_dict = {p.id: p for p in produtos}
    
    for item in carrinho.values():
        if isinstance(item, dict) and 'produto_id' in item:
            produto = produto_dict.get(item['produto_id'])
            if produto:
                total += produto.preco * item['quantidade']
    
    return total


def migrar_carrinho_antigo(carrinho):
    """Migra carrinho do formato antigo para o novo formato."""
    novo_carrinho = {}
    for chave, valor in carrinho.items():
        if isinstance(valor, int):  # Formato antigo
            novo_carrinho[chave] = {
                'produto_id': int(chave),
                'quantidade': valor,
                'size': None
            }
        else:  # Já está no formato novo
            novo_carrinho[chave] = valor
    return novo_carrinho

# ==========================
# Funções relacionadas ao frete
# ==========================

def cotar_frete_melhor_envio(cep_destino, token, cep_origem='01001-000'):
    url = "https://sandbox.melhorenvio.com.br/api/v2/me/shipment/calculate"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    payload = {
        "from": {"postal_code": cep_origem},
        "to": {"postal_code": cep_destino},
        "products": [
            {
                "weight": 1,
                "width": 15,
                "height": 10,
                "length": 20,
                "insurance_value": 100,
                "quantity": 1
            }
        ],
        "options": {
            "receipt": False,
            "own_hand": False,
            "insurance_value": 100,
            "reverse": False,
            "non_commercial": True
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    print("Response Status Code:", response.status_code)  # Debug: Verifica o status da resposta
    if response.status_code == 200:
        return response.json()
    return []

def cotar_frete_melhor_envio(cep_destino, token, cep_origem='01001-000'):
    url = "https://sandbox.melhorenvio.com.br/api/v2/me/shipment/calculate"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    payload = {
        "from": {"postal_code": cep_origem},
        "to": {"postal_code": cep_destino},
        "products": [
            {
                "weight": 1,
                "width": 15,
                "height": 10,
                "length": 20,
                "insurance_value": 100,
                "quantity": 1
            }
        ],
        "options": {
            "receipt": False,
            "own_hand": False,
            "insurance_value": 100,
            "reverse": False,
            "non_commercial": True
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    print("Response Status Code:", response.status_code)  # Debug: Verifica o status da resposta
    if response.status_code == 200:
        return response.json()
    return []
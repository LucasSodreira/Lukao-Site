import requests
from core.models import Produto
import mercadopago
from django.conf import settings

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
            # Verifica se o item tem 'produto_id' e adiciona ao produto_ids
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

def cotar_frete_melhor_envio(cep_destino, token, produtos, cep_origem='01001-000'):
    url = "https://sandbox.melhorenvio.com.br/api/v2/me/shipment/calculate"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    payload = {
        "from": {"postal_code": cep_origem},
        "to": {"postal_code": cep_destino},
        "products": produtos,  # Lista de produtos com peso, dimensões, quantidade
        "options": {
            "receipt": False,
            "own_hand": False,
            "insurance_value": sum(p['insurance_value'] for p in produtos),
            "reverse": False,
            "non_commercial": True
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        return response.json()
    return []


def preparar_produtos_para_frete(itens_carrinho):
    """Prepara a lista de produtos para cálculo de frete."""
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
    return produtos


def criar_envio_melhor_envio(pedido, token):
    url = "https://sandbox.melhorenvio.com.br/api/v2/me/shipment"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = montar_payload_envio(pedido)
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

def montar_payload_envio(pedido):
    return {
        "service": pedido.frete_id,  # ID do frete escolhido
        "from": {
            "name": "Lukao MultiMarcas",
            "phone": "(83)99381-0707",
            "email": "lucas.sobreira@academico.ifpb.edu.br",
            "document": "00000000000",
            "company_document": "00000000000000",
            "state_register": "",
            "address": "Rua Hipólito Cassiano",
            "complement": "",
            "number": "123",
            "district": "Centro",
            "city": "Pau dos Ferros",
            "state_abbr": "RN",
            "country_id": "BR",
            "postal_code": "01001-000"
        },
        "to": {
            "name": pedido.endereco.nome_completo,
            "phone": pedido.endereco.telefone,
            "email": pedido.usuario.email,
            "document": "15306069428",  # CPF do cliente, se tiver
            "address": pedido.endereco.rua,
            "complement": pedido.endereco.complemento,
            "number": pedido.endereco.numero,
            "district": pedido.endereco.bairro,
            "city": pedido.endereco.cidade,
            "state_abbr": pedido.endereco.estado,
            "country_id": "BR",
            "postal_code": pedido.endereco.cep
        },
        "products": [
            {
                "name": item.produto.nome,
                "quantity": item.quantidade,
                "unitary_value": float(item.preco_unitario)
            } for item in pedido.itens.all()
        ],
        "insurance_value": float(pedido.total),
        "package": {
            "weight": sum([float(item.produto.peso or 1) for item in pedido.itens.all()]),
            "width": 15,
            "height": 10,
            "length": 20
        }
    }

# ==========================
# Funções relacionadas ao pagamento
# ==========================

def criar_preferencia_pagamento(pedido):
    sdk = mercadopago.SDK(settings.MERCADO_PAGO_ACCESS_TOKEN)
    preference_data = {
        "items": [
            {
                "title": f"Pedido #{pedido.id}",
                "quantity": 1,
                "unit_price": float(pedido.total)
            }
        ],
        "payer": {
            "email": pedido.usuario.email,
        },
        "external_reference": str(pedido.id)
    }
    preference_response = sdk.preference().create(preference_data)
    print(preference_response)
    return preference_response["response"]["id"]
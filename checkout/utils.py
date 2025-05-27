import requests
from core.models import Produto, Carrinho, ItemCarrinho, ProdutoVariacao
from core.models import Carrinho, ItemCarrinho
from django.db import transaction
from core.models import LogAcao
import stripe
from django.db.models import F, Sum
from django.conf import settings
from decimal import Decimal
from core.models import LogAcao
import logging

logger = logging.getLogger(__name__)

# ==========================
# Funções relacionadas ao carrinho
# ==========================

def obter_carrinho_usuario(request):
    if not request.user.is_authenticated:
        return None
    carrinho, _ = Carrinho.objects.get_or_create(usuario=request.user)
    return carrinho

def obter_itens_do_carrinho(request):
    """Obtém os itens do carrinho e calcula o subtotal, validando produtos/variações ativos e estoque."""
    if request.user.is_authenticated:
        carrinho = obter_carrinho_usuario(request)
        itens = carrinho.itens.select_related('produto', 'variacao').all()
        itens_carrinho = []
        subtotal = 0
        for item in itens:
            # Segurança: só considera produtos/variações ativos
            if not item.produto.ativo:
                continue
            if item.variacao and not (item.variacao.ativo and item.variacao.estoque >= item.quantidade):
                continue
            if not item.variacao and hasattr(item.produto, 'variacoes') and item.produto.variacoes.exists():
                continue
            preco_vigente = item.produto.preco_vigente()
            subtotal_item = preco_vigente * item.quantidade
            subtotal += subtotal_item
            itens_carrinho.append({
                'produto': item.produto,
                'quantidade': item.quantidade,
                'variacao': item.variacao,
                'subtotal': subtotal_item,
            })
        return itens_carrinho, subtotal
    else:
        # fallback para sessão
        carrinho = request.session.get('carrinho', {})
        itens_carrinho = []
        subtotal = 0
        produto_ids = []
        variacao_ids = []
        for item in carrinho.values():
            if isinstance(item, dict) and 'produto_id' in item:
                produto_ids.append(item['produto_id'])
            if isinstance(item, dict) and 'variacao_id' in item:
                variacao_ids.append(item['variacao_id'])
        produtos = Produto.objects.filter(id__in=produto_ids, ativo=True)
        produto_dict = {p.id: p for p in produtos}
        variacoes = ProdutoVariacao.objects.filter(id__in=variacao_ids, ativo=True)
        variacao_dict = {v.id: v for v in variacoes}
        for chave, item in carrinho.items():
            produto = produto_dict.get(item['produto_id'])
            variacao = variacao_dict.get(item.get('variacao_id'))
            if not produto:
                continue
            quantidade = item['quantidade']
            # Segurança: só permite variação se for válida e com estoque
            if variacao:
                if not (variacao.estoque >= quantidade and variacao.produto_id == produto.id):
                    continue
            else:
                if hasattr(produto, 'variacoes') and produto.variacoes.exists():
                    continue
            preco_vigente = produto.preco_vigente()
            subtotal_item = preco_vigente * quantidade
            subtotal += subtotal_item
            itens_carrinho.append({
                'produto': produto,
                'quantidade': quantidade,
                'variacao': variacao,
                'subtotal': subtotal_item,
            })
        return itens_carrinho, subtotal


def limpar_carrinho(request):
    """Limpa completamente o carrinho da sessão ou do banco, com logging de auditoria."""
    if request.user.is_authenticated:
        carrinho = Carrinho.objects.filter(usuario=request.user).first()
        if carrinho:
            ItemCarrinho.objects.filter(carrinho=carrinho).delete()
            LogAcao.objects.create(
                usuario=request.user,
                acao="Limpou carrinho",
                detalhes=f"Carrinho ID: {carrinho.id} | IP: {getattr(request.META, 'REMOTE_ADDR', '')}"
            )
    else:
        request.session['carrinho'] = {}
        request.session.modified = True
        # Não loga usuário anônimo

def adicionar_ao_carrinho(request, produto_id, variacao_id=None, quantidade=1):
    """Adiciona um produto ao carrinho, validando estoque e status ativo."""
    quantidade = min(int(quantidade), settings.CARRINHO_MAX_QUANTIDADE)
    produto = Produto.objects.filter(id=produto_id, ativo=True).first()
    if not produto:
        return None  # Produto inativo ou inexistente
    variacao = None
    if variacao_id:
        variacao = ProdutoVariacao.objects.filter(id=variacao_id, produto=produto, ativo=True).first()
        if not variacao or variacao.estoque < quantidade:
            return None  # Variação inválida ou sem estoque
    else:
        if hasattr(produto, 'variacoes') and produto.variacoes.exists():
            return None  # Produto exige variação
    if not request.user.is_authenticated:
        # fallback para sessão se não logado
        carrinho = request.session.get('carrinho', {})
        chave_item = f"{produto_id}-{variacao_id}" if variacao_id else str(produto_id)
        if chave_item in carrinho:
            nova_qtd = min(carrinho[chave_item]['quantidade'] + quantidade, settings.CARRINHO_MAX_QUANTIDADE)
            carrinho[chave_item]['quantidade'] = nova_qtd
        else:
            carrinho[chave_item] = {
                'produto_id': produto_id,
                'quantidade': quantidade,
                'variacao_id': variacao_id
            }
        request.session['carrinho'] = carrinho
        request.session.modified = True
        return carrinho
    carrinho = obter_carrinho_usuario(request)
    item, created = ItemCarrinho.objects.get_or_create(
        carrinho=carrinho,
        produto_id=produto_id,
        variacao_id=variacao_id
    )
    if not created:
        item.quantidade = min(item.quantidade + quantidade, settings.CARRINHO_MAX_QUANTIDADE)
    else:
        item.quantidade = quantidade
    item.save()
    return carrinho


def remover_do_carrinho(request, produto_key):
    """Remove um item do carrinho, com logging de auditoria."""
    if request.user.is_authenticated:
        carrinho = obter_carrinho_usuario(request)
        item = carrinho.itens.filter(id=produto_key).first()
        if item:
            item.delete()
            LogAcao.objects.create(
                usuario=request.user,
                acao="Removeu item do carrinho",
                detalhes=f"ItemCarrinho ID: {produto_key} | Carrinho ID: {carrinho.id} | IP: {getattr(request.META, 'REMOTE_ADDR', '')}"
            )
        return carrinho.itens.count()
    else:
        carrinho_sessao = request.session.get('carrinho', {})
        if produto_key in carrinho_sessao:
            del carrinho_sessao[produto_key]
            request.session['carrinho'] = carrinho_sessao
            request.session.modified = True
        return len(carrinho_sessao)

def calcular_total_carrinho(request):
    """Calcula o total geral dos produtos no carrinho usando a lógica de preços correta."""
    # Usa a mesma lógica de obter_itens_do_carrinho para garantir consistência
    itens_carrinho, subtotal = obter_itens_do_carrinho(request)
    return subtotal


def migrar_carrinho_sessao_para_banco(request):
    """
    Migra o carrinho do visitante (sessão/localStorage) para o banco de dados do usuário autenticado,
    garantindo segurança, validação de estoque, produto e variação, atomicidade e logging.
    """
    if not request.user.is_authenticated:
        return
    carrinho_sessao = request.session.get('carrinho', {})
    if not carrinho_sessao:
        return
    try:
        with transaction.atomic():
            carrinho, _ = Carrinho.objects.get_or_create(usuario=request.user)
            for item_id, item in carrinho_sessao.items():
                try:
                    produto_id = int(item['produto_id'])
                    quantidade = int(item['quantidade'])
                    if quantidade < 1:
                        continue
                except (KeyError, ValueError, TypeError):
                    continue
                quantidade = min(quantidade, settings.CARRINHO_MAX_QUANTIDADE)
                produto = Produto.objects.filter(id=produto_id, ativo=True).first()
                if not produto:
                    continue
                variacao = None
                if item.get('variacao_id'):
                    try:
                        variacao_id = int(item['variacao_id'])
                        variacao = ProdutoVariacao.objects.filter(
                            id=variacao_id, produto=produto, estoque__gte=quantidade, ativo=True
                        ).first()
                    except (ValueError, TypeError):
                        continue
                    if not variacao:
                        continue
                else:
                    if hasattr(produto, 'variacoes') and produto.variacoes.exists():
                        continue
                # Sempre use o preço do banco, nunca do visitante
                item_carrinho, created = ItemCarrinho.objects.get_or_create(
                    carrinho=carrinho,
                    produto=produto,
                    variacao=variacao
                )
                if not created:
                    item_carrinho.quantidade = min(item_carrinho.quantidade + quantidade, settings.CARRINHO_MAX_QUANTIDADE)
                else:
                    item_carrinho.quantidade = quantidade
                item_carrinho.save()
            LogAcao.objects.create(
                usuario=request.user,
                acao="Migrou carrinho da sessão para banco",
                detalhes=f"Itens migrados: {len(carrinho_sessao)} | IP: {request.META.get('REMOTE_ADDR', '')}"
            )
    except Exception as e:
        LogAcao.objects.create(
            usuario=request.user,
            acao="Falha ao migrar carrinho da sessão para banco",
            detalhes=f"Erro: {str(e)} | IP: {request.META.get('REMOTE_ADDR', '')}"
        )
    finally:
        if 'carrinho' in request.session:
            del request.session['carrinho']
            request.session.modified = True

# ==========================
# Funções relacionadas ao frete
# ==========================

def cotar_frete_melhor_envio(cep_destino, token, produtos, cep_origem=None):
    """Cota frete via Melhor Envio, com tratamento de exceções e logging de falha."""
    if cep_origem is None:
        cep_origem = settings.MELHOR_ENVIO_CEP_ORIGEM
    
    url = f"{settings.MELHOR_ENVIO_BASE_URL}/me/shipment/calculate"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "from": {"postal_code": cep_origem},
        "to": {"postal_code": cep_destino},
        "products": produtos,
        "options": {
            "receipt": False,
            "own_hand": False,
            "insurance_value": sum(p.get('insurance_value', 0) for p in produtos),
            "reverse": False,
            "non_commercial": True
        }
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            try:
                return response.json()
            except Exception as e:
                logger.error(f"Erro ao decodificar resposta do Melhor Envio: {e}")
                return []
        else:
            logger.warning(f"Falha ao cotar frete: status {response.status_code} | retorno: {response.text}")
            return []
    except Exception as e:
        logger.error(f"Erro de conexão ao cotar frete: {e}")
        return []


def preparar_produtos_para_frete(itens_carrinho):
    """Prepara a lista de produtos para cálculo de frete considerando variação, validando dados."""
    produtos = []
    defaults = settings.FRETE_DEFAULTS
    
    for item in itens_carrinho:
        produto = item['produto']
        variacao = item.get('variacao')
        try:
            peso = float(variacao.peso) if variacao and hasattr(variacao, 'peso') and variacao.peso else float(produto.peso or defaults['peso_padrao'])
            width = getattr(variacao, 'width', defaults['largura_padrao']) if variacao else defaults['largura_padrao']
            height = getattr(variacao, 'height', defaults['altura_padrao']) if variacao else defaults['altura_padrao']
            length = getattr(variacao, 'length', defaults['comprimento_padrao']) if variacao else defaults['comprimento_padrao']
            insurance_value = float(item['subtotal'])
            quantidade = int(item['quantidade'])
            produtos.append({
                "weight": peso,
                "width": width,
                "height": height,
                "length": length,
                "insurance_value": insurance_value,
                "quantity": quantidade
            })
        except Exception as e:
            logger.warning(f"Item ignorado no cálculo de frete por dados inválidos: {e}")
            continue
    return produtos


def criar_envio_melhor_envio(pedido, token):
    """Cria envio no Melhor Envio, com tratamento de exceções e logging de falha."""
    url = f"{settings.MELHOR_ENVIO_BASE_URL}/me/shipment"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = montar_payload_envio(pedido)
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            try:
                return response.json()
            except Exception as e:
                logger.error(f"Erro ao decodificar resposta do Melhor Envio (envio): {e}")
                return None
        else:
            logger.warning(f"Falha ao criar envio: status {response.status_code} | retorno: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Erro de conexão ao criar envio: {e}")
        return None

def montar_payload_envio(pedido):
    """Monta payload do envio, sanitizando campos obrigatórios."""
    def safe_str(val):
        return str(val) if val is not None else ''
    
    remetente = settings.REMETENTE_CONFIG
    
    return {
        "service": safe_str(getattr(pedido, 'frete_id', '')),
        "from": {
            "name": remetente['name'],
            "phone": remetente['phone'],
            "email": remetente['email'],
            "document": remetente['document'],
            "company_document": remetente['company_document'],
            "state_register": remetente['state_register'],
            "address": remetente['address'],
            "complement": remetente['complement'],
            "number": remetente['number'],
            "district": remetente['district'],
            "city": remetente['city'],
            "state_abbr": remetente['state_abbr'],
            "country_id": remetente['country_id'],
            "postal_code": remetente['postal_code']
        },
        "to": {
            "name": safe_str(getattr(pedido.endereco, 'nome_completo', '')),
            "phone": safe_str(getattr(pedido.endereco, 'telefone', '')),
            "email": safe_str(getattr(pedido.usuario, 'email', '')),
            "document": safe_str(getattr(pedido.endereco, 'cpf', '15306069428')),
            "address": safe_str(getattr(pedido.endereco, 'rua', '')),
            "complement": safe_str(getattr(pedido.endereco, 'complemento', '')),
            "number": safe_str(getattr(pedido.endereco, 'numero', '')),
            "district": safe_str(getattr(pedido.endereco, 'bairro', '')),
            "city": safe_str(getattr(pedido.endereco, 'cidade', '')),
            "state_abbr": safe_str(getattr(pedido.endereco, 'estado', '')),
            "country_id": "BR",
            "postal_code": safe_str(getattr(pedido.endereco, 'cep', ''))
        },
        "products": [
            {
                "name": safe_str(item.produto.nome),
                "quantity": int(item.quantidade),
                "unitary_value": float(item.preco_unitario)
            } for item in pedido.itens.all()
        ],
        "insurance_value": float(pedido.total),
        "package": {
            "weight": sum([float(item.produto.peso or settings.FRETE_DEFAULTS['peso_padrao']) for item in pedido.itens.all()]),
            "width": settings.FRETE_DEFAULTS['largura_padrao'],
            "height": settings.FRETE_DEFAULTS['altura_padrao'],
            "length": settings.FRETE_DEFAULTS['comprimento_padrao']
        }
    }

# ==========================
# Funções relacionadas ao pagamento
# ==========================

def criar_payment_intent_stripe(user, pedido, itens_carrinho, frete_valor, cupom=None):
    """
    Cria um PaymentIntent Stripe de forma segura, recalculando valores e validando estoque/preço.
    Retorna o client_secret ou lança exceção.
    """
    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        # Recalcula total
        subtotal = sum(item['produto'].preco_vigente() * item['quantidade'] for item in itens_carrinho)
        total = subtotal + Decimal(str(frete_valor or 0))
        desconto = Decimal('0.00')
        if cupom and hasattr(cupom, 'is_valido') and cupom.is_valido(user):
            total_com_cupom = cupom.aplicar(total)
            desconto = total - total_com_cupom
            total = total_com_cupom
        # Validação de estoque/preço
        for item in itens_carrinho:
            produto = item['produto']
            variacao = item.get('variacao')
            quantidade = item['quantidade']
            if variacao:
                if not (variacao.ativo and variacao.estoque >= quantidade):
                    raise Exception(f"{produto.nome} - Estoque insuficiente para a variação selecionada.")
            else:
                if hasattr(produto, 'variacoes') and produto.variacoes.exists():
                    raise Exception(f"{produto.nome} exige seleção de variação.")
                elif hasattr(produto, 'estoque') and produto.estoque < quantidade:
                    raise Exception(f"{produto.nome}: estoque insuficiente")
        amount = int(total * 100)
        if amount < 50:
            raise Exception("O valor total do pedido é muito baixo para processamento.")
        # Cria PaymentIntent
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency='brl',
            automatic_payment_methods={'enabled': True},
            metadata={
                'user_id': user.id,
                'pedido_id': pedido.id if pedido else '',
            }
        )
        LogAcao.objects.create(
            usuario=user,
            acao="Criou PaymentIntent Stripe (utils)",
            detalhes=f"Intent ID: {intent.id} | Pedido ID: {pedido.id if pedido else ''}"
        )
        return intent.client_secret
    except Exception as e:
        logger.error(f"Erro ao criar PaymentIntent Stripe: {e}")
        LogAcao.objects.create(
            usuario=user,
            acao="Falha ao criar PaymentIntent Stripe (utils)",
            detalhes=f"Erro: {str(e)} | Pedido ID: {pedido.id if pedido else ''}"
        )
        raise


import requests
from core.models import Produto, Carrinho, ItemCarrinho, ProdutoVariacao
from django.db import transaction
from core.models import LogAcao
import stripe
from django.conf import settings
from decimal import Decimal
import logging
from django.core.cache import cache
from functools import lru_cache, wraps
from typing import Dict, List, Tuple, Optional, Any
from asgiref.sync import sync_to_async
import aiohttp
from django.core.exceptions import ValidationError
import re
from uuid import uuid4
from core.models import ReservaEstoque, ProtecaoCarrinho


# Configuração de logging
logger = logging.getLogger(__name__)

# Constantes
CARRINHO_CONFIG = {
    'MAX_QUANTIDADE': 99,
    'CACHE_TIMEOUT': 3600,
    'SESSION_KEY': 'carrinho',
    'CACHE_PREFIX': 'carrinho_',
    'MAX_ITENS': 50,
    'RATE_LIMIT': 60,  # requisições por minuto
}

FRETE_CONFIG = {
    'TIMEOUT': 10,
    'MAX_TENTATIVAS': 3,
    'CACHE_TIMEOUT': 3600,
    'CACHE_PREFIX': 'frete_',
    'MAX_PESO': 30.0,  # kg
    'MAX_VALOR': 10000.0,  # R$
}

# Validações
def validar_cep(cep: str) -> bool:
    """Valida formato do CEP brasileiro"""
    return bool(re.match(r'^\d{8}$', cep.replace('-', '')))

def validar_quantidade(quantidade: int) -> bool:
    """Valida quantidade de itens"""
    return 0 < quantidade <= CARRINHO_CONFIG['MAX_QUANTIDADE']

def sanitizar_input(valor: str) -> str:
    """Remove caracteres potencialmente perigosos"""
    return re.sub(r'[<>]', '', valor).strip()

def get_cache_key(prefix: str, *args) -> str:
    """Gera chave de cache segura baseada nos argumentos"""
    key_parts = [prefix] + [str(arg) for arg in args]
    return '_'.join(key_parts)

# Exceções personalizadas
class CarrinhoError(Exception):
    """Exceção base para erros do carrinho"""
    pass

class EstoqueInsuficienteError(CarrinhoError):
    """Erro quando não há estoque suficiente"""
    pass

class ProdutoInativoError(CarrinhoError):
    """Erro quando produto está inativo"""
    pass

class VariacaoInvalidaError(CarrinhoError):
    """Erro quando variação é inválida"""
    pass

class RateLimitError(CarrinhoError):
    """Erro quando limite de requisições é excedido"""
    pass

# Decoradores
def rate_limit(func):
    """Decorator para limitar requisições por minuto"""
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return await func(request, *args, **kwargs)
            
        key = get_cache_key('rate_limit', request.user.id, func.__name__)
        current = cache.get(key, 0)
        
        if current >= CARRINHO_CONFIG['RATE_LIMIT']:
            logger.warning(f"Rate limit excedido para usuário {request.user.id}")
            raise RateLimitError("Limite de requisições excedido")
            
        cache.set(key, current + 1, 60)
        return await func(request, *args, **kwargs)
    return wrapper

def cache_result(timeout: int = 3600):
    """Decorator para cachear resultados de funções"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = get_cache_key(func.__name__, *args, *kwargs.values())
            result = cache.get(key)
            
            if result is None:
                result = await func(*args, **kwargs)
                cache.set(key, result, timeout)
                
            return result
        return wrapper
    return decorator

# ==========================
# Funções relacionadas ao carrinho
# ==========================

@lru_cache(maxsize=128)
async def obter_carrinho_usuario(request) -> Optional[Carrinho]:
    """Obtém o carrinho do usuário com cache"""
    if not request.user.is_authenticated:
        return None
        
    cache_key = get_cache_key(CARRINHO_CONFIG['CACHE_PREFIX'], request.user.id)
    carrinho = cache.get(cache_key)
    
    if carrinho is None:
        carrinho, _ = await sync_to_async(Carrinho.objects.select_related('usuario').get_or_create)(usuario=request.user)
        cache.set(cache_key, carrinho, CARRINHO_CONFIG['CACHE_TIMEOUT'])
        
    return carrinho

@lru_cache(maxsize=256)
async def validar_itens_carrinho(itens: List[ItemCarrinho]) -> Tuple[set, set]:
    """Valida todos os itens do carrinho em uma única query"""
    produto_ids = [item.produto.id for item in itens]
    variacao_ids = [item.variacao.id for item in itens if item.variacao]
    
    produtos_validos = set(await sync_to_async(Produto.objects.filter(
        id__in=produto_ids, 
        ativo=True
    ).values_list)('id', flat=True))
    
    variacoes_validas = set(await sync_to_async(ProdutoVariacao.objects.filter(
        id__in=variacao_ids,
        ativo=True
    ).values_list)('id', flat=True))
    
    return produtos_validos, variacoes_validas

@cache_result(timeout=CARRINHO_CONFIG['CACHE_TIMEOUT'])
@rate_limit
async def obter_itens_do_carrinho(request) -> Tuple[List[Dict], Decimal]:
    """Obtém os itens do carrinho e calcula o subtotal"""
    if request.user.is_authenticated:
        carrinho = await obter_carrinho_usuario(request)
        itens = await sync_to_async(list)(carrinho.itens.select_related(
            'produto',
            'variacao'
        ).prefetch_related(
            'variacao__atributos__tipo',
            'produto__variacoes'
        ).all())
        
        # Validação em lote
        produtos_validos, variacoes_validas = await validar_itens_carrinho(itens)
        
        itens_carrinho = []
        subtotal = Decimal('0.00')
        
        for item in itens:
            if item.produto.id not in produtos_validos:
                continue
                
            if item.variacao and item.variacao.id not in variacoes_validas:
                continue
                
            if item.variacao and not item.variacao.estoque >= item.quantidade:
                continue
                
            if not item.variacao and hasattr(item.produto, 'variacoes') and await sync_to_async(item.produto.variacoes.exists)():
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
        return await gerenciar_carrinho_sessao(request, 'obter')

async def gerenciar_carrinho_sessao(request, acao: str, **kwargs) -> Tuple[List[Dict], Decimal]:
    """Gerencia operações do carrinho na sessão"""
    carrinho = request.session.get(CARRINHO_CONFIG['SESSION_KEY'], {})
    itens_carrinho = []
    subtotal = Decimal('0.00')
    
    if not carrinho:
        return itens_carrinho, subtotal
        
    produto_ids = []
    variacao_ids = []
    
    for item in carrinho.values():
        if isinstance(item, dict):
            if 'produto_id' in item:
                produto_ids.append(int(item['produto_id']))
            if 'variacao_id' in item:
                variacao_ids.append(int(item['variacao_id']))
                
    # Busca otimizada
    produtos = await sync_to_async(Produto.objects.filter(id__in=produto_ids, ativo=True).all)()
    produto_dict = {p.id: p for p in produtos}
    
    variacoes = await sync_to_async(ProdutoVariacao.objects.filter(id__in=variacao_ids).all)()
    variacao_dict = {v.id: v for v in variacoes}
    
    for chave, item in carrinho.items():
        produto = produto_dict.get(item['produto_id'])
        if not produto:
            continue
            
        variacao = variacao_dict.get(item.get('variacao_id'))
        quantidade = min(int(item['quantidade']), CARRINHO_CONFIG['MAX_QUANTIDADE'])
        
        if variacao:
            if not (variacao.estoque >= quantidade and variacao.produto_id == produto.id):
                continue
        else:
            if hasattr(produto, 'variacoes') and await sync_to_async(produto.variacoes.exists)():
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

@rate_limit
@cache_result(timeout=60)  # Cache por 1 minuto
async def verificar_protecao_carrinho(request, itens_carrinho) -> bool:
    """Verifica se o carrinho está protegido contra manipulação"""
    try:
        protecao = await sync_to_async(ProtecaoCarrinho.get_protecao)(
            sessao_id=request.session.session_key,
            usuario_id=request.user.id if request.user.is_authenticated else None
        )
        return await sync_to_async(protecao.verificar_manipulacao)(itens_carrinho)
    except ValidationError:
        return False

@cache_result(timeout=60)  # Cache por 1 minuto
async def atualizar_protecao_carrinho(request, itens_carrinho) -> None:
    """Atualiza a proteção do carrinho com os itens atuais"""
    protecao = await sync_to_async(ProtecaoCarrinho.get_protecao)(
        sessao_id=request.session.session_key,
        usuario_id=request.user.id if request.user.is_authenticated else None
    )
    protecao.checksum = await sync_to_async(protecao.gerar_checksum)(itens_carrinho)
    await sync_to_async(protecao.save)()

@rate_limit
@cache_result(timeout=CARRINHO_CONFIG['CACHE_TIMEOUT'])
async def adicionar_ao_carrinho(request, produto_id: int, variacao_id: Optional[int] = None, quantidade: int = 1) -> Optional[Any]:
    try:
        # Validação de segurança
        if not request.user.is_authenticated:
            raise CarrinhoError("Usuário não autenticado")
            
        # Sanitização de inputs
        produto_id = sanitizar_input(str(produto_id))
        if variacao_id:
            variacao_id = sanitizar_input(str(variacao_id))
        quantidade = sanitizar_input(str(quantidade))
        
        # Verifica proteção do carrinho
        carrinho = await obter_carrinho_usuario(request)
        if not await verificar_protecao_carrinho(request, carrinho.itens.all()):
            raise CarrinhoError("Tentativa de manipulação detectada")
            
        quantidade = min(int(quantidade), CARRINHO_CONFIG['MAX_QUANTIDADE'])
        
        if not validar_quantidade(quantidade):
            raise ValidationError("Quantidade inválida")
        
        produto = await sync_to_async(Produto.objects.filter(id=produto_id, ativo=True).first)()
        if not produto:
            raise ProdutoInativoError(f"Produto {produto_id} não encontrado ou inativo")
            
        variacao = None
        if variacao_id:
            variacao = await sync_to_async(ProdutoVariacao.objects.filter(
                id=variacao_id,
                produto=produto,
                ativo=True
            ).first)()
            
            if not variacao:
                raise VariacaoInvalidaError(f"Variação {variacao_id} não encontrada ou inativa")
                
            # Verifica estoque disponível considerando reservas
            if not await verificar_reserva_estoque(variacao_id, quantidade):
                raise EstoqueInsuficienteError(f"Estoque insuficiente para a variação {variacao_id}")
                
            # Cria reserva de estoque
            sessao_id = request.session.session_key or str(uuid4())
            reserva = await criar_reserva_estoque(variacao_id, quantidade, sessao_id)
            if not reserva:
                raise EstoqueInsuficienteError("Não foi possível reservar o estoque")
                
        else:
            if hasattr(produto, 'variacoes') and await sync_to_async(produto.variacoes.exists)():
                raise VariacaoInvalidaError("Produto requer seleção de variação")
                
        if not request.user.is_authenticated:
            return await gerenciar_carrinho_sessao(request, 'adicionar', 
                produto_id=produto_id, 
                variacao_id=variacao_id, 
                quantidade=quantidade
            )
            
        carrinho = await obter_carrinho_usuario(request)
        async with transaction.atomic():
            item, created = await sync_to_async(ItemCarrinho.objects.get_or_create)(
                carrinho=carrinho,
                produto_id=produto_id,
                variacao_id=variacao_id
            )
            
            if not created:
                item.quantidade = min(item.quantidade + quantidade, CARRINHO_CONFIG['MAX_QUANTIDADE'])
            else:
                item.quantidade = quantidade
                
            await sync_to_async(item.save)()
            
            # Atualiza proteção após adicionar item
            await atualizar_protecao_carrinho(request, carrinho.itens.all())
            
            # Invalida cache
            cache.delete(get_cache_key(CARRINHO_CONFIG['CACHE_PREFIX'], request.user.id))
            
        return {'success': True, 'message': 'Item adicionado ao carrinho'}
        
    except Exception as e:
        logger.error(f"Erro ao adicionar ao carrinho: {str(e)}")
        raise

@rate_limit
@cache_result(timeout=CARRINHO_CONFIG['CACHE_TIMEOUT'])
async def remover_do_carrinho(request, produto_key):
    try:
        # Validação de segurança
        if not request.user.is_authenticated:
            raise CarrinhoError("Usuário não autenticado")
            
        # Sanitização de input
        produto_key = sanitizar_input(produto_key)
        
        # Verifica proteção do carrinho
        carrinho = await obter_carrinho_usuario(request)
        if not await verificar_protecao_carrinho(request, carrinho.itens.all()):
            raise CarrinhoError("Tentativa de manipulação detectada")
            
        item = await sync_to_async(carrinho.itens.filter(id=produto_key).first)()
        if item:
            await sync_to_async(item.delete)()
            await sync_to_async(LogAcao.objects.create)(
                usuario=request.user,
                acao="Removeu item do carrinho",
                detalhes=f"ItemCarrinho ID: {produto_key} | Carrinho ID: {carrinho.id}"
            )
        return await sync_to_async(carrinho.itens.count)()
    except Exception as e:
        logger.error(f"Erro ao remover do carrinho: {str(e)}")
        raise

    # Atualiza proteção após remover item
    await atualizar_protecao_carrinho(request, carrinho.itens.all())
    
    # Invalida cache
    cache.delete(get_cache_key(CARRINHO_CONFIG['CACHE_PREFIX'], request.user.id))
    
    return {'success': True, 'message': 'Item removido do carrinho'}

@cache_result(timeout=CARRINHO_CONFIG['CACHE_TIMEOUT'])
async def calcular_total_carrinho(request):
    """Calcula o total geral dos produtos no carrinho"""
    itens_carrinho, subtotal = await obter_itens_do_carrinho(request)
    return subtotal

@rate_limit
async def migrar_carrinho_sessao_para_banco(request):
    """Migra o carrinho do visitante para o banco de dados do usuário autenticado."""
    if not request.user.is_authenticated:
        return
        
    carrinho_sessao = request.session.get('carrinho', {})
    if not carrinho_sessao:
        return
        
    try:
        async with transaction.atomic():
            carrinho, _ = await sync_to_async(Carrinho.objects.get_or_create)(usuario=request.user)
            
            # Coleta IDs para busca otimizada
            produto_ids = []
            variacao_ids = []
            for item in carrinho_sessao.values():
                if isinstance(item, dict):
                    try:
                        if 'produto_id' in item:
                            produto_ids.append(int(item['produto_id']))
                        if 'variacao_id' in item:
                            variacao_ids.append(int(item['variacao_id']))
                    except (ValueError, TypeError):
                        logger.warning(f"ID inválido encontrado no carrinho da sessão: {item}")
                        continue
            
            # Validação de limites
            if len(produto_ids) > CARRINHO_CONFIG['MAX_ITENS']:
                raise ValidationError(f"Número máximo de itens ({CARRINHO_CONFIG['MAX_ITENS']}) excedido")
            
            # Busca otimizada com select_related
            produtos = await sync_to_async(Produto.objects.filter(
                id__in=produto_ids, 
                ativo=True
            ).select_related('categoria').all)()
            produto_dict = {p.id: p for p in produtos}
            
            variacoes = await sync_to_async(ProdutoVariacao.objects.filter(
                id__in=variacao_ids,
                ativo=True
            ).select_related('produto').all)()
            variacao_dict = {v.id: v for v in variacoes}
            
            # Prepara itens para bulk_create
            itens_para_criar = []
            itens_para_atualizar = []
            
            for item_id, item in carrinho_sessao.items():
                try:
                    produto_id = int(item['produto_id'])
                    quantidade = min(int(item['quantidade']), CARRINHO_CONFIG['MAX_QUANTIDADE'])
                    
                    # Validações
                    if quantidade < 1:
                        logger.warning(f"Quantidade inválida para produto {produto_id}: {quantidade}")
                        continue
                        
                    produto = produto_dict.get(produto_id)
                    if not produto:
                        logger.warning(f"Produto {produto_id} não encontrado ou inativo")
                        continue
                        
                    variacao = None
                    if item.get('variacao_id'):
                        variacao_id = int(item['variacao_id'])
                        variacao = variacao_dict.get(variacao_id)
                        if not variacao or not variacao.estoque >= quantidade:
                            logger.warning(f"Variação {variacao_id} não encontrada ou sem estoque suficiente")
                            continue
                    else:
                        if hasattr(produto, 'variacoes') and await sync_to_async(produto.variacoes.exists)():
                            logger.warning(f"Produto {produto_id} requer seleção de variação")
                            continue
                    
                    # Verifica se item já existe
                    item_existente = await sync_to_async(ItemCarrinho.objects.filter(
                        carrinho=carrinho,
                        produto=produto,
                        variacao=variacao
                    ).first)()
                    
                    if item_existente:
                        item_existente.quantidade = min(
                            item_existente.quantidade + quantidade, 
                            CARRINHO_CONFIG['MAX_QUANTIDADE']
                        )
                        itens_para_atualizar.append(item_existente)
                    else:
                        itens_para_criar.append(ItemCarrinho(
                            carrinho=carrinho,
                            produto=produto,
                            variacao=variacao,
                            quantidade=quantidade
                        ))
                        
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(f"Erro ao processar item do carrinho: {str(e)}")
                    continue
            
            # Executa operações em lote
            if itens_para_criar:
                await sync_to_async(ItemCarrinho.objects.bulk_create)(itens_para_criar)
            
            if itens_para_atualizar:
                await sync_to_async(ItemCarrinho.objects.bulk_update)(
                    itens_para_atualizar, 
                    ['quantidade']
                )
            
            # Registra a ação
            await sync_to_async(LogAcao.objects.create)(
                usuario=request.user,
                acao="Migrou carrinho da sessão para banco",
                detalhes=f"Itens migrados: {len(itens_para_criar) + len(itens_para_atualizar)}"
            )
            
            # Limpa cache
            cache.delete(get_cache_key(CARRINHO_CONFIG['CACHE_PREFIX'], request.user.id))
            
    except Exception as e:
        logger.error(f"Erro ao migrar carrinho: {str(e)}")
        await sync_to_async(LogAcao.objects.create)(
            usuario=request.user,
            acao="Falha ao migrar carrinho da sessão para banco",
            detalhes=f"Erro: {str(e)}"
        )
        raise CarrinhoError(f"Erro ao migrar carrinho: {str(e)}")
    finally:
        if 'carrinho' in request.session:
            del request.session['carrinho']
            request.session.modified = True

# ==========================
# Funções relacionadas ao frete
# ==========================

@cache_result(timeout=FRETE_CONFIG['CACHE_TIMEOUT'])
async def cotar_frete_melhor_envio(cep_destino: str, token: str, produtos: List[Dict], cep_origem: Optional[str] = None) -> List[Dict]:
    """Cota frete via Melhor Envio"""
    if not validar_cep(cep_destino):
        raise ValidationError("CEP inválido")
        
    if cep_origem is None:
        cep_origem = settings.MELHOR_ENVIO_CEP_ORIGEM
    
    # Validação de peso e valor
    peso_total = sum(p.get('weight', 0) for p in produtos)
    valor_total = sum(p.get('insurance_value', 0) for p in produtos)
    
    if peso_total > FRETE_CONFIG['MAX_PESO']:
        raise ValidationError("Peso total excede o limite permitido")
    if valor_total > FRETE_CONFIG['MAX_VALOR']:
        raise ValidationError("Valor total excede o limite permitido")
    
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
            "insurance_value": valor_total,
            "reverse": False,
            "non_commercial": True
        }
    }
    
    for tentativa in range(FRETE_CONFIG['MAX_TENTATIVAS']):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, 
                    headers=headers, 
                    json=payload, 
                    timeout=FRETE_CONFIG['TIMEOUT']
                ) as response:
                    if response.status == 200:
                        try:
                            return await response.json()
                        except Exception as e:
                            logger.error(f"Erro ao decodificar resposta do Melhor Envio: {e}")
                            break
                    else:
                        logger.warning(
                            f"Falha ao cotar frete (tentativa {tentativa + 1}): "
                            f"status {response.status}"
                        )
                        
        except Exception as e:
            logger.error(f"Erro de conexão ao cotar frete (tentativa {tentativa + 1}): {e}")
            
    return []

@lru_cache(maxsize=128)
def preparar_produtos_para_frete(itens_carrinho: List[Dict]) -> List[Dict]:
    """Prepara a lista de produtos para cálculo de frete"""
    produtos = []
    defaults = settings.FRETE_DEFAULTS
    
    for item in itens_carrinho:
        try:
            produto = item['produto']
            variacao = item.get('variacao')
            
            peso = float(variacao.peso) if variacao and hasattr(variacao, 'peso') and variacao.peso else float(produto.peso or defaults['peso_padrao'])
            width = getattr(variacao, 'width', defaults['largura_padrao']) if variacao else defaults['largura_padrao']
            height = getattr(variacao, 'height', defaults['altura_padrao']) if variacao else defaults['altura_padrao']
            length = getattr(variacao, 'length', defaults['comprimento_padrao']) if variacao else defaults['comprimento_padrao']
            insurance_value = float(item['subtotal'])
            quantidade = int(item['quantidade'])
            
            # Validações
            if peso <= 0 or width <= 0 or height <= 0 or length <= 0:
                raise ValidationError("Dimensões inválidas")
            if insurance_value <= 0:
                raise ValidationError("Valor do seguro inválido")
            if quantidade <= 0:
                raise ValidationError("Quantidade inválida")
            
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

@cache_result(timeout=FRETE_CONFIG['CACHE_TIMEOUT'])
async def criar_envio_melhor_envio(pedido, token: str) -> Optional[Dict]:
    """Cria envio no Melhor Envio"""
    url = f"{settings.MELHOR_ENVIO_BASE_URL}/me/shipment"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = montar_payload_envio(pedido)
    
    for tentativa in range(FRETE_CONFIG['MAX_TENTATIVAS']):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, 
                    headers=headers, 
                    json=payload, 
                    timeout=FRETE_CONFIG['TIMEOUT']
                ) as response:
                    if response.status == 200:
                        try:
                            return await response.json()
                        except Exception as e:
                            logger.error(f"Erro ao decodificar resposta do Melhor Envio (envio): {e}")
                            break
                    else:
                        logger.warning(
                            f"Falha ao criar envio (tentativa {tentativa + 1}): "
                            f"status {response.status}"
                        )
                        
        except Exception as e:
            logger.error(f"Erro de conexão ao criar envio (tentativa {tentativa + 1}): {e}")
            
    return None

@lru_cache(maxsize=64)
def montar_payload_envio(pedido) -> Dict:
    """Monta payload do envio"""
    def safe_str(val: Any) -> str:
        return sanitizar_input(str(val) if val is not None else '')
    
    remetente = settings.REMETENTE_CONFIG
    
    return {
        "service": safe_str(getattr(pedido, 'frete_id', '')),
        "from": {
            "name": safe_str(remetente['name']),
            "phone": safe_str(remetente['phone']),
            "email": safe_str(remetente['email']),
            "document": safe_str(remetente['document']),
            "company_document": safe_str(remetente['company_document']),
            "state_register": safe_str(remetente['state_register']),
            "address": safe_str(remetente['address']),
            "complement": safe_str(remetente['complement']),
            "number": safe_str(remetente['number']),
            "district": safe_str(remetente['district']),
            "city": safe_str(remetente['city']),
            "state_abbr": safe_str(remetente['state_abbr']),
            "country_id": safe_str(remetente['country_id']),
            "postal_code": safe_str(remetente['postal_code'])
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

async def criar_payment_intent_stripe(user, pedido, itens_carrinho: List[Dict], frete_valor: Decimal, cupom=None) -> str:
    """Cria um PaymentIntent Stripe"""
    try:
        async with transaction.atomic():
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
            # Recalcula total
            subtotal = sum(item['produto'].preco_vigente() * item['quantidade'] for item in itens_carrinho)
            total = subtotal + Decimal(str(frete_valor or 0))
            desconto = Decimal('0.00')
            
            if cupom and hasattr(cupom, 'is_valido') and await sync_to_async(cupom.is_valido)(user):
                total_com_cupom = await sync_to_async(cupom.aplicar)(total)
                desconto = total - total_com_cupom
                total = total_com_cupom
                
            # Validação de estoque/preço
            for item in itens_carrinho:
                produto = item['produto']
                variacao = item.get('variacao')
                quantidade = item['quantidade']
                
                if variacao:
                    if not variacao.estoque >= quantidade:
                        raise EstoqueInsuficienteError(f"{produto.nome} - Estoque insuficiente para a variação selecionada.")
                else:
                    if hasattr(produto, 'variacoes') and await sync_to_async(produto.variacoes.exists)():
                        raise VariacaoInvalidaError(f"{produto.nome} exige seleção de variação.")
                    elif hasattr(produto, 'estoque') and produto.estoque < quantidade:
                        raise EstoqueInsuficienteError(f"{produto.nome}: estoque insuficiente")
                        
            amount = int(total * 100)
            if amount < 50:
                raise ValueError("O valor total do pedido é muito baixo para processamento.")
                
            # Cria PaymentIntent
            intent = await sync_to_async(stripe.PaymentIntent.create)(
                amount=amount,
                currency='brl',
                automatic_payment_methods={'enabled': True},
                metadata={
                    'user_id': user.id,
                    'pedido_id': pedido.id if pedido else '',
                }
            )
            
            await sync_to_async(LogAcao.objects.create)(
                usuario=user,
                acao="Criou PaymentIntent Stripe",
                detalhes=f"Intent ID: {intent.id} | Pedido ID: {pedido.id if pedido else ''}"
            )
            
            return intent.client_secret
            
    except (EstoqueInsuficienteError, VariacaoInvalidaError) as e:
        logger.error(f"Erro de validação ao criar PaymentIntent Stripe: {e}")
        await sync_to_async(LogAcao.objects.create)(
            usuario=user,
            acao="Falha de validação ao criar PaymentIntent Stripe",
            detalhes=f"Erro: {str(e)} | Pedido ID: {pedido.id if pedido else ''}"
        )
        raise
    except Exception as e:
        logger.error(f"Erro ao criar PaymentIntent Stripe: {e}")
        await sync_to_async(LogAcao.objects.create)(
            usuario=user,
            acao="Falha ao criar PaymentIntent Stripe",
            detalhes=f"Erro: {str(e)} | Pedido ID: {pedido.id if pedido else ''}"
        )
        raise CarrinhoError(f"Erro ao criar PaymentIntent Stripe: {str(e)}")

async def verificar_reserva_estoque(variacao_id: int, quantidade: int) -> bool:
    """Verifica se há estoque disponível para reserva"""
    try:
        variacao = await sync_to_async(ProdutoVariacao.objects.select_for_update().get)(
            id=variacao_id,
            ativo=True,
            produto__ativo=True
        )
        quantidade_reservada = await sync_to_async(ReservaEstoque.get_quantidade_reservada)(variacao_id)
        return variacao.estoque - quantidade_reservada >= quantidade
    except ProdutoVariacao.DoesNotExist:
        return False

async def criar_reserva_estoque(variacao_id: int, quantidade: int, sessao_id: str) -> Optional[ReservaEstoque]:
    """Cria uma reserva de estoque com controle de concorrência"""
    try:
        return await sync_to_async(ReservaEstoque.reservar_estoque)(
            variacao_id=variacao_id,
            quantidade=quantidade,
            sessao_id=sessao_id
        )
    except ValidationError:
        return None

async def confirmar_reserva_estoque(reserva_id: int, pedido_id: int) -> bool:
    """Confirma uma reserva de estoque para um pedido"""
    return await sync_to_async(ReservaEstoque.confirmar_reserva)(
        reserva_id=reserva_id,
        pedido_id=pedido_id
    )

async def liberar_reserva_estoque(variacao_id: int, sessao_id: str) -> None:
    """Libera uma reserva de estoque"""
    await sync_to_async(ReservaEstoque.objects.filter(
        variacao_id=variacao_id,
        sessao_id=sessao_id,
        status='P'
    ).update)(status='L')


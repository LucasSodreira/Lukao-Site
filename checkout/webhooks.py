import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from core.models import Pedido, ItemPedido
import json
from django.db import transaction
from django.views.decorators.http import require_POST

from asgiref.sync import sync_to_async
# from core.tasks import enviar_email_confirmacao_pedido, enviar_email_falha_pagamento
from core.models import LogAcao
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from core.models import ReservaEstoque, LogEstoque
import logging
from django.core.cache import cache
import hmac
import hashlib
from .utils import sanitizar_input, verificar_protecao_carrinho, get_cache_key, atualizar_protecao_carrinho
from user.models import Notificacao


logger = logging.getLogger(__name__)

@require_POST
@csrf_exempt
def stripe_webhook(request):
    """Processa eventos do webhook do Stripe"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        return HttpResponse(status=400)
        
    if event.type == 'payment_intent.succeeded':
        handle_payment_success(event.data.object)
    elif event.type == 'payment_intent.payment_failed':
        handle_payment_failure(event.data.object)
        
    return HttpResponse(status=200)
    
async def handle_payment_success(payment_intent):
    """Manipula pagamento bem-sucedido"""
    try:
        pedido = await sync_to_async(Pedido.objects.select_related(
            'endereco_entrega',
            'endereco_faturamento',
            'cupom'
        ).prefetch_related(
            'itens',
            'itens__variacao',
            'itens__variacao__produto'
        ).get)(payment_intent_id=payment_intent.id)
        
        # Confirma as reservas de estoque
        reservas = await sync_to_async(ReservaEstoque.objects.filter)(
            pedido=pedido,
            status='P'
        )
        for reserva in reservas:
            await sync_to_async(ReservaEstoque.confirmar_reserva)(reserva.id, pedido.id)
        
        # Atualiza status do pedido
        pedido.status = 'PA'  # Payment Approved
        await sync_to_async(pedido.save)()
        
        # Notifica o usuário
        await sync_to_async(Notificacao.objects.create)(
            usuario=pedido.usuario,
            titulo="Pagamento Aprovado",
            mensagem=f"Seu pedido #{pedido.codigo} foi aprovado e está sendo processado.",
            tipo='success'
        )
        
    except Pedido.DoesNotExist:
        logger.error(f"Pedido não encontrado para payment_intent: {payment_intent.id}")
    except Exception as e:
        logger.error(f"Erro ao processar pagamento: {str(e)}")
        

def handle_payment_failure(payment_intent):
    """Processa falha no pagamento"""
    try:
        pedido = Pedido.objects.select_related('user').get(
            payment_intent_id=payment_intent.id,
            status='P'
        )
        
        # Atualiza status do pedido
        pedido.status = 'PF'  # Payment Failed
        pedido.payment_status = 'failed'
        pedido.save()
        
        # Envia email de falha
        # enviar_email_falha_pagamento.delay(pedido.id)
        
    except Pedido.DoesNotExist:
        LogAcao.objects.create(
            usuario=None,
            acao="Pedido não encontrado",
            detalhes=f"Payment Intent ID: {payment_intent.id}"
        )
    except Exception as e:
        LogAcao.objects.create(
            usuario=None,
            acao="Erro ao processar falha de pagamento",
            detalhes=f"Erro: {str(e)} | Payment Intent ID: {payment_intent.id}"
        )

def criar_pedido_definitivo(request, payment_intent):
    with transaction.atomic():
        # Recupera dados do pedido temporário
        pedido_temp = request.session.get('pedido_temp')
        
        # Cria pedido definitivo
        pedido = Pedido.objects.create(
            usuario=pedido_temp['usuario'],
            status='PA',  # Pagamento Aprovado
            endereco_entrega=pedido_temp['endereco_entrega'],
            total=pedido_temp['total'],
            frete_valor=pedido_temp['frete_valor'],
            payment_intent_id=payment_intent['id']
        )
        
        # Cria itens do pedido
        for item in pedido_temp['itens']:
            ItemPedido.objects.create(
                pedido=pedido,
                produto=item['produto'],
                variacao=item.get('variacao'),
                quantidade=item['quantidade'],
                preco_unitario=item['subtotal'] / item['quantidade']
            )
            
        # Limpa dados temporários
        for key in list(request.session.keys()):
            if key.startswith('reserva_estoque_'):
                del request.session[key]
        del request.session['pedido_temp']

def verificar_assinatura_webhook(request):
    """Verifica a assinatura do webhook para garantir autenticidade"""
    assinatura = request.headers.get('X-Webhook-Signature')
    if not assinatura:
        return False
        
    payload = request.body
    assinatura_esperada = hmac.new(
        settings.WEBHOOK_SECRET_KEY.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(assinatura, assinatura_esperada)

@csrf_exempt
@require_http_methods(["POST"])
def webhook_pagamento(request):
    """Processa notificações de pagamento via webhook"""
    try:
        # Verifica assinatura do webhook
        if not verificar_assinatura_webhook(request):
            logger.warning("Tentativa de webhook não autenticado")
            return JsonResponse({'error': 'Assinatura inválida'}, status=401)
            
        # Sanitiza e valida dados do payload
        try:
            payload = json.loads(request.body)
            status = sanitizar_input(payload.get('status'))
            pedido_id = sanitizar_input(str(payload.get('pedido_id')))
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'error': 'Payload inválido'}, status=400)
            
        # Verifica proteção do carrinho
        pedido = Pedido.objects.get(id=pedido_id)
        carrinho = pedido.usuario.carrinho
        if not verificar_protecao_carrinho(request, carrinho.itens.all()):
            logger.warning(f"Tentativa de manipulação detectada no pedido {pedido_id}")
            return JsonResponse({'error': 'Tentativa de manipulação detectada'}, status=403)
            
        with transaction.atomic():
            # Confirma reservas e atualiza estoque
            for item in pedido.itens.all():
                if item.variacao:
                    # Confirma reservas pendentes
                    ReservaEstoque.objects.filter(
                        variacao=item.variacao,
                        pedido=pedido,
                        status='P'
                    ).update(status='C')
                    
                    # Atualiza estoque
                    item.variacao.estoque -= item.quantidade
                    item.variacao.save()
                    
                    # Registra log
                    LogEstoque.objects.create(
                        variacao=item.variacao,
                        quantidade=-item.quantidade,
                        motivo=f"Pagamento aprovado - Pedido {pedido.codigo}",
                        pedido=pedido
                    )
            
            pedido.status = 'PA'
            pedido.save()
            
            # Atualiza proteção após processar webhook
            atualizar_protecao_carrinho(request, carrinho.itens.all())
            
            # Invalida cache
            cache.delete(get_cache_key(request, 'carrinho'))
            
            return JsonResponse({'success': True})
            
    except Exception as e:
        logger.error(f"Erro no webhook de pagamento: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)

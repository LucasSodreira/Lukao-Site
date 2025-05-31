from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from core.models import ItemPedido, ProdutoVariacao, Pedido
from django.core.mail import send_mail
from django.contrib.auth.signals import user_logged_in
from user.models import Notificacao
from django.core.cache import cache
from django.conf import settings
import logging
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import F, Q
from functools import lru_cache
import asyncio
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

# Cache para variações
@lru_cache(maxsize=1000)
def get_variacao_cache(variacao_id):
    return ProdutoVariacao.objects.select_related('produto').get(id=variacao_id)

# Diminui o estoque da variação ao criar um item de pedido
@receiver(post_save, sender=ItemPedido)
def diminuir_estoque_variacao(sender, instance, created, **kwargs):
    if created:
        variacao = getattr(instance, 'variacao', None)
        if variacao:
            try:
                with transaction.atomic():
                    # Usar F() para atualização atômica
                    variacao_atual = ProdutoVariacao.objects.select_for_update().get(
                        id=variacao.id,
                        ativo=True
                    )
                    
                    if variacao_atual.estoque < instance.quantidade:
                        raise ValidationError("Estoque insuficiente para a variação selecionada.")
                    
                    # Atualização atômica do estoque
                    ProdutoVariacao.objects.filter(id=variacao.id).update(
                        estoque=F('estoque') - instance.quantidade
                    )
                    
                    # Invalidar caches em batch
                    cache_keys = [
                        f'variacao_{variacao.id}',
                        f'produto_{variacao.produto.id}',
                        'produtos_ativos',
                        'estoque_total'
                    ]
                    cache.delete_many(cache_keys)
                    
            except Exception as e:
                logger.error(f"Erro ao diminuir estoque: {str(e)}")
                raise

# Devolve o estoque da variação ao remover um item de pedido
@receiver(post_delete, sender=ItemPedido)
def devolver_estoque_variacao(sender, instance, **kwargs):
    variacao = getattr(instance, 'variacao', None)
    if variacao:
        try:
            with transaction.atomic():
                # Atualização atômica do estoque
                ProdutoVariacao.objects.filter(
                    id=variacao.id,
                    ativo=True
                ).update(
                    estoque=F('estoque') + instance.quantidade
                )
                
                # Invalidar caches em batch
                cache_keys = [
                    f'variacao_{variacao.id}',
                    f'produto_{variacao.produto.id}',
                    'produtos_ativos',
                    'estoque_total'
                ]
                cache.delete_many(cache_keys)
                
        except Exception as e:
            logger.error(f"Erro ao devolver estoque: {str(e)}")
            raise

# Gera SKU automaticamente para variações sem SKU
@receiver(pre_save, sender=ProdutoVariacao)
def gerar_sku_variacao(sender, instance, **kwargs):
    if not instance.sku and instance.pk and instance.atributos.exists():
        try:
            # Usar cache para SKUs gerados
            cache_key = f'sku_gerado_{instance.id}'
            sku = cache.get(cache_key)
            
            if not sku:
                sku = instance.gerar_sku_automatico()
                cache.set(cache_key, sku, timeout=3600)
                
            instance.sku = sku
            
        except Exception as e:
            logger.error(f"Erro ao gerar SKU: {str(e)}")
            raise

# Notifica usuário por e-mail e cria notificação ao mudar status do pedido
@receiver(pre_save, sender=Pedido)
def notificar_status_pedido(sender, instance, **kwargs):
    if instance.pk:
        try:
            # Usar select_related para otimizar query
            pedido_antigo = Pedido.objects.select_related(
                'usuario',
                'endereco'
            ).get(pk=instance.pk)
            
            if pedido_antigo.status != instance.status:
                # Rate limiting com cache distribuído
                cache_key = f'notificacao_pedido_{instance.id}'
                if not cache.get(cache_key):
                    # Preparar dados para notificação
                    notification_data = {
                        'subject': f"Seu pedido {instance.codigo} mudou de status",
                        'message': f"Novo status: {instance.get_status_display()}",
                        'email': instance.usuario.email,
                        'pedido_id': instance.id
                    }
                    
                    # Enviar notificação de forma assíncrona
                    asyncio.create_task(send_notification_async(notification_data))
                    
                    # Criar notificação em batch
                    if not Notificacao.objects.filter(
                        Q(usuario=instance.usuario) &
                        Q(mensagem__icontains=instance.codigo) &
                        Q(lida=False) &
                        Q(created_at__gte=timezone.now() - timezone.timedelta(minutes=5))
                    ).exists():
                        Notificacao.objects.create(
                            usuario=instance.usuario,
                            mensagem=f"Status do pedido {instance.codigo} alterado para: {instance.get_status_display()}"
                        )
                    
                    cache.set(cache_key, True, timeout=300)
                    
        except Exception as e:
            logger.error(f"Erro ao notificar status do pedido: {str(e)}")

# Função assíncrona para enviar notificações
async def send_notification_async(notification_data):
    try:
        if notification_data['email'] and '@' in notification_data['email']:
            await sync_to_async(send_mail)(
                subject=notification_data['subject'],
                message=notification_data['message'],
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[notification_data['email']],
                fail_silently=False,
            )
    except Exception as e:
        logger.error(f"Erro ao enviar notificação assíncrona: {str(e)}")

# Migra o carrinho da sessão para o banco ao login
@receiver(user_logged_in)
def migrar_carrinho_ao_login(sender, user, request, **kwargs):
    if hasattr(request, "user") and request.user.is_authenticated:
        try:
            from checkout.utils import migrar_carrinho_sessao_para_banco
            with transaction.atomic():
                # Usar bulk_create para melhor performance
                migrar_carrinho_sessao_para_banco(request)
                
                # Invalidar caches relacionados
                cache_keys = [
                    f'carrinho_{request.user.id}',
                    'carrinhos_ativos',
                    f'itens_carrinho_{request.user.id}'
                ]
                cache.delete_many(cache_keys)
                
        except Exception as e:
            logger.error(f"Erro ao migrar carrinho: {str(e)}")
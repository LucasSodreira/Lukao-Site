from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.db import transaction
from django.core.cache import cache
from django.conf import settings
from core.models import Pedido, LogAcao, ReservaEstoque, LogEstoque
import logging
from functools import wraps


# Configuração de logging
logger = logging.getLogger(__name__)

# Constantes
EMAIL_CONFIG = {
    'MAX_TENTATIVAS': 3,
    'TIMEOUT': 10,
    'CACHE_TIMEOUT': 3600,
    'RATE_LIMIT': 5,  # emails por minuto
}

def get_cache_key(prefix: str, *args) -> str:
    """Gera chave de cache segura baseada nos argumentos"""
    key_parts = [prefix] + [str(arg) for arg in args]
    return '_'.join(key_parts)

def rate_limit_email(func):
    """Decorator para limitar envio de emails"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        user_id = kwargs.get('instance').usuario.id
        key = get_cache_key('email_rate', user_id)
        current = cache.get(key, 0)
        
        if current >= EMAIL_CONFIG['RATE_LIMIT']:
            logger.warning(f"Rate limit de email excedido para usuário {user_id}")
            return
            
        cache.set(key, current + 1, 60)
        return func(*args, **kwargs)
    return wrapper

@receiver(pre_save, sender=Pedido)
@rate_limit_email
def notificar_status_pedido(sender, instance: Pedido, **kwargs):
    """Envia e-mail ao usuário quando o status do pedido muda."""
    if not instance.pk:
        return
        
    try:
        pedido_antigo = Pedido.objects.select_related('usuario').get(pk=instance.pk)
        if pedido_antigo.status != instance.status:
            # Verifica se já enviou email recentemente
            cache_key = get_cache_key('email_status', instance.pk, instance.status)
            if cache.get(cache_key):
                return
                
            # Valida email do usuário
            if not instance.usuario.email or '@' not in instance.usuario.email:
                logger.warning(f"Email inválido para usuário {instance.usuario.id}")
                return
                
            try:
                with transaction.atomic():
                    send_mail(
                        subject=f"Seu pedido {instance.codigo} mudou de status",
                        message=f"Novo status: {instance.get_status_display()}",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[instance.usuario.email],
                        fail_silently=True,
                    )
                    
                    # Registra sucesso
                    LogAcao.objects.create(
                        usuario=instance.usuario,
                        acao="Enviou e-mail de status do pedido",
                        detalhes=f"Pedido {instance.codigo} | Status: {instance.status}"
                    )
                    
                    # Cache para evitar spam
                    cache.set(cache_key, True, EMAIL_CONFIG['CACHE_TIMEOUT'])
                    
            except Exception as e:
                logger.error(f"Erro ao enviar email: {str(e)}")
                LogAcao.objects.create(
                    usuario=instance.usuario,
                    acao="Falha ao enviar e-mail de status do pedido",
                    detalhes=f"Pedido {instance.codigo} | Erro: {str(e)}"
                )
    except Pedido.DoesNotExist:
        logger.error(f"Pedido {instance.pk} não encontrado")
    except Exception as e:
        logger.error(f"Erro ao processar notificação: {str(e)}")

@receiver(post_save, sender=Pedido)
def atualizar_estoque_pedido(sender, instance: Pedido, created: bool, **kwargs):
    """Atualiza estoque e reservas quando um pedido é criado ou atualizado"""
    if created or instance.status in ['PA', 'E', 'T', 'C']:
        with transaction.atomic():
            for item in instance.itens.all():
                if item.variacao:
                    # Confirma reservas pendentes
                    ReservaEstoque.objects.filter(
                        variacao=item.variacao,
                        pedido=instance,
                        status='P'
                    ).update(status='C')
                    
                    # Atualiza estoque
                    item.variacao.estoque -= item.quantidade
                    item.variacao.save()
                    
                    # Registra log
                    LogEstoque.objects.create(
                        variacao=item.variacao,
                        quantidade=-item.quantidade,
                        motivo=f"Pedido {instance.codigo}",
                        pedido=instance
                    )

@receiver(pre_save, sender=Pedido)
def devolver_estoque_cancelado(sender, instance: Pedido, **kwargs):
    """Libera reservas e devolve estoque quando um pedido é cancelado"""
    if instance.pk:  # Se não é uma nova instância
        try:
            pedido_antigo = Pedido.objects.get(pk=instance.pk)
            if pedido_antigo.status not in ['X', 'D'] and instance.status in ['X', 'D']:
                with transaction.atomic():
                    for item in instance.itens.all():
                        if item.variacao:
                            # Libera reservas associadas ao pedido
                            ReservaEstoque.objects.filter(
                                variacao=item.variacao,
                                pedido=instance,
                                status='C'
                            ).update(status='L')
                            
                            # Devolve estoque
                            item.variacao.estoque += item.quantidade
                            item.variacao.save()
                            
                            # Registra log
                            LogEstoque.objects.create(
                                variacao=item.variacao,
                                quantidade=item.quantidade,
                                motivo=f"Devolução - Pedido {instance.codigo} cancelado",
                                pedido=instance
                            )
        except Pedido.DoesNotExist:
            pass
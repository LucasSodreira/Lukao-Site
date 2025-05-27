from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from core.models import Pedido, ProdutoVariacao, LogAcao

@receiver(pre_save, sender=Pedido)
def notificar_status_pedido(sender, instance, **kwargs):
    """Envia e-mail ao usuário quando o status do pedido muda. Para produção, use Celery para envio assíncrono."""
    if instance.pk:
        pedido_antigo = Pedido.objects.get(pk=instance.pk)
        if pedido_antigo.status != instance.status:
            try:
                send_mail(
                    subject=f"Seu pedido {instance.codigo} mudou de status",
                    message=f"Novo status: {instance.get_status_display()}",
                    from_email="loja@exemplo.com",
                    recipient_list=[instance.usuario.email],
                    fail_silently=True,
                )
            except Exception as e:
                LogAcao.objects.create(
                    usuario=instance.usuario,
                    acao="Falha ao enviar e-mail de status do pedido",
                    detalhes=f"Pedido {instance.codigo} | Erro: {str(e)}"
                )

@receiver(post_save, sender=Pedido)
def atualizar_estoque_pedido(sender, instance, created, **kwargs):
    """Ao criar pedido, diminui estoque das variações dos itens."""
    if created and instance.status == "P":
        for item in instance.itens.select_related('variacao').all():
            variacao = getattr(item, 'variacao', None)
            if variacao:
                try:
                    variacao.diminuir_estoque(item.quantidade)
                except Exception as e:
                    LogAcao.objects.create(
                        usuario=instance.usuario,
                        acao="Falha ao diminuir estoque",
                        detalhes=f"Pedido {instance.codigo} | Variação {variacao.id} | Erro: {str(e)}"
                    )

@receiver(pre_save, sender=Pedido)
def devolver_estoque_cancelado(sender, instance, **kwargs):
    """Ao cancelar pedido, devolve estoque das variações dos itens."""
    if instance.pk:
        pedido_antigo = Pedido.objects.get(pk=instance.pk)
        if pedido_antigo.status != "X" and instance.status == "X":
            for item in instance.itens.select_related('variacao').all():
                variacao = getattr(item, 'variacao', None)
                if variacao:
                    try:
                        variacao.aumentar_estoque(item.quantidade)
                    except Exception as e:
                        LogAcao.objects.create(
                            usuario=instance.usuario,
                            acao="Falha ao devolver estoque",
                            detalhes=f"Pedido {instance.codigo} | Variação {variacao.id} | Erro: {str(e)}"
                        )
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from core.models import Pedido, ProdutoVariacao

@receiver(pre_save, sender=Pedido)
def notificar_status_pedido(sender, instance, **kwargs):
    if instance.pk:
        pedido_antigo = Pedido.objects.get(pk=instance.pk)
        if pedido_antigo.status != instance.status:
            send_mail(
                subject=f"Seu pedido {instance.codigo} mudou de status",
                message=f"Novo status: {instance.get_status_display()}",
                from_email="loja@exemplo.com",
                recipient_list=[instance.usuario.email],
                fail_silently=True,
            )

@receiver(post_save, sender=Pedido)
def atualizar_estoque_pedido(sender, instance, created, **kwargs):
# Ao criar pedido, diminui estoque das variações
    if created and instance.status == "P":
        for item in instance.itens.all():
            try:
                variacao = ProdutoVariacao.objects.get(
                    produto=item.produto,
                    tamanho=item.tamanho
                )
                variacao.estoque = max(0, variacao.estoque - item.quantidade)
                variacao.save(update_fields=['estoque'])
            except ProdutoVariacao.DoesNotExist:
                pass

@receiver(pre_save, sender=Pedido)
def devolver_estoque_cancelado(sender, instance, **kwargs):
    if instance.pk:
        pedido_antigo = Pedido.objects.get(pk=instance.pk)
        if pedido_antigo.status != "X" and instance.status == "X":
            for item in instance.itens.all():
                try:
                    variacao = ProdutoVariacao.objects.get(
                        produto=item.produto,
                        tamanho=item.tamanho
                    )
                    variacao.estoque += item.quantidade
                    variacao.save(update_fields=['estoque'])
                except ProdutoVariacao.DoesNotExist:
                    pass
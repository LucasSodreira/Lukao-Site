from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db import models
from django.db.models import Sum
from core.models import AvaliacaoProduto, ItemPedido, ProdutoVariacao
from uuid import uuid4
from django.core.mail import send_mail
from core.models import Pedido

@receiver([post_save, post_delete], sender=AvaliacaoProduto)
def atualizar_avaliacao_produto(sender, instance, **kwargs):
    produto = instance.produto
    avaliacoes = produto.avaliacoes.all()
    media = avaliacoes.aggregate(models.Avg('nota'))['nota__avg'] or 0
    produto.avaliacao = round(media, 2)
    produto.save(update_fields=['avaliacao'])

@receiver(post_save, sender=ItemPedido)
def diminuir_estoque_variacao(sender, instance, created, **kwargs):
    if created:
        try:
            variacao = ProdutoVariacao.objects.get(
                produto=instance.produto,
                tamanho=instance.tamanho
            )
            variacao.estoque = max(0, variacao.estoque - instance.quantidade)
            variacao.save(update_fields=['estoque'])
        except ProdutoVariacao.DoesNotExist:
            pass

@receiver(post_delete, sender=ItemPedido)
def devolver_estoque_variacao(sender, instance, **kwargs):
    try:
        variacao = ProdutoVariacao.objects.get(
            produto=instance.produto,
            tamanho=instance.tamanho
        )
        variacao.estoque += instance.quantidade
        variacao.save(update_fields=['estoque'])
    except ProdutoVariacao.DoesNotExist:
        pass


@receiver(post_save, sender=ProdutoVariacao)
def atualizar_estoque_produto(sender, instance, **kwargs):
    produto = instance.produto
    estoque_total = produto.variacoes.aggregate(total=Sum('estoque'))['total'] or 0
    produto.estoque = estoque_total
    produto.save(update_fields=['estoque'])


@receiver(pre_save, sender=ProdutoVariacao)
def gerar_sku_variacao(sender, instance, **kwargs):
    if not instance.sku:
        instance.sku = f"{instance.produto.id}-{instance.cor.id}-{instance.tamanho}-{uuid4().hex[:6].upper()}"
        
        
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
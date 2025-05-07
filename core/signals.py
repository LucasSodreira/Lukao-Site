from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db import models
from django.db.models import Sum
from core.models import AvaliacaoProduto, ItemPedido, ProdutoVariacao, Pedido
from uuid import uuid4
from django.core.mail import send_mail, BadHeaderError
from django.contrib.auth.signals import user_logged_in
from user.models import Notificacao

# Atualiza a média de avaliações do produto sempre que uma avaliação é criada, alterada ou removida
@receiver([post_save, post_delete], sender=AvaliacaoProduto)
def atualizar_avaliacao_produto(sender, instance, **kwargs):
    produto = instance.produto
    avaliacoes = produto.avaliacoes.all()
    media = avaliacoes.aggregate(media=Sum('nota'))['media'] or 0
    total = avaliacoes.count()
    produto.avaliacao = round(media / total, 2) if total > 0 else 0
    produto.save(update_fields=['avaliacao'])

# Diminui o estoque da variação ao criar um item de pedido
@receiver(post_save, sender=ItemPedido)
def diminuir_estoque_variacao(sender, instance, created, **kwargs):
    if created:
        try:
            variacao = ProdutoVariacao.objects.get(
                produto=instance.produto,
                tamanho=instance.tamanho
            )
            variacao.diminuir_estoque(instance.quantidade)
        except ProdutoVariacao.DoesNotExist:
            pass
        except ValueError as e:
            # Log do erro pode ser adicionado aqui
            pass

# Devolve o estoque da variação ao remover um item de pedido
@receiver(post_delete, sender=ItemPedido)
def devolver_estoque_variacao(sender, instance, **kwargs):
    try:
        variacao = ProdutoVariacao.objects.get(
            produto=instance.produto,
            tamanho=instance.tamanho
        )
        variacao.aumentar_estoque(instance.quantidade)
    except ProdutoVariacao.DoesNotExist:
        pass

# Atualiza o estoque total do produto sempre que uma variação é salva
@receiver(post_save, sender=ProdutoVariacao)
def atualizar_estoque_produto(sender, instance, **kwargs):
    produto = instance.produto
    estoque_total = produto.variacoes.aggregate(total=Sum('estoque'))['total'] or 0
    produto.estoque = estoque_total
    produto.save(update_fields=['estoque'])

# Gera SKU automaticamente para variações sem SKU
@receiver(pre_save, sender=ProdutoVariacao)
def gerar_sku_variacao(sender, instance, **kwargs):
    if not instance.sku:
        instance.sku = f"{instance.produto.id}-{instance.cor.id}-{instance.tamanho}-{uuid4().hex[:6].upper()}"

# Notifica usuário por e-mail e cria notificação ao mudar status do pedido
@receiver(pre_save, sender=Pedido)
def notificar_status_pedido(sender, instance, **kwargs):
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
                if not Notificacao.objects.filter(usuario=instance.usuario, mensagem__icontains=instance.codigo, lida=False).exists():
                    Notificacao.objects.create(
                        usuario=instance.usuario,
                        mensagem=f"Status do pedido {instance.codigo} alterado para: {instance.get_status_display()}"
                    )
            except BadHeaderError:
                pass
            except Exception:
                pass

# Migra o carrinho da sessão para o banco ao login
@receiver(user_logged_in)
def migrar_carrinho_ao_login(sender, user, request, **kwargs):
    if hasattr(request, "user") and request.user.is_authenticated:
        from checkout.utils import migrar_carrinho_sessao_para_banco
        migrar_carrinho_sessao_para_banco(request)
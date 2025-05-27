from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from core.models import ItemPedido, ProdutoVariacao, Pedido
from django.core.mail import send_mail, BadHeaderError
from django.contrib.auth.signals import user_logged_in
from user.models import Notificacao

# Diminui o estoque da variação ao criar um item de pedido
@receiver(post_save, sender=ItemPedido)
def diminuir_estoque_variacao(sender, instance, created, **kwargs):
    if created:
        variacao = getattr(instance, 'variacao', None)
        if variacao:
            try:
                if variacao.estoque < instance.quantidade:
                    raise ValueError("Estoque insuficiente para a variação selecionada.")
                variacao.estoque -= instance.quantidade
                variacao.save(update_fields=["estoque"])
            except Exception as e:
                # Log do erro pode ser adicionado aqui
                pass

# Devolve o estoque da variação ao remover um item de pedido
@receiver(post_delete, sender=ItemPedido)
def devolver_estoque_variacao(sender, instance, **kwargs):
    variacao = getattr(instance, 'variacao', None)
    if variacao:
        variacao.estoque += instance.quantidade
        variacao.save(update_fields=["estoque"])

# Gera SKU automaticamente para variações sem SKU (usa lógica do model)
@receiver(pre_save, sender=ProdutoVariacao)
def gerar_sku_variacao(sender, instance, **kwargs):
    # Só tenta gerar SKU se a variação já tem ID (foi salva antes) e tem atributos
    if not instance.sku and instance.pk and instance.atributos.exists():
        instance.gerar_sku_automatico()

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
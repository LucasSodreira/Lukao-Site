from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out
from user.models import Notificacao
from core.models import Pedido
from .models import LogAtividadeUsuario

User = get_user_model()

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@receiver(pre_save, sender=User)
def notificar_alteracao_usuario(sender, instance, **kwargs):
    if instance.pk:
        user_antigo = User.objects.get(pk=instance.pk)
        if (
            user_antigo.email != instance.email or
            user_antigo.first_name != instance.first_name or
            user_antigo.last_name != instance.last_name
        ):
            send_mail(
                subject="Seus dados foram alterados",
                message="Seus dados de cadastro foram atualizados com sucesso.",
                from_email="loja@exemplo.com",
                recipient_list=[instance.email],
                fail_silently=True,
            )

@receiver(pre_save, sender=Pedido)
def notificar_status_pedido(sender, instance, **kwargs):
    if instance.pk:
        pedido_antigo = Pedido.objects.get(pk=instance.pk)
        if pedido_antigo.status != instance.status:
            Notificacao.objects.create(
                usuario=instance.usuario,
                mensagem=f"Status do pedido {instance.codigo} alterado para: {instance.get_status_display()}"
            )

@receiver(user_logged_in)
def registrar_login(sender, request, user, **kwargs):
    LogAtividadeUsuario.objects.create(
        usuario=user,
        tipo='login',
        ip=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )

@receiver(user_logged_out)
def registrar_logout(sender, request, user, **kwargs):
    LogAtividadeUsuario.objects.create(
        usuario=user,
        tipo='logout',
        ip=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
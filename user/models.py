from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Perfil(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    cpf = models.CharField(max_length=14, blank=True, null=True)
    telefone = models.CharField(max_length=15, blank=True, null=True)
    data_nascimento = models.DateField(blank=True, null=True)
    sexo = models.CharField(
        max_length=10, blank=True, null=True,
        choices=[('M', 'Masculino'), ('F', 'Feminino'), ('O', 'Outro')]
    )
    endereco_padrao = models.ForeignKey(
        'core.Endereco', on_delete=models.SET_NULL,
        blank=True, null=True, related_name='usuarios_padrao'
    )
    newsletter = models.BooleanField(default=False, verbose_name="Aceita receber promoções?")
    data_cadastro = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.usuario.get_full_name() or self.usuario.username

class Notificacao(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notificacoes')
    mensagem = models.CharField(max_length=255)
    lida = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.usuario.username}: {self.mensagem[:30]}"
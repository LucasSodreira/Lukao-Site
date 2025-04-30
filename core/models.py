from django.db import models
from django.core.validators import MinValueValidator
from django.core.validators import RegexValidator
from django.conf import settings
from django.db.models import Sum, F
from django.core.validators import MinLengthValidator
class Categoria(models.Model):
    nome = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nome


class Produto(models.Model):
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True, null=True)
    preco = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    categoria = models.ForeignKey(
        Categoria, on_delete=models.SET_NULL, null=True, related_name="produtos"
    )
    estoque = models.PositiveIntegerField(default=0)
    tamanhos = models.CharField(max_length=50, blank=True, null=True)
    imagem = models.ImageField(upload_to="produtos/", blank=True, null=True)

    def __str__(self):
        return f"{self.nome} (R${self.preco})"

    def diminuir_estoque(self, quantidade):
        """Diminui o estoque do produto e salva no banco"""
        if self.estoque >= quantidade:
            self.estoque -= quantidade
            self.save()
            return True
        return False

    def aumentar_estoque(self, quantidade):
        """Aumenta o estoque do produto e salva no banco"""
        self.estoque += quantidade
        self.save()
        
    TAMANHOS = [
        ('PP', 'Extra Pequeno'),
        ('P', 'Pequeno'),
        ('M', 'Médio'),
        ('G', 'Grande'),
        ('GG', 'Extra Grande'),
        ('XG', 'Tamanho Extra'),
    ]
    
    tamanhos_disponiveis = models.CharField(
        max_length=50,
        blank=True,
        help_text="Tamanhos disponíveis separados por vírgula (ex: P,M,G)"
    )

    def get_tamanhos_disponiveis(self):
        if self.tamanhos_disponiveis:
            return [t.strip() for t in self.tamanhos_disponiveis.split(',')]
        return []




class Endereco(models.Model):
    ESTADO_CHOICES = [
        ("AC", "Acre"),
        ("AL", "Alagoas"),
        ("AP", "Amapá"),
        ("AM", "Amazonas"),
        ("BA", "Bahia"),
        ("CE", "Ceará"),
        ("DF", "Distrito Federal"),
        ("ES", "Espírito Santo"),
        ("GO", "Goiás"),
        ("MA", "Maranhão"),
        ("MT", "Mato Grosso"),
        ("MS", "Mato Grosso do Sul"),
        ("MG", "Minas Gerais"),
        ("PA", "Pará"),
        ("PB", "Paraíba"),
        ("PR", "Paraná"),
        ("PE", "Pernambuco"),
        ("PI", "Piauí"),
        ("RJ", "Rio de Janeiro"),
        ("RN", "Rio Grande do Norte"),
        ("RS", "Rio Grande do Sul"),
        ("RO", "Rondônia"),
        ("RR", "Roraima"),
        ("SC", "Santa Catarina"),
        ("SP", "São Paulo"),
        ("SE", "Sergipe"),
        ("TO", "Tocantins"),
    ]

    nome_completo = models.CharField(
        max_length=100, verbose_name="Nome Completo", validators=[MinLengthValidator(3)]
    )

    telefone = models.CharField(
        max_length=15,
        validators=[
            RegexValidator(
                regex=r"^\(\d{2}\) \d{4,5}-\d{4}$",
                message="Telefone deve estar no formato (99) 99999-9999",
            )
        ],
    )

    rua = models.CharField(max_length=200, verbose_name="Logradouro")

    numero = models.CharField(max_length=20, verbose_name="Número")

    complemento = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Complemento"
    )

    bairro = models.CharField(max_length=100, verbose_name="Bairro")

    cep = models.CharField(
        max_length=9,
        validators=[
            RegexValidator(
                regex=r"^\d{5}-\d{3}$", message="CEP deve estar no formato 12345-678"
            )
        ],
    )

    cidade = models.CharField(max_length=100)

    estado = models.CharField(max_length=2, choices=ESTADO_CHOICES, verbose_name="UF")

    pais = models.CharField(max_length=50, default="Brasil")

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enderecos",
        null=True,
        blank=True,
    )

    principal = models.BooleanField(default=False, verbose_name="Endereço Principal")

    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")

    atualizado_em = models.DateTimeField(
        auto_now=True, verbose_name="Última Atualização"
    )

    class Meta:
        verbose_name = "Endereço"
        verbose_name_plural = "Endereços"
        ordering = ["-principal", "-criado_em"]

    def __str__(self):
        return f"{self.nome_completo} - {self.rua}, {self.numero}, {self.cidade}/{self.estado}"

    def save(self, *args, **kwargs):
        # Garante que só tenha um endereço principal por usuário
        if self.principal and self.usuario:
            Endereco.objects.filter(usuario=self.usuario, principal=True).update(
                principal=False
            )
        super().save(*args, **kwargs)


class Pedido(models.Model):
    STATUS_CHOICES = [
        ("P", "Pendente"),
        ("E", "Enviado"),
        ("C", "Concluído"),
        ("X", "Cancelado"),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pedidos",
        null=True,
        blank=True,
    )
    data_criacao = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default="P")
    endereco_entrega = models.ForeignKey(Endereco, on_delete=models.SET_NULL, null=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ["-data_criacao"]

    def __str__(self):
        return f"Pedido #{self.id} - {self.get_status_display()}"

    def calcular_total(self):
        """Calcula o total do pedido somando todos os itens"""
        return (
            self.itens.aggregate(total=Sum(F("quantidade") * F("preco_unitario")))[
                "total"
            ]
            or 0
        )

    def atualizar_estoque(self, operacao="diminuir"):
        """
        Atualiza o estoque dos produtos conforme os itens do pedido
        operacao: 'diminuir' (padrão) ou 'aumentar' (para cancelamentos)
        """
        for item in self.itens.all():
            if operacao == "diminuir":
                item.produto.diminuir_estoque(item.quantidade)
            else:
                item.produto.aumentar_estoque(item.quantidade)

    def save(self, *args, **kwargs):
        """Sobrescreve o save para calcular o total automaticamente"""
        if not self.pk:  # Se for um novo pedido
            super().save(*args, **kwargs)  # Salva primeiro para ter um ID
        self.total = self.calcular_total()
        super().save(*args, **kwargs)

        # Se o pedido foi concluído ou cancelado, atualiza o estoque
        if self.status == "C":
            self.atualizar_estoque("diminuir")
        elif self.status == "X":
            self.atualizar_estoque("aumentar")


class ItemPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="itens")
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.PositiveIntegerField(default=1)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    tamanho = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        tamanho = f" ({self.tamanho})" if self.tamanho else ""
        return f"{self.quantidade}x {self.produto.nome}{tamanho} (R${self.preco_unitario})"

    def save(self, *args, **kwargs):
        """Sobrescreve o save para definir o preço unitário e atualizar o total do pedido"""
        if not self.preco_unitario:  # Se o preço não foi definido
            self.preco_unitario = self.produto.preco
        super().save(*args, **kwargs)
        self.pedido.save()  # Atualiza o total do pedido

    def delete(self, *args, **kwargs):
        """Sobrescreve o delete para atualizar o total do pedido"""
        pedido = self.pedido
        super().delete(*args, **kwargs)
        pedido.save()  # Atualiza o total do pedido

from django.db import models
from django.core.validators import (
    MinValueValidator,
    RegexValidator,
    MinLengthValidator,
)
from django.conf import settings
from django.db.models import Sum, F
from django.core.exceptions import ValidationError
from uuid import uuid4


class Categoria(models.Model):
    nome = models.CharField(max_length=255)

    def __str__(self):
        return self.nome


class Cor(models.Model):
    nome = models.CharField(max_length=50, unique=True)
    valor_css = models.CharField(max_length=50, help_text="Valor para background-color no CSS (ex: 'red', '#ff0000')")

    def __str__(self):
        return self.nome

class Marca(models.Model):
    nome = models.CharField(max_length=50, unique=True)
    descricao = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nome

class Produto(models.Model):
    nome = models.CharField(max_length=255)
    descricao = models.TextField(blank=True, null=True)
    preco = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    preco_original = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    desconto = models.IntegerField(null=True, blank=True)
    categoria = models.ForeignKey(
        Categoria, on_delete=models.CASCADE, related_name='produtos'
    )
    tamanho = models.CharField(max_length=50)
    peso = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True,
        help_text="Peso do produto em kg"
    )
    width = models.PositiveIntegerField(
        null=True, blank=True, help_text="Largura em cm"
    )
    height = models.PositiveIntegerField(
        null=True, blank=True, help_text="Altura em cm"
    )
    length = models.PositiveIntegerField(
        null=True, blank=True, help_text="Comprimento em cm"
    )
    estoque = models.PositiveIntegerField(default=0)
    imagem = models.ImageField(upload_to="produtos/", default="produtos/default.jpg")
    avaliacao = models.FloatField(default=0.0)
    sku = models.CharField(max_length=50, unique=True, blank=True, null=True, help_text="SKU do produto")
    codigo_barras = models.CharField(max_length=50, blank=True, null=True, help_text="Código de barras")
    seo_title = models.CharField(max_length=70, blank=True, null=True)
    seo_description = models.CharField(max_length=160, blank=True, null=True)
    marca = models.ForeignKey(
        Marca, on_delete=models.CASCADE, related_name='produtos', null=True, blank=True
    )
    tags = models.ManyToManyField('Tag', blank=True, related_name='produtos')

    CATEGORY_CHOICES = [
        ('T-Shirts', 'T-Shirts'),
        ('Shorts', 'Shorts'),
        ('Hoodie', 'Hoodie'),
        ('Jeans', 'Jeans'),
    ]
    SIZE_CHOICES = [
        ('X-Small', 'PP'),
        ('Small', 'P'),
        ('Medium', 'M'),
        ('Large', 'G'),
        ('X-Large', 'GG'),
        ('XX-Large', 'XG'),
    ]
    DRESS_STYLE_CHOICES = [
        ('Casual', 'Casual'),
        ('Formal', 'Formal'),
        ('Party', 'Festa'),
        ('Sport', 'Esporte'),
        ('Beach', 'Praia'),
        ('Gym', 'Academia'),
    ]

    tamanhos_disponiveis = models.CharField(
        max_length=50,
        blank=True,
        help_text="Tamanhos disponíveis separados por vírgula (ex: P,M,G)",
    )

    def __str__(self):
        return f"{self.nome} (R${self.preco})"

    def get_tamanhos_disponiveis(self):
        if self.tamanhos_disponiveis:
            return [t.strip() for t in self.tamanhos_disponiveis.split(",")]
        return []

    def clean(self):
        """Validação no nível do model"""
        if self.estoque < 0:
            raise ValidationError("O estoque não pode ser negativo")

    def diminuir_estoque(self, quantidade):
        """Método seguro para diminuir estoque"""
        if quantidade <= 0:
            raise ValueError("Quantidade deve ser positiva")
        if self.estoque < quantidade:
            raise ValueError(f"Estoque insuficiente (disponível: {self.estoque})")
        self.estoque -= quantidade
        self.save()

    def aumentar_estoque(self, quantidade):
        """Aumenta o estoque do produto e salva no banco"""
        self.estoque += quantidade
        self.save()

    def save(self, *args, **kwargs):
        if self.preco_original and self.preco_original > self.preco:
            self.desconto = int((1 - (self.preco / self.preco_original)) * 100)
        super().save(*args, **kwargs)


class ProdutoCor(models.Model):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='cores')
    cor = models.ForeignKey(Cor, on_delete=models.CASCADE)
    estoque = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('produto', 'cor')

    def __str__(self):
        return f"{self.produto.nome} - {self.cor.nome} ({self.estoque})"


class ProdutoVariacao(models.Model):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='variacoes')
    cor = models.ForeignKey(Cor, on_delete=models.CASCADE)
    tamanho = models.CharField(max_length=20, choices=Produto.SIZE_CHOICES)
    estoque = models.PositiveIntegerField(default=0)
    sku = models.CharField(max_length=50, unique=True, blank=True, null=True)
    peso = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True,
        help_text="Peso da variação em kg"
    )
    width = models.PositiveIntegerField(
        null=True, blank=True, help_text="Largura em cm"
    )
    height = models.PositiveIntegerField(
        null=True, blank=True, help_text="Altura em cm"
    )
    length = models.PositiveIntegerField(
        null=True, blank=True, help_text="Comprimento em cm"
    )

    class Meta:
        unique_together = ('produto', 'cor', 'tamanho')

    def __str__(self):
        return f"{self.produto.nome} - {self.cor.nome} - {self.tamanho}"


class ImagemProduto(models.Model):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='imagens')
    imagem = models.ImageField(upload_to="produtos/galeria/")
    destaque = models.BooleanField(default=False)

    def __str__(self):
        return f"Imagem de {self.produto.nome}"


class AvaliacaoProduto(models.Model):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='avaliacoes')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    nota = models.PositiveSmallIntegerField()
    comentario = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.usuario} - {self.produto.nome} ({self.nota})"


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
        ("T", "Em Transporte"),
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
    codigo = models.CharField(
        max_length=10,
        unique=True,
        editable=False,
        verbose_name="Código do Pedido"
    )
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default="P")
    endereco_entrega = models.ForeignKey(
        Endereco, on_delete=models.SET_NULL, null=True
    )
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    codigo_rastreamento = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Código de Rastreio"
    )
    metodo_pagamento = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Método de Pagamento"
    )
    data_criacao = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data_criacao"]

    def __str__(self):
        return f"#{self.codigo} - {self.get_status_display()}"

    def calcular_total(self):
        return self.itens.aggregate(
            total=Sum(F("quantidade") * F("preco_unitario"))
        )["total"] or 0

    def atualizar_estoque(self, operacao="diminuir"):
        for item in self.itens.all():
            # Supondo que ItemPedido tenha um campo 'variacao'
            variacao = getattr(item, 'variacao', None)
            if variacao:
                if operacao == "diminuir":
                    variacao.estoque -= item.quantidade
                else:
                    variacao.estoque += item.quantidade
                variacao.save(update_fields=['estoque'])
            else:
                # fallback para produto simples
                if operacao == "diminuir":
                    item.produto.diminuir_estoque(item.quantidade)
                else:
                    item.produto.aumentar_estoque(item.quantidade)

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = str(uuid4()).split("-")[0].upper()
        creating = self.pk is None
        status_antigo = None
        if not creating:
            status_antigo = Pedido.objects.get(pk=self.pk).status
        super().save(*args, **kwargs)
        if not creating:
            self.total = self.calcular_total()
            super().save(update_fields=['total'])
            # Se mudou de C (concluído) para X (cancelado), devolve estoque
            if status_antigo == "C" and self.status == "X":
                self.atualizar_estoque("aumentar")
            # Se mudou de outro status para C, diminui estoque
            elif status_antigo != "C" and self.status == "C":
                self.atualizar_estoque("diminuir")
        # Cria log de alteração de status
        if status_antigo and status_antigo != self.status:
            LogStatusPedido.objects.create(
                pedido=self,
                status_antigo=status_antigo,
                status_novo=self.status,
                usuario=getattr(self, 'usuario', None)
            )


class ItemPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="itens")
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.PositiveIntegerField(default=1)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    tamanho = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        tamanho = f" ({self.tamanho})" if self.tamanho else ""
        return (
            f"{self.quantidade}x {self.produto.nome}{tamanho} (R${self.preco_unitario})"
        )

    def save(self, *args, **kwargs):
        """Sobrescreve o save para definir o preço unitário e atualizar o total do pedido"""
        if not self.preco_unitario:
            self.preco_unitario = self.produto.preco
        super().save(*args, **kwargs)
        self.pedido.save()  # Atualiza o total do pedido

    def delete(self, *args, **kwargs):
        """Sobrescreve o delete para atualizar o total do pedido"""
        pedido = self.pedido
        super().delete(*args, **kwargs)
        pedido.save()  # Atualiza o total do pedido


class Tag(models.Model):
    nome = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.nome


class Favorito(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('usuario', 'produto')


class LogStatusPedido(models.Model):
    pedido = models.ForeignKey('Pedido', on_delete=models.CASCADE, related_name='logs_status')
    status_antigo = models.CharField(max_length=2)
    status_novo = models.CharField(max_length=2)
    data = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Pedido {self.pedido.codigo}: {self.status_antigo} → {self.status_novo} em {self.data:%d/%m/%Y %H:%M}"


class Carrinho(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='carrinho')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)


class ItemCarrinho(models.Model):
    carrinho = models.ForeignKey(Carrinho, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.PositiveIntegerField(default=1)
    tamanho = models.CharField(max_length=20, null=True, blank=True)
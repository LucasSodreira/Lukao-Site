from django.db import models
from django.core.validators import (
    MinValueValidator,
    RegexValidator,
    MinLengthValidator,
)
from django.conf import settings
from django.db.models import Avg
from django.db.models import Sum, F
from django.core.exceptions import ValidationError
from uuid import uuid4
from django.utils.text import slugify
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class Categoria(models.Model):
    nome = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    descricao = models.TextField(blank=True, null=True)
    categoria_pai = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subcategorias')

    def __str__(self):
        return self.nome

    def clean(self):
        if self.nome and len(self.nome.strip()) < 2:
            raise ValidationError("O nome da categoria deve ter pelo menos 2 caracteres.")
        if self.categoria_pai and self.categoria_pai == self:
            raise ValidationError("A categoria não pode ser pai dela mesma.")

    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.slug:
            self.slug = slugify(self.nome)
        super().save(*args, **kwargs)


class Cor(models.Model):
    nome = models.CharField(max_length=50, unique=True)
    valor_css = models.CharField(max_length=50, help_text="Valor para background-color no CSS (ex: 'red', '#ff0000')")
    ordem = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.nome

    def clean(self):
        if not self.nome or len(self.nome.strip()) < 2:
            raise ValidationError("O nome da cor deve ter pelo menos 2 caracteres.")


class Marca(models.Model):
    nome = models.CharField(max_length=50, unique=True)
    descricao = models.TextField(blank=True, null=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    logo = models.ImageField(upload_to="marcas/", blank=True, null=True)

    def __str__(self):
        return self.nome

    def clean(self):
        if not self.nome or len(self.nome.strip()) < 2:
            raise ValidationError("O nome da marca deve ter pelo menos 2 caracteres.")

    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.slug:
            self.slug = slugify(self.nome)
        super().save(*args, **kwargs)


class Produto(models.Model):
    visivel = models.BooleanField(default=True)
    nome = models.CharField(max_length=255)
    descricao = models.TextField(blank=True, null=True)
    preco = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    categoria = models.ForeignKey(
        Categoria, on_delete=models.CASCADE, related_name='produtos'
    )
    preco_original = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    desconto = models.IntegerField(null=True, blank=True)
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
    sku = models.CharField(max_length=50, unique=True, blank=True, null=True, help_text="SKU do produto")
    codigo_barras = models.CharField(max_length=50, blank=True, null=True, help_text="Código de barras")
    seo_title = models.CharField(max_length=70, blank=True, null=True)
    seo_description = models.CharField(max_length=160, blank=True, null=True)
    marca = models.ForeignKey(
        Marca, on_delete=models.CASCADE, related_name='produtos', null=True, blank=True
    )
    tags = models.ManyToManyField('Tag', blank=True, related_name='produtos')

    ativo = models.BooleanField(default=True)
    destaque = models.BooleanField(default=False)
    
    preco_promocional = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    promocao_inicio = models.DateTimeField(null=True, blank=True)
    promocao_fim = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    
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

    def __str__(self):
        return f"{self.nome} (R${self.preco})"

    def preco_vigente(self):
        agora = timezone.now()
        if self.preco_promocional and self.promocao_inicio and self.promocao_fim:
            if self.promocao_inicio <= agora <= self.promocao_fim:
                return self.preco_promocional
        return self.preco
    
    def calcular_desconto(self):
        preco_base = self.preco_original or self.preco
        preco_atual = self.preco_vigente()
        if preco_base > preco_atual:
            return round((1 - (preco_atual / preco_base)) * 100)
        return 0
    
    def get_tamanhos_disponiveis(self):
        if self.tamanhos_disponiveis:
            return [t.strip() for t in self.tamanhos_disponiveis.split(",")]
        return []

    def clean(self):
        super().clean()
        if self.preco_original and self.preco_original < self.preco:
            raise ValidationError("O preço original não pode ser menor que o preço atual.")
        if self.preco_promocional and self.preco_promocional > self.preco:
            raise ValidationError("O preço promocional deve ser menor que o preço atual.")
        if self.estoque is not None and self.estoque < 0:
            raise ValidationError("O estoque não pode ser negativo.")
        if self.peso is not None and self.peso < 0:
            raise ValidationError("O peso não pode ser negativo.")
        if self.width is not None and self.width < 0:
            raise ValidationError("A largura não pode ser negativa.")
        if self.height is not None and self.height < 0:
            raise ValidationError("A altura não pode ser negativa.")
        if self.length is not None and self.length < 0:
            raise ValidationError("O comprimento não pode ser negativo.")
        if self.nome and len(self.nome.strip()) < 2:
            raise ValidationError("O nome do produto deve ter pelo menos 2 caracteres.")
        if self.promocao_inicio and self.promocao_fim:
            if self.promocao_inicio >= self.promocao_fim:
                raise ValidationError("A data de início da promoção deve ser menor que a data de fim.")

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

    def media_avaliacoes(self):
        return self.avaliacoes.aggregate(media=Avg('nota'))['media'] or 0.0

    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.seo_title:
            self.seo_title = self.nome[:70]
        if not self.slug:
            self.slug = slugify(self.nome)
        if not self.preco_original:
            self.preco_original = self.preco
        self.desconto = self.calcular_desconto()
        preco_antigo = None
        if self.pk:
            preco_antigo = Produto.objects.get(pk=self.pk).preco
        super().save(*args, **kwargs)
        if preco_antigo is not None and preco_antigo != self.preco:
            HistoricoPreco.objects.create(produto=self, preco=self.preco)


class ProdutoVariacao(models.Model):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='variacoes')
    cor = models.ForeignKey(Cor, on_delete=models.CASCADE)
    tamanho = models.CharField(max_length=20, choices=Produto.SIZE_CHOICES, null=True, blank=True)
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

    def clean(self):
        if self.estoque is not None and self.estoque < 0:
            raise ValidationError("O estoque da variação não pode ser negativo.")
        if self.peso is not None and self.peso < 0:
            raise ValidationError("O peso da variação não pode ser negativo.")
        if self.width is not None and self.width < 0:
            raise ValidationError("A largura da variação não pode ser negativa.")
        if self.height is not None and self.height < 0:
            raise ValidationError("A altura da variação não pode ser negativa.")
        if self.length is not None and self.length < 0:
            raise ValidationError("O comprimento da variação não pode ser negativo.")


class ImagemProduto(models.Model):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='imagens')
    imagem = models.ImageField(upload_to="produtos/galeria/")
    destaque = models.BooleanField(default=False)
    ordem = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Imagem de {self.produto.nome}"

    def clean(self):
        if not self.imagem:
            raise ValidationError("A imagem é obrigatória.")


class AvaliacaoProduto(models.Model):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='avaliacoes')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    nota = models.PositiveSmallIntegerField()
    comentario = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    aprovada = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.usuario} - {self.produto.nome} ({self.nota})"

    def clean(self):
        if self.nota < 1 or self.nota > 5:
            raise ValidationError("A nota deve ser entre 1 e 5.")


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

    def clean(self):
        if self.nome_completo and len(self.nome_completo.strip()) < 3:
            raise ValidationError("O nome completo deve ter pelo menos 3 caracteres.")
        if self.numero and len(self.numero.strip()) == 0:
            raise ValidationError("O número do endereço é obrigatório.")
        if self.cidade and len(self.cidade.strip()) < 2:
            raise ValidationError("O nome da cidade deve ter pelo menos 2 caracteres.")

    def save(self, *args, **kwargs):
        # Garante que só tenha um endereço principal por usuário
        if self.principal and self.usuario:
            Endereco.objects.filter(usuario=self.usuario, principal=True).update(
                principal=False
            )
        super().save(*args, **kwargs)


class Cupom(models.Model):
    codigo = models.CharField(max_length=30, unique=True)
    descricao = models.CharField(max_length=255, blank=True)
    desconto_percentual = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    desconto_valor = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    ativo = models.BooleanField(default=True)
    validade = models.DateTimeField(null=True, blank=True)
    uso_unico = models.BooleanField(default=False)
    max_usos = models.PositiveIntegerField(null=True, blank=True)
    usos = models.PositiveIntegerField(default=0)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    def is_valido(self, user=None):
        from django.utils import timezone
        if not self.ativo:
            return False
        if self.validade and self.validade < timezone.now():
            return False
        if self.max_usos and self.usos >= self.max_usos:
            return False
        if self.uso_unico and user and Pedido.objects.filter(cupom=self, usuario=user).exists():
            return False
        if self.usuario and user and self.usuario != user:
            return False
        return True

    def aplicar(self, total):
        # Aplica o desconto do cupom ao total informado
        if self.desconto_percentual:
            desconto = total * (self.desconto_percentual / 100)
        elif self.desconto_valor:
            desconto = self.desconto_valor
        else:
            desconto = 0
        return max(total - desconto, 0)

    def clean(self):
        if not self.codigo or len(self.codigo.strip()) < 3:
            raise ValidationError("O código do cupom deve ter pelo menos 3 caracteres.")
        if self.desconto_percentual and (self.desconto_percentual < 0 or self.desconto_percentual > 100):
            raise ValidationError("O desconto percentual deve ser entre 0 e 100.")
        if self.desconto_valor and self.desconto_valor < 0:
            raise ValidationError("O desconto em valor não pode ser negativo.")

    def __str__(self):
        return self.codigo


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
    cupom = models.ForeignKey(Cupom, null=True, blank=True, on_delete=models.SET_NULL)
    payment_intent_id = models.CharField(max_length=255, blank=True, null=True)  # Para Stripe
    frete_id = models.CharField(max_length=50, blank=True, null=True)  # ID do serviço de frete
    melhor_envio_id = models.CharField(max_length=255, blank=True, null=True)  # ID do envio no Melhor Envio

    class Meta:
        ordering = ["-data_criacao"]

    def __str__(self):
        return f"Pedido {self.codigo}"

    def calcular_total(self):
        # Soma o valor dos itens + frete (se houver)
        total = sum(item.preco_unitario * item.quantidade for item in self.itens.all())
        if hasattr(self, 'frete_valor') and self.frete_valor:
            total += self.frete_valor
        return total

    def atualizar_estoque(self, operacao="diminuir"):
        # Atualiza o estoque das variações dos itens do pedido
        for item in self.itens.all():
            variacao = getattr(item, 'variacao', None)
            if variacao:
                if operacao == "diminuir":
                    variacao.estoque = max(0, variacao.estoque - item.quantidade)
                elif operacao == "aumentar":
                    variacao.estoque += item.quantidade
                variacao.save()

    def clean(self):
        if self.total is not None and self.total < 0:
            raise ValidationError("O total do pedido não pode ser negativo.")

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
    variacao = models.ForeignKey(ProdutoVariacao, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.produto} x {self.quantidade}"

    def clean(self):
        if self.quantidade < 1:
            raise ValidationError("A quantidade do item deve ser pelo menos 1.")
        if self.preco_unitario is not None and self.preco_unitario < 0:
            raise ValidationError("O preço unitário não pode ser negativo.")

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


class HistoricoPreco(models.Model):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='historico_precos')
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    data = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.preco < 0:
            raise ValidationError("O preço do histórico não pode ser negativo.")


class Tag(models.Model):
    nome = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.nome

    def clean(self):
        if not self.nome or len(self.nome.strip()) < 2:
            raise ValidationError("O nome da tag deve ter pelo menos 2 caracteres.")


class Favorito(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('usuario', 'produto')

    def clean(self):
        if not self.usuario_id or not self.produto_id:
            raise ValidationError("Usuário e produto são obrigatórios.")


class LogStatusPedido(models.Model):
    pedido = models.ForeignKey('Pedido', on_delete=models.CASCADE, related_name='logs_status')
    status_antigo = models.CharField(max_length=2)
    status_novo = models.CharField(max_length=2)
    data = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Pedido {self.pedido.codigo}: {self.status_antigo} → {self.status_novo} em {self.data:%d/%m/%Y %H:%M}"

    def clean(self):
        if not self.status_antigo or not self.status_novo:
            raise ValidationError("Status antigo e novo são obrigatórios.")


class LogAcao(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    acao = models.CharField(max_length=100)
    detalhes = models.TextField(blank=True)
    data = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.usuario} - {self.acao} em {self.data:%d/%m/%Y %H:%M}"

    def clean(self):
        if not self.acao or len(self.acao.strip()) < 2:
            raise ValidationError("A ação deve ter pelo menos 2 caracteres.")


class Carrinho(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='carrinho')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def clean(self):
        if not self.usuario_id:
            raise ValidationError("Usuário é obrigatório para o carrinho.")


class ItemCarrinho(models.Model):
    carrinho = models.ForeignKey(Carrinho, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.PositiveIntegerField(default=1)
    variacao = models.ForeignKey(ProdutoVariacao, on_delete=models.SET_NULL, null=True, blank=True)

    def clean(self):
        if self.quantidade < 1:
            raise ValidationError("A quantidade do item do carrinho deve ser pelo menos 1.")


class Perfil(models.Model):
    endereco_rapido = models.ForeignKey(
        'core.Endereco', on_delete=models.SET_NULL,
        blank=True, null=True, related_name='usuarios_rapido'
    )
    metodo_pagamento_rapido = models.CharField(max_length=50, blank=True, null=True)

    def clean(self):
        if self.metodo_pagamento_rapido and len(self.metodo_pagamento_rapido.strip()) < 2:
            raise ValidationError("O método de pagamento rápido deve ter pelo menos 2 caracteres.")
        
class Reembolso(models.Model):
    STATUS_CHOICES = (
        ('P', 'Pendente'),
        ('A', 'Aprovado'),
        ('R', 'Rejeitado'),
        ('C', 'Concluído'),
    )
    pedido = models.OneToOneField(Pedido, related_name='reembolso', on_delete=models.CASCADE)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    data_criacao = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=2, choices=STATUS_CHOICES, default='P')
    motivo = models.TextField(blank=True)
    notas = models.TextField(blank=True)  # Notas do administrador
    def __str__(self): return f"Reembolso de Pedido #{self.pedido.id}"

class HistoricoPedido(models.Model):
    pedido = models.ForeignKey(Pedido, related_name='historico', on_delete=models.CASCADE)
    status_antigo = models.CharField(max_length=2, choices=Pedido.STATUS_CHOICES)
    status_novo = models.CharField(max_length=2, choices=Pedido.STATUS_CHOICES)
    data = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    notas = models.TextField(blank=True)
    def __str__(self): return f"Histórico de Pedido #{self.pedido.id}: {self.status_antigo} -> {self.status_novo}"
    
class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='notifications',
        on_delete=models.CASCADE
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='actor_notifications',
        on_delete=models.CASCADE,
        null=True
    )
    verb = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    unread = models.BooleanField(default=True)
    target_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    target_object_id = models.PositiveIntegerField(null=True, blank=True)
    target = GenericForeignKey('target_content_type', 'target_object_id')

    def __str__(self):
        return f"{self.recipient} - {self.verb} - {self.timestamp}"

    class Meta:
        ordering = ['-timestamp']
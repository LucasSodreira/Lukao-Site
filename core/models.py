from django.db import models
from django.core.validators import (
    MinValueValidator,
    RegexValidator,
    MinLengthValidator,
)
from django.conf import settings
from django.db.models import Avg
from django.core.exceptions import ValidationError
from uuid import uuid4
from django.utils.text import slugify
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import hashlib
import os

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
            # Gera slug base
            base_slug = slugify(self.nome)
            slug = base_slug
            
            # Garante que o slug seja único
            counter = 1
            while Categoria.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            self.slug = slug
        super().save(*args, **kwargs)



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
            # Gera slug base
            base_slug = slugify(self.nome)
            slug = base_slug
            
            # Garante que o slug seja único
            counter = 1
            while Marca.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            self.slug = slug
        super().save(*args, **kwargs)


class AtributoTipo(models.Model):
    nome = models.CharField(max_length=50, unique=True)  # "Tamanho", "Cor", "Material", "Estilo"
    tipo = models.CharField(max_length=20, choices=[
        ('select', 'Seleção Única'),
        ('color', 'Cor'),
        ('size', 'Tamanho'),
        ('text', 'Texto Livre')
    ])
    obrigatorio = models.BooleanField(default=False, help_text="Se é obrigatório escolher este atributo")
    ordem = models.PositiveIntegerField(default=0, help_text="Ordem de exibição")
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['ordem', 'nome']
        verbose_name = "Tipo de Atributo"
        verbose_name_plural = "Tipos de Atributos"

    def __str__(self):
        return self.nome

    def clean(self):
        if not self.nome or len(self.nome.strip()) < 2:
            raise ValidationError("O nome do tipo de atributo deve ter pelo menos 2 caracteres.")


class AtributoValor(models.Model):
    tipo = models.ForeignKey(AtributoTipo, on_delete=models.CASCADE, related_name='valores')
    valor = models.CharField(max_length=100)
    codigo = models.CharField(max_length=20, blank=True, help_text="Código interno (ex: 'M', 'GG', '#FF0000')")
    ordem = models.PositiveIntegerField(default=0)
    ativo = models.BooleanField(default=True)
    valor_adicional_preco = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Valor adicional ao preço do produto"
    )

    class Meta:
        unique_together = ('tipo', 'valor')
        ordering = ['tipo', 'ordem', 'valor']
        verbose_name = "Valor de Atributo"
        verbose_name_plural = "Valores de Atributos"

    def __str__(self):
        return f"{self.tipo.nome}: {self.valor}"

    def clean(self):
        if not self.valor or len(self.valor.strip()) < 1:
            raise ValidationError("O valor do atributo não pode estar vazio.")


class Produto(models.Model):
    visivel = models.BooleanField(default=True, db_index=True)
    nome = models.CharField(max_length=255, db_index=True)
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
    # estoque removido - agora só existe em ProdutoVariacao
    imagem = models.ImageField(upload_to="produtos/", default="produtos/default.jpg")
    sku = models.CharField(max_length=50, unique=True, blank=True, null=True, help_text="SKU do produto")
    codigo_barras = models.CharField(max_length=50, blank=True, null=True, help_text="Código de barras")
    seo_title = models.CharField(max_length=70, blank=True, null=True)
    seo_description = models.CharField(max_length=160, blank=True, null=True)
    marca = models.ForeignKey(
        Marca, on_delete=models.CASCADE, related_name='produtos', null=True, blank=True
    )
    tags = models.ManyToManyField('Tag', blank=True, related_name='produtos')

    # Campos específicos para e-commerce de roupas
    genero = models.CharField(max_length=20, choices=[
        ('M', 'Masculino'),
        ('F', 'Feminino'),
        ('U', 'Unissex')
    ], default='M')
    
    temporada = models.CharField(max_length=20, choices=[
        ('verao', 'Verão'),
        ('inverno', 'Inverno'),
        ('meia_estacao', 'Meia Estação'),
        ('todo_ano', 'Todo Ano')
    ], blank=True)
    
    cuidados = models.TextField(blank=True, help_text="Instruções de lavagem e cuidados")
    origem = models.CharField(max_length=50, default="Brasil")

    ativo = models.BooleanField(default=True, db_index=True)
    destaque = models.BooleanField(default=False, db_index=True)
    
    preco_promocional = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    promocao_inicio = models.DateTimeField(null=True, blank=True)
    promocao_fim = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)

    def __str__(self):
        return f"{self.nome} (R${self.preco})"
    
    def delete(self, *args, **kwargs):
        if self.imagem and self.imagem.name != "produtos/default.jpg":
            if os.path.isfile(self.imagem.path):
                os.remove(self.imagem.path)
        super().delete(*args, **kwargs)

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
        """Retorna tamanhos disponíveis baseado nas variações do produto"""
        tamanhos = []
        for variacao in self.variacoes.filter(estoque__gt=0):
            for atributo in variacao.atributos.filter(tipo__tipo='size'):
                if atributo.valor not in tamanhos:
                    tamanhos.append(atributo.valor)
        return tamanhos
    
    def clean(self):
        super().clean()
        if self.preco_original and self.preco_original < self.preco:
            raise ValidationError("O preço original não pode ser menor que o preço atual.")
        if self.preco_promocional and self.preco_promocional > self.preco:
            raise ValidationError("O preço promocional deve ser menor que o preço atual.")
        # estoque removido - validação agora só em ProdutoVariacao
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
                raise ValidationError("A data de início da promoção deve ser menor que a data de fim.")    # Métodos de estoque removidos - agora gerenciados em ProdutoVariacao

    def media_avaliacoes(self):
        return self.avaliacoes.aggregate(media=Avg('nota'))['media'] or 0.0

    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.seo_title:
            self.seo_title = self.nome[:70]
        if not self.slug:
            # Gera slug base
            base_slug = slugify(self.nome)
            slug = base_slug
            
            # Garante que o slug seja único
            counter = 1
            while Produto.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            self.slug = slug
            
        if not self.preco_original:
            self.preco_original = self.preco
        
        # Só calcular desconto se necessário
        self.desconto = self.calcular_desconto()
        
        # Só verificar preço antigo se for uma atualização
        preco_antigo = None
        if self.pk:
            preco_antigo = self.__class__.objects.filter(pk=self.pk).values_list('preco', flat=True).first()
        
        super().save(*args, **kwargs)
        
        # Só criar histórico se preço mudou
        if preco_antigo is not None and preco_antigo != self.preco:
            HistoricoPreco.objects.create(produto=self, preco=self.preco)


class ProdutoVariacao(models.Model):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='variacoes')
    atributos = models.ManyToManyField(AtributoValor, related_name='variacoes')
    sku = models.CharField(max_length=50, unique=True, blank=True, null=True, db_index=True)
    estoque = models.PositiveIntegerField(default=0, db_index=True)
    ativo = models.BooleanField(default=True, db_index=True, help_text="Se a variação está ativa/visível")
    preco_adicional = models.DecimalField(max_digits=10, decimal_places=2, default=0)
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
    atributos_hash = models.CharField(max_length=128, editable=False, db_index=True)
    preco_promocional = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    promocao_inicio = models.DateTimeField(null=True, blank=True)
    promocao_fim = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Variação de Produto"
        verbose_name_plural = "Variações de Produtos"
        constraints = [
            models.UniqueConstraint(fields=['produto', 'atributos_hash'], name='unique_produto_atributos')
        ]

    def __str__(self):
        try:
            # Verifica se a instância já foi salva no banco
            if self.pk and self.atributos.exists():
                atributos_str = " - ".join([f"{attr.tipo.nome}: {attr.valor}" for attr in self.atributos.all()])
                return f"{self.produto.nome} - {atributos_str}"
            else:
                return f"{self.produto.nome} - Variação (sem atributos definidos)"
        except:
            # Fallback em caso de erro
            return f"Variação de {getattr(self.produto, 'nome', 'Produto')} (ID: {self.pk or 'Novo'})"
    
    def clean(self):
        super().clean()
        
        # Validar atributos obrigatórios
        tipos_obrigatorios = AtributoTipo.objects.filter(obrigatorio=True)
        atributos_tipos = [attr.tipo for attr in self.atributos.all()]
        
        for tipo in tipos_obrigatorios:
            if tipo not in atributos_tipos:
                raise ValidationError(f"Atributo obrigatório '{tipo.nome}' não foi selecionado.")
        
        # Validar atributos duplicados (mesmo tipo)
        tipos_selecionados = []
        for attr in self.atributos.all():
            if attr.tipo in tipos_selecionados:
                raise ValidationError(f"Múltiplos valores para '{attr.tipo.nome}' não são permitidos.")
            tipos_selecionados.append(attr.tipo)
            
        # Validar combinação única de atributos para o mesmo produto
        if self.pk:  # Se for uma edição
            variacoes_existentes = ProdutoVariacao.objects.filter(produto=self.produto).exclude(pk=self.pk)
        else:  # Se for uma nova variação
            variacoes_existentes = ProdutoVariacao.objects.filter(produto=self.produto)
            
        for variacao_existente in variacoes_existentes:
            atributos_existentes = set(variacao_existente.atributos.all())
            atributos_novos = set(self.atributos.all())
            
            if atributos_existentes == atributos_novos:
                raise ValidationError("Já existe uma variação com essa combinação de atributos para este produto.")
    
    def gerar_sku_automatico(self):
        """Gera SKU automaticamente baseado no produto e atributos"""
        if not self.sku and self.produto.sku:
            # Pega valores dos atributos para compor o SKU
            sufixos = []
            for attr in self.atributos.all().order_by('tipo__ordem', 'tipo__nome'):
                if attr.codigo:
                    sufixos.append(attr.codigo)
                else:
                    # Se não tem código, usa primeiras letras do valor
                    sufixos.append(attr.valor[:3].upper())
            
            if sufixos:
                self.sku = f"{self.produto.sku}-{'-'.join(sufixos)}"
    
    def calcular_hash_atributos(self):
        ids = sorted(str(attr.id) for attr in self.atributos.all())
        return hashlib.sha256("-".join(ids).encode()).hexdigest()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)  # Salva para garantir que tenha ID
        self.atributos_hash = self.calcular_hash_atributos()
        super().save(update_fields=['atributos_hash'])
    
    def preco_final(self):
        agora = timezone.now()
        if self.preco_promocional and self.promocao_inicio and self.promocao_fim:
            if self.promocao_inicio <= agora <= self.promocao_fim:
                return self.preco_promocional
        preco_base = self.produto.preco_vigente()
        preco_adicional_variacao = self.preco_adicional
        preco_adicional_atributos = sum(attr.valor_adicional_preco for attr in self.atributos.all())
        return preco_base + preco_adicional_variacao + preco_adicional_atributos

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

    def delete(self, *args, **kwargs):
        if self.imagem and os.path.isfile(self.imagem.path):
            os.remove(self.imagem.path)
        super().delete(*args, **kwargs)


class AvaliacaoProduto(models.Model):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='avaliacoes')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    nota = models.PositiveSmallIntegerField()
    comentario = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    aprovada = models.BooleanField(default=False)  # Mudou para False para moderação

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
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Última Atualização")

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
    TIPO_CHOICES = [
        ('percentual', 'Desconto Percentual'),
        ('valor_fixo', 'Valor Fixo'),
        ('frete_gratis', 'Frete Grátis'),
        ('compre_leve', 'Compre X Leve Y'),
    ]
    
    codigo = models.CharField(max_length=30, unique=True)
    descricao = models.CharField(max_length=255, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='percentual')
    desconto_percentual = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    desconto_valor = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)    
    ativo = models.BooleanField(default=True, db_index=True)
    validade_inicio = models.DateTimeField(null=True, blank=True, help_text="Data de início da validade")
    validade_fim = models.DateTimeField(null=True, blank=True, help_text="Data de fim da validade", db_index=True)
    uso_unico = models.BooleanField(default=False, help_text="Permite apenas um uso por usuário")
    max_usos = models.PositiveIntegerField(null=True, blank=True, help_text="Número máximo de usos totais")
    usos = models.PositiveIntegerField(default=0, help_text="Quantas vezes foi usado")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, help_text="Cupom exclusivo para um usuário")
      # Campos para regras de aplicação
    valor_minimo_pedido = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Valor mínimo do pedido para usar o cupom")
    valor_maximo_desconto = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Valor máximo de desconto a ser aplicado")
    primeira_compra_apenas = models.BooleanField(default=False, help_text="Válido apenas para primeira compra")
    aplicar_apenas_itens_elegiveis = models.BooleanField(default=False, help_text="Se True, aplica desconto apenas aos itens elegíveis. Se False, aplica ao total do pedido")
    categorias_aplicaveis = models.ManyToManyField('Categoria', blank=True, help_text="Categorias onde o cupom é aplicável")
    produtos_aplicaveis = models.ManyToManyField('Produto', blank=True, help_text="Produtos específicos onde o cupom é aplicável")
    
    # Campos para cupons "Compre X Leve Y"
    quantidade_comprar = models.PositiveIntegerField(null=True, blank=True, help_text="Quantidade para comprar (tipo compre_leve)")
    quantidade_levar = models.PositiveIntegerField(null=True, blank=True, help_text="Quantidade para levar grátis (tipo compre_leve)")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cupom"
        verbose_name_plural = "Cupons"
        ordering = ['-criado_em']

    def is_valido(self, user=None, pedido_valor=None, produtos=None):
        from django.utils import timezone
        
        if not self.ativo:
            return False, "Cupom inativo"
            
        # Verificar data de validade
        agora = timezone.now()
        if self.validade_inicio and self.validade_inicio > agora:
            return False, "Cupom ainda não está válido"
        if self.validade_fim and self.validade_fim < agora:
            return False, "Cupom expirado"
            
        # Verificar número máximo de usos
        if self.max_usos and self.usos >= self.max_usos:
            return False, "Cupom esgotado"
            
        # Verificar uso único por usuário
        if self.uso_unico and user and Pedido.objects.filter(cupom=self, usuario=user).exists():
            return False, "Cupom já foi usado por este usuário"
            
        # Verificar se é cupom exclusivo de usuário
        if self.usuario and user and self.usuario != user:
            return False, "Cupom não disponível para este usuário"
            
        # Verificar valor mínimo do pedido
        if self.valor_minimo_pedido and pedido_valor and pedido_valor < self.valor_minimo_pedido:
            return False, f"Valor mínimo do pedido: R$ {self.valor_minimo_pedido}"
            
        # Verificar primeira compra
        if self.primeira_compra_apenas and user and Pedido.objects.filter(usuario=user, status__in=['PA', 'E', 'T', 'C']).exists():
            return False, "Cupom válido apenas para primeira compra"
            
        # Verificar produtos/categorias aplicáveis
        if produtos and (self.produtos_aplicaveis.exists() or self.categorias_aplicaveis.exists()):
            produtos_validos = False
            for produto in produtos:
                if self.produtos_aplicaveis.filter(id=produto.id).exists():
                    produtos_validos = True
                    break
                if self.categorias_aplicaveis.filter(id=produto.categoria.id).exists():
                    produtos_validos = True
                    break
            if not produtos_validos:
                return False, "Cupom não aplicável aos produtos do carrinho"
        
        return True, "Cupom válido"    
    
    def aplicar(self, total, itens_pedido=None):
        """Aplica o desconto do cupom ao total informado com granularidade de aplicação"""
        if self.tipo == 'frete_gratis':
            # Para frete grátis, o desconto é tratado separadamente no checkout
            return total, {'tipo': 'frete_gratis', 'desconto': 0}
            
        elif self.tipo == 'compre_leve' and itens_pedido:
            # Lógica para "Compre X Leve Y"
            desconto_total = 0
            if self.quantidade_comprar and self.quantidade_levar:
                for item in itens_pedido:
                    if self._produto_aplicavel(item.produto):
                        grupos_completos = item.quantidade // (self.quantidade_comprar + self.quantidade_levar)
                        itens_gratis = grupos_completos * self.quantidade_levar
                        desconto_total += itens_gratis * item.preco_unitario
            
            desconto_aplicado = min(desconto_total, total)
            if self.valor_maximo_desconto:
                desconto_aplicado = min(desconto_aplicado, self.valor_maximo_desconto)
                
            return max(total - desconto_aplicado, 0), {'tipo': 'compre_leve', 'desconto': desconto_aplicado}
            
        else:
            # Desconto percentual ou valor fixo com granularidade
            if self.aplicar_apenas_itens_elegiveis and itens_pedido and (self.produtos_aplicaveis.exists() or self.categorias_aplicaveis.exists()):
                # Aplica desconto apenas aos itens elegíveis
                total_elegiveis = 0
                for item in itens_pedido:
                    if self._produto_aplicavel(item.produto):
                        total_elegiveis += item.preco_unitario * item.quantidade
                
                if total_elegiveis == 0:
                    return total, {'tipo': self.tipo, 'desconto': 0}
                
                # Calcula desconto sobre itens elegíveis
                if self.desconto_percentual:
                    desconto = total_elegiveis * (self.desconto_percentual / 100)
                elif self.desconto_valor:
                    desconto = self.desconto_valor
                else:
                    desconto = 0
                    
                # Aplicar valor máximo de desconto se configurado
                if self.valor_maximo_desconto:
                    desconto = min(desconto, self.valor_maximo_desconto)
                    
                desconto_aplicado = min(desconto, total_elegiveis)
                return max(total - desconto_aplicado, 0), {'tipo': self.tipo, 'desconto': desconto_aplicado, 'total_elegiveis': total_elegiveis}
            else:
                # Aplica desconto ao total do pedido (comportamento padrão)
                if self.desconto_percentual:
                    desconto = total * (self.desconto_percentual / 100)
                elif self.desconto_valor:
                    desconto = self.desconto_valor
                else:
                    desconto = 0
                    
                # Aplicar valor máximo de desconto se configurado
                if self.valor_maximo_desconto:
                    desconto = min(desconto, self.valor_maximo_desconto)
                    
                desconto_aplicado = min(desconto, total)
                return max(total - desconto_aplicado, 0), {'tipo': self.tipo, 'desconto': desconto_aplicado}

    def _produto_aplicavel(self, produto):
        """Verifica se o produto é aplicável para este cupom"""
        if not self.produtos_aplicaveis.exists() and not self.categorias_aplicaveis.exists():
            return True
        
        if self.produtos_aplicaveis.filter(id=produto.id).exists():
            return True
            
        if self.categorias_aplicaveis.filter(id=produto.categoria.id).exists():
            return True
            
        return False
        
    def incrementar_uso(self):
        """Incrementa o contador de usos do cupom"""
        self.usos += 1
        self.save(update_fields=['usos'])

    def clean(self):
        if not self.codigo or len(self.codigo.strip()) < 3:
            raise ValidationError("O código do cupom deve ter pelo menos 3 caracteres.")
            
        if self.tipo == 'percentual' and not self.desconto_percentual:
            raise ValidationError("Desconto percentual é obrigatório para cupons do tipo percentual.")
            
        if self.tipo == 'valor_fixo' and not self.desconto_valor:
            raise ValidationError("Desconto em valor é obrigatório para cupons do tipo valor fixo.")
            
        if self.tipo == 'compre_leve' and (not self.quantidade_comprar or not self.quantidade_levar):
            raise ValidationError("Quantidades de compra e leva são obrigatórias para cupons do tipo 'Compre X Leve Y'.")
            
        if self.desconto_percentual and (self.desconto_percentual < 0 or self.desconto_percentual > 100):
            raise ValidationError("O desconto percentual deve ser entre 0 e 100.")
            
        if self.desconto_valor and self.desconto_valor < 0:
            raise ValidationError("O desconto em valor não pode ser negativo.")
            
        if self.valor_minimo_pedido and self.valor_minimo_pedido < 0:
            raise ValidationError("O valor mínimo do pedido não pode ser negativo.")
            
        if self.valor_maximo_desconto and self.valor_maximo_desconto < 0:
            raise ValidationError("O valor máximo de desconto não pode ser negativo.")
            
        if self.validade_inicio and self.validade_fim and self.validade_inicio >= self.validade_fim:
            raise ValidationError("A data de início deve ser anterior à data de fim.")

    def __str__(self):
        return f"{self.codigo} - {self.get_tipo_display()}"


class Pedido(models.Model):
    STATUS_CHOICES = [
        ("P", "Pendente"),
        ("PA", "Pagamento Aprovado"),
        ("E", "Enviado"),
        ("T", "Em Transporte"),
        ("C", "Concluído"),
        ("X", "Cancelado"),
        ("D", "Devolvido"),
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
    status = models.CharField(max_length=2, choices=STATUS_CHOICES, default="P", db_index=True)
    endereco_entrega = models.ForeignKey(
        Endereco, on_delete=models.SET_NULL, null=True
    )
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    frete_valor = models.DecimalField(max_digits=10, decimal_places=2, default=0)
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
    data_criacao = models.DateTimeField(auto_now_add=True, db_index=True)
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
        """Calcula o total do pedido incluindo frete e descontos de cupom"""
        # Soma o valor dos itens
        total_itens = sum(item.preco_unitario * item.quantidade for item in self.itens.all())
        total_com_frete = total_itens + self.frete_valor
        
        # Aplica desconto do cupom se houver
        if self.cupom:
            produtos = [item.produto for item in self.itens.all()]
            valido, mensagem = self.cupom.is_valido(
                user=self.usuario, 
                pedido_valor=total_itens, 
                produtos=produtos
            )
            
            if valido:
                if self.cupom.tipo == 'frete_gratis':
                    # Para frete grátis, remove o valor do frete
                    return total_itens
                else:
                    # Para outros tipos, aplica o desconto
                    total_final, info_desconto = self.cupom.aplicar(total_com_frete, self.itens.all())
                    return total_final
        
        return total_com_frete
        
    def calcular_desconto_cupom(self):
        """Retorna informações sobre o desconto aplicado pelo cupom"""
        if not self.cupom:
            return {'tem_desconto': False, 'valor_desconto': 0, 'tipo': None}
            
        total_sem_desconto = sum(item.preco_unitario * item.quantidade for item in self.itens.all()) + self.frete_valor
        total_com_desconto = self.calcular_total()
        
        desconto = total_sem_desconto - total_com_desconto
        
        return {
            'tem_desconto': desconto > 0,
            'valor_desconto': desconto,
            'tipo': self.cupom.tipo,
            'codigo': self.cupom.codigo
        }
        
    def atualizar_estoque(self, operacao="diminuir"):
        """Atualiza o estoque das variações dos itens do pedido"""
        for item in self.itens.all():
            variacao = getattr(item, 'variacao', None)
            produto = item.produto
            
            if variacao:
                if operacao == "diminuir":
                    variacao.estoque = max(0, variacao.estoque - item.quantidade)
                elif operacao == "aumentar":
                    variacao.estoque += item.quantidade
                variacao.save()
            else:
                # Se não tem variação, não atualiza estoque do produto principal
                # pois agora o estoque está apenas nas variações
                pass

    def clean(self):
        if self.total is not None and self.total < 0:
            raise ValidationError("O total do pedido não pode ser negativo.")
        if self.frete_valor is not None and self.frete_valor < 0:
            raise ValidationError("O valor do frete não pode ser negativo.")
    
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
            
            # Lógica melhorada de atualização de estoque baseada na mudança de status
            # Estoque é reduzido quando o pagamento é aprovado (não apenas quando concluído)
            # Estoque é devolvido quando pedido é cancelado ou devolvido
            if status_antigo and status_antigo != self.status:
                if status_antigo not in ["PA", "E", "T", "C"] and self.status == "PA":
                    # Diminui estoque quando pagamento é aprovado
                    self.atualizar_estoque("diminuir")
                elif status_antigo in ["PA", "E", "T", "C"] and self.status in ["X", "D"]:
                    # Devolve estoque quando cancelado ou devolvido
                    self.atualizar_estoque("aumentar")
        
        # Cria log de alteração de status
        if status_antigo and status_antigo != self.status:
            LogStatusPedido.objects.create(
                pedido=self,
                status_antigo=status_antigo,
                status_novo=self.status,
                usuario=getattr(self, '_current_user', None),
                notas=f"Status alterado de {dict(self.STATUS_CHOICES).get(status_antigo)} para {dict(self.STATUS_CHOICES).get(self.status)}"
            )


class ItemPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="itens")
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.PositiveIntegerField(default=1)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    variacao = models.ForeignKey(ProdutoVariacao, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.produto} x {self.quantidade}"

    def preco_total(self):
        return self.preco_unitario * self.quantidade

    def clean(self):
        if self.quantidade < 1:
            raise ValidationError("A quantidade do item deve ser pelo menos 1.")
        if self.preco_unitario is not None and self.preco_unitario < 0:
            raise ValidationError("O preço unitário não pode ser negativo.")

    def save(self, *args, **kwargs):
        """Define o preço unitário e atualiza o total do pedido"""
        if not self.preco_unitario:
            if self.variacao:
                self.preco_unitario = self.variacao.preco_final()
            else:
                self.preco_unitario = self.produto.preco_vigente()
        
        super().save(*args, **kwargs)
        self.pedido.save()  # Atualiza o total do pedido

    def delete(self, *args, **kwargs):
        """Atualiza o total do pedido após deletar item"""
        pedido = self.pedido
        super().delete(*args, **kwargs)
        pedido.save()


class HistoricoPreco(models.Model):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='historico_precos')
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    data = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data']

    def clean(self):
        if self.preco < 0:
            raise ValidationError("O preço do histórico não pode ser negativo.")


class Tag(models.Model):
    nome = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True, blank=True)
    cor = models.CharField(max_length=7, default="#007bff", help_text="Cor da tag em hexadecimal")

    def __str__(self):
        return self.nome

    def clean(self):
        if not self.nome or len(self.nome.strip()) < 2:
            raise ValidationError("O nome da tag deve ter pelo menos 2 caracteres.")

    def save(self, *args, **kwargs):
        if not self.slug:
            # Gera slug base
            base_slug = slugify(self.nome)
            slug = base_slug
            
            # Garante que o slug seja único
            counter = 1
            while Tag.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            self.slug = slug
        super().save(*args, **kwargs)


class LogStatusPedido(models.Model):
    pedido = models.ForeignKey('Pedido', on_delete=models.CASCADE, related_name='logs_status')
    status_antigo = models.CharField(max_length=2)
    status_novo = models.CharField(max_length=2)
    data = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    notas = models.TextField(blank=True, help_text="Observações sobre a mudança de status")

    class Meta:
        ordering = ['-data']

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

    class Meta:
        ordering = ['-data']

    def __str__(self):
        return f"{self.usuario} - {self.acao} em {self.data:%d/%m/%Y %H:%M}"

    def clean(self):
        if not self.acao or len(self.acao.strip()) < 2:
            raise ValidationError("A ação deve ter pelo menos 2 caracteres.")


class Carrinho(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='carrinho')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def calcular_total(self):
        return sum(item.preco_total() for item in self.itens.all())

    def quantidade_total(self):
        return sum(item.quantidade for item in self.itens.all())

    def clean(self):
        if not self.usuario_id:
            raise ValidationError("Usuário é obrigatório para o carrinho.")


class ItemCarrinho(models.Model):
    carrinho = models.ForeignKey(Carrinho, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.PositiveIntegerField(default=1)
    variacao = models.ForeignKey(ProdutoVariacao, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ('carrinho', 'produto', 'variacao')

    def preco_unitario(self):
        if self.variacao:
            return self.variacao.preco_final()
        return self.produto.preco_vigente()

    def preco_total(self):
        return self.preco_unitario() * self.quantidade

    def clean(self):
        if self.quantidade < 1:
            raise ValidationError("A quantidade do item do carrinho deve ser pelo menos 1.")


# class Perfil(models.Model):
#     usuario = models.OneToOneField(
#         settings.AUTH_USER_MODEL, 
#         on_delete=models.CASCADE, 
#         related_name='perfil'
#     )
#     telefone = models.CharField(
#         max_length=15, 
#         blank=True, 
#         validators=[
#             RegexValidator(
#                 regex=r"^\(\d{2}\) \d{4,5}-\d{4}$",
#                 message="Telefone deve estar no formato (99) 99999-9999",
#             )
#         ]
#     )
#     data_nascimento = models.DateField(null=True, blank=True)
#     genero = models.CharField(max_length=1, choices=[
#         ('M', 'Masculino'),
#         ('F', 'Feminino'),
#         ('O', 'Outro'),
#     ], blank=True)
#     endereco_rapido = models.ForeignKey(
#         'Endereco', on_delete=models.SET_NULL,
#         blank=True, null=True, related_name='usuarios_rapido'
#     )
#     metodo_pagamento_rapido = models.CharField(max_length=50, blank=True, null=True)
#     receber_newsletters = models.BooleanField(default=True)
#     receber_promocoes = models.BooleanField(default=True)

#     def clean(self):
#         if self.metodo_pagamento_rapido and len(self.metodo_pagamento_rapido.strip()) < 2:
#             raise ValidationError("O método de pagamento rápido deve ter pelo menos 2 caracteres.")


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
    data_processamento = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=2, choices=STATUS_CHOICES, default='P')
    motivo = models.TextField(blank=True)
    notas = models.TextField(blank=True)  # Notas do administrador
    
    def __str__(self):
        return f"Reembolso de Pedido #{self.pedido.codigo}"

    def clean(self):
        if self.valor <= 0:
            raise ValidationError("O valor do reembolso deve ser positivo.")


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


# Modelo para Sistema de Wishlist Melhorado
class Wishlist(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    nome = models.CharField(max_length=100, default="Minha Lista")
    publica = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('usuario', 'nome')

    def __str__(self):
        return f"{self.usuario.username} - {self.nome}"


class ItemWishlist(models.Model):
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    variacao = models.ForeignKey(ProdutoVariacao, on_delete=models.CASCADE, null=True, blank=True)
    adicionado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('wishlist', 'produto', 'variacao')

    def __str__(self):
        return f"{self.wishlist.nome} - {self.produto.nome}"


class LogEstoque(models.Model):
    variacao = models.ForeignKey(ProdutoVariacao, on_delete=models.CASCADE, related_name='logs_estoque')
    quantidade = models.IntegerField()
    data = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    pedido = models.ForeignKey('Pedido', null=True, blank=True, on_delete=models.SET_NULL)
    motivo = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-data']

    def __str__(self):
        return f"{self.variacao} | {self.quantidade} | {self.data:%d/%m/%Y %H:%M}"

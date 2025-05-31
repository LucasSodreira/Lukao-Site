from django.db import models
from django.core.validators import (
    MinValueValidator,
    RegexValidator,
    MinLengthValidator,
    MaxValueValidator,
)
from django.conf import settings
from django.db.models import Avg
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.utils.text import slugify
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
import hashlib
import os
import logging
from typing import Optional, List
from functools import lru_cache
from uuid import uuid4
import json


# Configuração de logging
logger = logging.getLogger(__name__)

# Constantes
CACHE_TIMEOUT = 3600  # 1 hora
MAX_CACHE_SIZE = 1000
PRODUTO_CONFIG = {
    'MAX_PESO': 100.0,  # kg
    'MAX_DIMENSAO': 200,  # cm
    'MAX_PRECO': 100000.0,  # R$
    'MIN_PRECO': 0.01,  # R$
}

class Categoria(models.Model):
    nome = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True, db_index=True)
    descricao = models.TextField(blank=True, null=True)
    categoria_pai = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='subcategorias',
        db_index=True
    )
    ativo = models.BooleanField(default=True, db_index=True)
    ordem = models.PositiveIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordem', 'nome']
        indexes = [
            models.Index(fields=['nome', 'ativo']),
            models.Index(fields=['categoria_pai', 'ativo']),
        ]

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
            base_slug = slugify(self.nome)
            slug = base_slug
            counter = 1
            while Categoria.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        
        # Invalida cache
        cache.delete(f'categoria_{self.pk}')
        cache.delete('categorias_ativas')
        
        super().save(*args, **kwargs)

    @classmethod
    @lru_cache(maxsize=MAX_CACHE_SIZE)
    def get_categorias_ativas(cls) -> List['Categoria']:
        """Retorna categorias ativas com cache"""
        cache_key = 'categorias_ativas'
        categorias = cache.get(cache_key)
        
        if categorias is None:
            categorias = list(cls.objects.filter(
                ativo=True
            ).select_related(
                'categoria_pai'
            ).prefetch_related(
                'subcategorias'
            ).order_by('ordem', 'nome'))
            
            cache.set(cache_key, categorias, CACHE_TIMEOUT)
            
        return categorias

class Marca(models.Model):
    nome = models.CharField(max_length=50, unique=True, db_index=True)
    descricao = models.TextField(blank=True, null=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True, db_index=True)
    logo = models.ImageField(upload_to="marcas/", blank=True, null=True)
    ativo = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome']
        indexes = [
            models.Index(fields=['nome', 'ativo']),
        ]

    def __str__(self):
        return self.nome

    def clean(self):
        if not self.nome or len(self.nome.strip()) < 2:
            raise ValidationError("O nome da marca deve ter pelo menos 2 caracteres.")

    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.slug:
            base_slug = slugify(self.nome)
            slug = base_slug
            counter = 1
            while Marca.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
            
        # Invalida cache
        cache.delete(f'marca_{self.pk}')
        cache.delete('marcas_ativas')
        
        super().save(*args, **kwargs)

    @classmethod
    @lru_cache(maxsize=MAX_CACHE_SIZE)
    def get_marcas_ativas(cls) -> List['Marca']:
        """Retorna marcas ativas com cache"""
        cache_key = 'marcas_ativas'
        marcas = cache.get(cache_key)
        
        if marcas is None:
            marcas = list(cls.objects.filter(ativo=True).order_by('nome'))
            cache.set(cache_key, marcas, CACHE_TIMEOUT)
            
        return marcas

class AtributoTipo(models.Model):
    nome = models.CharField(max_length=50, unique=True, db_index=True)
    tipo = models.CharField(max_length=20, choices=[
        ('select', 'Seleção Única'),
        ('color', 'Cor'),
        ('size', 'Tamanho'),
        ('text', 'Texto Livre')
    ])
    obrigatorio = models.BooleanField(default=False, db_index=True, help_text="Se é obrigatório escolher este atributo")
    ordem = models.PositiveIntegerField(default=0, db_index=True, help_text="Ordem de exibição")
    ativo = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordem', 'nome']
        indexes = [
            models.Index(fields=['nome', 'ativo']),
            models.Index(fields=['tipo', 'ativo']),
        ]
        verbose_name = "Tipo de Atributo"
        verbose_name_plural = "Tipos de Atributos"

    def __str__(self):
        return self.nome

    def clean(self):
        if not self.nome or len(self.nome.strip()) < 2:
            raise ValidationError("O nome do tipo de atributo deve ter pelo menos 2 caracteres.")

    def save(self, *args, **kwargs):
        self.full_clean()
        # Invalida cache
        cache.delete(f'atributo_tipo_{self.pk}')
        cache.delete('atributos_tipos_ativos')
        super().save(*args, **kwargs)

    @classmethod
    @lru_cache(maxsize=MAX_CACHE_SIZE)
    def get_atributos_tipos_ativos(cls) -> List['AtributoTipo']:
        """Retorna tipos de atributos ativos com cache"""
        cache_key = 'atributos_tipos_ativos'
        tipos = cache.get(cache_key)
        
        if tipos is None:
            tipos = list(cls.objects.filter(
                ativo=True
            ).prefetch_related(
                'valores'
            ).order_by('ordem', 'nome'))
            
            cache.set(cache_key, tipos, CACHE_TIMEOUT)
            
        return tipos

class AtributoValor(models.Model):
    tipo = models.ForeignKey(
        AtributoTipo, 
        on_delete=models.CASCADE, 
        related_name='valores',
        db_index=True
    )
    valor = models.CharField(max_length=100, db_index=True)
    codigo = models.CharField(max_length=20, blank=True, db_index=True, help_text="Código interno (ex: 'M', 'GG', '#FF0000')")
    ordem = models.PositiveIntegerField(default=0, db_index=True)
    ativo = models.BooleanField(default=True, db_index=True)
    valor_adicional_preco = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Valor adicional ao preço do produto"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('tipo', 'valor')
        ordering = ['tipo', 'ordem', 'valor']
        indexes = [
            models.Index(fields=['tipo', 'valor', 'ativo']),
            models.Index(fields=['codigo', 'ativo']),
        ]
        verbose_name = "Valor de Atributo"
        verbose_name_plural = "Valores de Atributos"

    def __str__(self):
        return f"{self.tipo.nome}: {self.valor}"

    def clean(self):
        if not self.valor or len(self.valor.strip()) < 1:
            raise ValidationError("O valor do atributo não pode estar vazio.")
        if self.valor_adicional_preco < 0:
            raise ValidationError("O valor adicional não pode ser negativo.")

    def save(self, *args, **kwargs):
        self.full_clean()
        # Invalida cache
        cache.delete(f'atributo_valor_{self.pk}')
        cache.delete(f'atributo_tipo_{self.tipo_id}_valores')
        super().save(*args, **kwargs)

    @classmethod
    @lru_cache(maxsize=MAX_CACHE_SIZE)
    def get_valores_ativos_por_tipo(cls, tipo_id: int) -> List['AtributoValor']:
        """Retorna valores ativos de um tipo com cache"""
        cache_key = f'atributo_tipo_{tipo_id}_valores'
        valores = cache.get(cache_key)
        
        if valores is None:
            valores = list(cls.objects.filter(
                tipo_id=tipo_id,
                ativo=True
            ).order_by('ordem', 'valor'))
            
            cache.set(cache_key, valores, CACHE_TIMEOUT)
            
        return valores

class Produto(models.Model):
    visivel = models.BooleanField(default=True, db_index=True)
    nome = models.CharField(max_length=255, db_index=True)
    descricao = models.TextField(blank=True, null=True)
    preco = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(PRODUTO_CONFIG['MIN_PRECO'])]
    )
    categoria = models.ForeignKey(
        Categoria, 
        on_delete=models.CASCADE, 
        related_name='produtos',
        db_index=True
    )
    preco_original = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    desconto = models.IntegerField(null=True, blank=True)
    peso = models.DecimalField(
        max_digits=6, 
        decimal_places=3, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Peso do produto em kg"
    )
    width = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        help_text="Largura em cm"
    )
    height = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        help_text="Altura em cm"
    )
    length = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        help_text="Comprimento em cm"
    )
    imagem = models.ImageField(upload_to="produtos/", default="produtos/default.jpg")
    sku = models.CharField(max_length=50, unique=True, blank=True, null=True, db_index=True, help_text="SKU do produto")
    codigo_barras = models.CharField(max_length=50, blank=True, null=True, db_index=True, help_text="Código de barras")
    seo_title = models.CharField(max_length=70, blank=True, null=True)
    seo_description = models.CharField(max_length=160, blank=True, null=True)
    marca = models.ForeignKey(
        Marca, 
        on_delete=models.CASCADE, 
        related_name='produtos', 
        null=True, 
        blank=True,
        db_index=True
    )
    tags = models.ManyToManyField('Tag', blank=True, related_name='produtos')
    genero = models.CharField(
        max_length=20, 
        choices=[
            ('M', 'Masculino'),
            ('F', 'Feminino'),
            ('U', 'Unissex')
        ], 
        default='M',
        db_index=True
    )
    temporada = models.CharField(
        max_length=20, 
        choices=[
            ('verao', 'Verão'),
            ('inverno', 'Inverno'),
            ('meia_estacao', 'Meia Estação'),
            ('todo_ano', 'Todo Ano')
        ], 
        blank=True,
        db_index=True
    )
    cuidados = models.TextField(blank=True)
    origem = models.CharField(max_length=50, default="Brasil")
    ativo = models.BooleanField(default=True, db_index=True)
    destaque = models.BooleanField(default=False, db_index=True)
    preco_promocional = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    promocao_inicio = models.DateTimeField(null=True, blank=True)
    promocao_fim = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['nome', 'ativo']),
            models.Index(fields=['categoria', 'ativo']),
            models.Index(fields=['marca', 'ativo']),
            models.Index(fields=['preco', 'ativo']),
            models.Index(fields=['destaque', 'ativo']),
        ]

    def __str__(self):
        return f"{self.nome} (R${self.preco})"
    
    def delete(self, *args, **kwargs):
        if self.imagem and self.imagem.name != "produtos/default.jpg":
            if os.path.isfile(self.imagem.path):
                os.remove(self.imagem.path)
        # Invalida cache
        cache.delete(f'produto_{self.pk}')
        cache.delete(f'produto_slug_{self.slug}')
        super().delete(*args, **kwargs)

    def preco_vigente(self):
        """Retorna o preço atual do produto com cache"""
        cache_key = f'produto_{self.pk}_preco'
        preco = cache.get(cache_key)
        
        if preco is None:
            agora = timezone.now()
            if self.preco_promocional and self.promocao_inicio and self.promocao_fim:
                if self.promocao_inicio <= agora <= self.promocao_fim:
                    preco = self.preco_promocional
                else:
                    preco = self.preco
            else:
                preco = self.preco
                
            cache.set(cache_key, preco, CACHE_TIMEOUT)
            
        return preco
    
    def calcular_desconto(self):
        """Calcula o percentual de desconto com cache"""
        cache_key = f'produto_{self.pk}_desconto'
        desconto = cache.get(cache_key)
        
        if desconto is None:
            preco_base = self.preco_original or self.preco
            preco_atual = self.preco_vigente()
            if preco_base > preco_atual:
                desconto = round((1 - (preco_atual / preco_base)) * 100)
            else:
                desconto = 0
                
            cache.set(cache_key, desconto, CACHE_TIMEOUT)
            
        return desconto
    
    def get_tamanhos_disponiveis(self):
        """Retorna tamanhos disponíveis com cache"""
        cache_key = f'produto_{self.pk}_tamanhos'
        tamanhos = cache.get(cache_key)
        
        if tamanhos is None:
            tamanhos = []
            for variacao in self.variacoes.filter(estoque__gt=0):
                for atributo in variacao.atributos.filter(tipo__tipo='size'):
                    if atributo.valor not in tamanhos:
                        tamanhos.append(atributo.valor)
                        
            cache.set(cache_key, tamanhos, CACHE_TIMEOUT)
            
        return tamanhos
    
    def clean(self):
        super().clean()
        if self.preco_original and self.preco_original < self.preco:
            raise ValidationError("O preço original não pode ser menor que o preço atual.")
        if self.preco_promocional and self.preco_promocional > self.preco:
            raise ValidationError("O preço promocional deve ser menor que o preço atual.")
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
        if self.peso and self.peso > PRODUTO_CONFIG['MAX_PESO']:
            raise ValidationError(f"O peso não pode ser maior que {PRODUTO_CONFIG['MAX_PESO']}kg.")
        if self.width and self.width > PRODUTO_CONFIG['MAX_DIMENSAO']:
            raise ValidationError(f"A largura não pode ser maior que {PRODUTO_CONFIG['MAX_DIMENSAO']}cm.")
        if self.height and self.height > PRODUTO_CONFIG['MAX_DIMENSAO']:
            raise ValidationError(f"A altura não pode ser maior que {PRODUTO_CONFIG['MAX_DIMENSAO']}cm.")
        if self.length and self.length > PRODUTO_CONFIG['MAX_DIMENSAO']:
            raise ValidationError(f"O comprimento não pode ser maior que {PRODUTO_CONFIG['MAX_DIMENSAO']}cm.")
        if self.preco > PRODUTO_CONFIG['MAX_PRECO']:
            raise ValidationError(f"O preço não pode ser maior que R${PRODUTO_CONFIG['MAX_PRECO']}.")

    def media_avaliacoes(self):
        """Retorna média das avaliações com cache"""
        cache_key = f'produto_{self.pk}_media_avaliacoes'
        media = cache.get(cache_key)
        
        if media is None:
            media = self.avaliacoes.aggregate(media=Avg('nota'))['media'] or 0.0
            cache.set(cache_key, media, CACHE_TIMEOUT)
            
        return media

    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.seo_title:
            self.seo_title = self.nome[:70]
        if not self.slug:
            base_slug = slugify(self.nome)
            slug = base_slug
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
        
        # Invalida cache
        cache.delete(f'produto_{self.pk}')
        cache.delete(f'produto_slug_{self.slug}')
        cache.delete(f'produto_{self.pk}_preco')
        cache.delete(f'produto_{self.pk}_desconto')
        cache.delete(f'produto_{self.pk}_tamanhos')
        cache.delete(f'produto_{self.pk}_media_avaliacoes')
        
        super().save(*args, **kwargs)
        
        # Só criar histórico se preço mudou
        if preco_antigo is not None and preco_antigo != self.preco:
            HistoricoPreco.objects.create(produto=self, preco=self.preco)

    @classmethod
    def get_produtos_ativos(cls) -> List['Produto']:
        """Retorna produtos ativos com cache"""
        cache_key = 'produtos_ativos'
        produtos = cache.get(cache_key)
        
        if produtos is None:
            produtos = list(cls.objects.filter(
                ativo=True,
                visivel=True
            ).select_related(
                'categoria',
                'marca'
            ).prefetch_related(
                'tags',
                'variacoes'
            ).order_by('-created_at'))
            
            cache.set(cache_key, produtos, CACHE_TIMEOUT)
            
        return produtos

    @classmethod
    def get_produtos_destaque(cls) -> List['Produto']:
        """Retorna produtos em destaque com cache"""
        cache_key = 'produtos_destaque'
        produtos = cache.get(cache_key)
        
        if produtos is None:
            produtos = list(cls.objects.filter(
                ativo=True,
                visivel=True,
                destaque=True
            ).select_related(
                'categoria',
                'marca'
            ).prefetch_related(
                'tags',
                'variacoes'
            ).order_by('-created_at'))
            
            cache.set(cache_key, produtos, CACHE_TIMEOUT)
            
        return produtos

class ProdutoVariacao(models.Model):
    produto = models.ForeignKey(
        Produto, 
        on_delete=models.CASCADE, 
        related_name='variacoes',
        db_index=True
    )
    atributos = models.ManyToManyField(
        AtributoValor, 
        related_name='variacoes',
        db_index=True
    )
    sku = models.CharField(max_length=50, unique=True, blank=True, null=True, db_index=True)
    estoque = models.PositiveIntegerField(default=0, db_index=True)
    ativo = models.BooleanField(default=True, db_index=True, help_text="Se a variação está ativa/visível")
    preco_adicional = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Preço adicional da variação"
    )
    peso = models.DecimalField(
        max_digits=6, 
        decimal_places=3, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Peso da variação em kg"
    )
    width = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        help_text="Largura em cm"
    )
    height = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        help_text="Altura em cm"
    )
    length = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        help_text="Comprimento em cm"
    )
    atributos_hash = models.CharField(max_length=128, editable=False, db_index=True)
    preco_promocional = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    promocao_inicio = models.DateTimeField(null=True, blank=True)
    promocao_fim = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Variação de Produto"
        verbose_name_plural = "Variações de Produtos"
        indexes = [
            models.Index(fields=['produto', 'ativo']),
            models.Index(fields=['estoque', 'ativo']),
            models.Index(fields=['sku', 'ativo']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['produto', 'atributos_hash'], name='unique_produto_atributos')
        ]

    def __str__(self):
        try:
            if self.pk and self.atributos.exists():
                atributos_str = " - ".join([f"{attr.tipo.nome}: {attr.valor}" for attr in self.atributos.all()])
                return f"{self.produto.nome} - {atributos_str}"
            return f"{self.produto.nome} - Variação (sem atributos definidos)"
        except:
            return f"Variação de {getattr(self.produto, 'nome', 'Produto')} (ID: {self.pk or 'Novo'})"
    
    def clean(self):
        super().clean()
        
        # Validar atributos obrigatórios
        tipos_obrigatorios = AtributoTipo.objects.filter(obrigatorio=True)
        atributos_tipos = [attr.tipo for attr in self.atributos.all()]
        
        for tipo in tipos_obrigatorios:
            if tipo not in atributos_tipos:
                raise ValidationError(f"Atributo obrigatório '{tipo.nome}' não foi selecionado.")
        
        # Validar atributos duplicados
        tipos_selecionados = []
        for attr in self.atributos.all():
            if attr.tipo in tipos_selecionados:
                raise ValidationError(f"Múltiplos valores para '{attr.tipo.nome}' não são permitidos.")
            tipos_selecionados.append(attr.tipo)
            
        # Validar combinação única
        if self.pk:
            variacoes_existentes = ProdutoVariacao.objects.filter(produto=self.produto).exclude(pk=self.pk)
        else:
            variacoes_existentes = ProdutoVariacao.objects.filter(produto=self.produto)
            
        for variacao_existente in variacoes_existentes:
            atributos_existentes = set(variacao_existente.atributos.all())
            atributos_novos = set(self.atributos.all())
            
            if atributos_existentes == atributos_novos:
                raise ValidationError("Já existe uma variação com essa combinação de atributos para este produto.")
                
        # Validar dimensões
        if self.peso and self.peso > PRODUTO_CONFIG['MAX_PESO']:
            raise ValidationError(f"O peso não pode ser maior que {PRODUTO_CONFIG['MAX_PESO']}kg.")
        if self.width and self.width > PRODUTO_CONFIG['MAX_DIMENSAO']:
            raise ValidationError(f"A largura não pode ser maior que {PRODUTO_CONFIG['MAX_DIMENSAO']}cm.")
        if self.height and self.height > PRODUTO_CONFIG['MAX_DIMENSAO']:
            raise ValidationError(f"A altura não pode ser maior que {PRODUTO_CONFIG['MAX_DIMENSAO']}cm.")
        if self.length and self.length > PRODUTO_CONFIG['MAX_DIMENSAO']:
            raise ValidationError(f"O comprimento não pode ser maior que {PRODUTO_CONFIG['MAX_DIMENSAO']}cm.")
    
    def gerar_sku_automatico(self):
        """Gera SKU automaticamente baseado no produto e atributos"""
        if not self.sku and self.produto.sku:
            sufixos = []
            for attr in self.atributos.all().order_by('tipo__ordem', 'tipo__nome'):
                if attr.codigo:
                    sufixos.append(attr.codigo)
                else:
                    sufixos.append(attr.valor[:3].upper())
            
            if sufixos:
                self.sku = f"{self.produto.sku}-{'-'.join(sufixos)}"
    
    def calcular_hash_atributos(self):
        """Calcula hash único para combinação de atributos"""
        ids = sorted(str(attr.id) for attr in self.atributos.all())
        return hashlib.sha256("-".join(ids).encode()).hexdigest()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        self.atributos_hash = self.calcular_hash_atributos()
        super().save(update_fields=['atributos_hash'])
        
        # Invalida cache
        cache.delete(f'produto_{self.produto_id}')
        cache.delete(f'produto_{self.produto_id}_variacoes')
        cache.delete(f'variacao_{self.pk}')
    
    def preco_final(self):
        """Retorna preço final com cache"""
        cache_key = f'variacao_{self.pk}_preco'
        preco = cache.get(cache_key)
        
        if preco is None:
            agora = timezone.now()
            if self.preco_promocional and self.promocao_inicio and self.promocao_fim:
                if self.promocao_inicio <= agora <= self.promocao_fim:
                    preco = self.preco_promocional
                else:
                    preco = self.produto.preco_vigente() + self.preco_adicional
            else:
                preco = self.produto.preco_vigente() + self.preco_adicional
                
            cache.set(cache_key, preco, CACHE_TIMEOUT)
            
        return preco

    def diminuir_estoque(self, quantidade: int):
        """Diminui estoque com validação e log"""
        if quantidade <= 0:
            raise ValidationError("Quantidade deve ser maior que zero")
            
        if self.estoque < quantidade:
            raise ValidationError("Estoque insuficiente")
            
        self.estoque -= quantidade
        self.save(update_fields=['estoque'])
        
        # Registra log
        LogEstoque.objects.create(
            variacao=self,
            quantidade=-quantidade,
            motivo="Venda"
        )

    def aumentar_estoque(self, quantidade: int):
        """Aumenta estoque com validação e log"""
        if quantidade <= 0:
            raise ValidationError("Quantidade deve ser maior que zero")
            
        self.estoque += quantidade
        self.save(update_fields=['estoque'])
        
        # Registra log
        LogEstoque.objects.create(
            variacao=self,
            quantidade=quantidade,
            motivo="Devolução"
        )

    @classmethod
    def get_variacoes_ativas(cls, produto_id: int) -> List['ProdutoVariacao']:
        """Retorna variações ativas de um produto com cache"""
        cache_key = f'produto_{produto_id}_variacoes'
        variacoes = cache.get(cache_key)
        
        if variacoes is None:
            variacoes = list(cls.objects.filter(
                produto_id=produto_id,
                ativo=True
            ).prefetch_related(
                'atributos',
                'atributos__tipo'
            ).order_by('atributos__tipo__ordem', 'atributos__ordem'))
            
            cache.set(cache_key, variacoes, CACHE_TIMEOUT)
            
        return variacoes

class ImagemProduto(models.Model):
    produto = models.ForeignKey(
        Produto, 
        on_delete=models.CASCADE, 
        related_name='imagens',
        db_index=True
    )
    imagem = models.ImageField(upload_to="produtos/galeria/")
    destaque = models.BooleanField(default=False, db_index=True)
    ordem = models.PositiveIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordem']
        indexes = [
            models.Index(fields=['produto', 'destaque']),
        ]

    def __str__(self):
        return f"Imagem de {self.produto.nome}"

    def clean(self):
        if not self.imagem:
            raise ValidationError("A imagem é obrigatória.")

    def delete(self, *args, **kwargs):
        if self.imagem and os.path.isfile(self.imagem.path):
            os.remove(self.imagem.path)
        # Invalida cache
        cache.delete(f'produto_{self.produto_id}_imagens')
        super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.full_clean()
        # Invalida cache
        cache.delete(f'produto_{self.produto_id}_imagens')
        super().save(*args, **kwargs)

    @classmethod
    def get_imagens_produto(cls, produto_id: int) -> List['ImagemProduto']:
        """Retorna imagens de um produto com cache"""
        cache_key = f'produto_{produto_id}_imagens'
        imagens = cache.get(cache_key)
        
        if imagens is None:
            imagens = list(cls.objects.filter(
                produto_id=produto_id
            ).order_by('ordem'))
            
            cache.set(cache_key, imagens, CACHE_TIMEOUT)
            
        return imagens

class AvaliacaoProduto(models.Model):
    produto = models.ForeignKey(
        Produto, 
        on_delete=models.CASCADE, 
        related_name='avaliacoes',
        db_index=True
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        db_index=True
    )
    nota = models.PositiveSmallIntegerField()
    comentario = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    aprovada = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['produto', 'aprovada']),
            models.Index(fields=['usuario', 'aprovada']),
        ]
        unique_together = ('produto', 'usuario')

    def __str__(self):
        return f"{self.usuario} - {self.produto.nome} ({self.nota})"

    def clean(self):
        if self.nota < 1 or self.nota > 5:
            raise ValidationError("A nota deve ser entre 1 e 5.")
        if self.comentario and len(self.comentario.strip()) < 10:
            raise ValidationError("O comentário deve ter pelo menos 10 caracteres.")

    def save(self, *args, **kwargs):
        self.full_clean()
        # Invalida cache
        cache.delete(f'produto_{self.produto_id}_avaliacoes')
        cache.delete(f'produto_{self.produto_id}_media_avaliacoes')
        super().save(*args, **kwargs)

    @classmethod
    def get_avaliacoes_produto(cls, produto_id: int) -> List['AvaliacaoProduto']:
        """Retorna avaliações de um produto com cache"""
        cache_key = f'produto_{produto_id}_avaliacoes'
        avaliacoes = cache.get(cache_key)
        
        if avaliacoes is None:
            avaliacoes = list(cls.objects.filter(
                produto_id=produto_id,
                aprovada=True
            ).select_related(
                'usuario'
            ).order_by('-criado_em'))
            
            cache.set(cache_key, avaliacoes, CACHE_TIMEOUT)
            
        return avaliacoes

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
        max_length=100, 
        verbose_name="Nome Completo", 
        validators=[MinLengthValidator(3)],
        db_index=True
    )
    telefone = models.CharField(
        max_length=15,
        validators=[
            RegexValidator(
                regex=r"^\(\d{2}\) \d{4,5}-\d{4}$",
                message="Telefone deve estar no formato (99) 99999-9999",
            )
        ],
        db_index=True
    )
    rua = models.CharField(max_length=200, verbose_name="Logradouro", db_index=True)
    numero = models.CharField(max_length=20, verbose_name="Número")
    complemento = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name="Complemento"
    )
    bairro = models.CharField(max_length=100, verbose_name="Bairro", db_index=True)
    cep = models.CharField(
        max_length=9,
        validators=[
            RegexValidator(
                regex=r"^\d{5}-\d{3}$", 
                message="CEP deve estar no formato 12345-678"
            )
        ],
        db_index=True
    )
    cidade = models.CharField(max_length=100, db_index=True)
    estado = models.CharField(
        max_length=2, 
        choices=ESTADO_CHOICES, 
        verbose_name="UF",
        db_index=True
    )
    pais = models.CharField(max_length=50, default="Brasil")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enderecos",
        null=True,
        blank=True,
        db_index=True
    )
    principal = models.BooleanField(
        default=False, 
        verbose_name="Endereço Principal",
        db_index=True
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Última Atualização")

    class Meta:
        verbose_name = "Endereço"
        verbose_name_plural = "Endereços"
        ordering = ["-principal", "-criado_em"]
        indexes = [
            models.Index(fields=['usuario', 'principal']),
            models.Index(fields=['cep', 'numero']),
            models.Index(fields=['cidade', 'estado']),
        ]

    def __str__(self):
        return f"{self.nome_completo} - {self.rua}, {self.numero}, {self.cidade}/{self.estado}"

    def clean(self):
        if self.nome_completo and len(self.nome_completo.strip()) < 3:
            raise ValidationError("O nome completo deve ter pelo menos 3 caracteres.")
        if self.numero and len(self.numero.strip()) == 0:
            raise ValidationError("O número do endereço é obrigatório.")
        if self.cidade and len(self.cidade.strip()) < 2:
            raise ValidationError("O nome da cidade deve ter pelo menos 2 caracteres.")
        if self.rua and len(self.rua.strip()) < 3:
            raise ValidationError("O logradouro deve ter pelo menos 3 caracteres.")
        if self.bairro and len(self.bairro.strip()) < 2:
            raise ValidationError("O bairro deve ter pelo menos 2 caracteres.")

    def save(self, *args, **kwargs):
        self.full_clean()
        # Garante que só tenha um endereço principal por usuário
        if self.principal and self.usuario:
            Endereco.objects.filter(
                usuario=self.usuario, 
                principal=True
            ).exclude(
                pk=self.pk
            ).update(principal=False)
            
        # Invalida cache
        if self.usuario:
            cache.delete(f'usuario_{self.usuario_id}_enderecos')
            cache.delete(f'usuario_{self.usuario_id}_endereco_principal')
            
        super().save(*args, **kwargs)

    @classmethod
    def get_enderecos_usuario(cls, usuario_id: int) -> List['Endereco']:
        """Retorna endereços de um usuário com cache"""
        cache_key = f'usuario_{usuario_id}_enderecos'
        enderecos = cache.get(cache_key)
        
        if enderecos is None:
            enderecos = list(cls.objects.filter(
                usuario_id=usuario_id
            ).order_by('-principal', '-criado_em'))
            
            cache.set(cache_key, enderecos, CACHE_TIMEOUT)
            
        return enderecos

    @classmethod
    def get_endereco_principal(cls, usuario_id: int) -> Optional['Endereco']:
        """Retorna endereço principal de um usuário com cache"""
        cache_key = f'usuario_{usuario_id}_endereco_principal'
        endereco = cache.get(cache_key)
        
        if endereco is None:
            endereco = cls.objects.filter(
                usuario_id=usuario_id,
                principal=True
            ).first()
            
            if endereco:
                cache.set(cache_key, endereco, CACHE_TIMEOUT)
            
        return endereco

class Cupom(models.Model):
    TIPO_CHOICES = [
        ('percentual', 'Desconto Percentual'),
        ('valor_fixo', 'Valor Fixo'),
        ('frete_gratis', 'Frete Grátis'),
        ('compre_leve', 'Compre X Leve Y'),
    ]
    
    codigo = models.CharField(max_length=30, unique=True, db_index=True)
    descricao = models.CharField(max_length=255, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='percentual', db_index=True)
    desconto_percentual = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    desconto_valor = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0)]
    )    
    ativo = models.BooleanField(default=True, db_index=True)
    validade_inicio = models.DateTimeField(null=True, blank=True, help_text="Data de início da validade")
    validade_fim = models.DateTimeField(null=True, blank=True, help_text="Data de fim da validade", db_index=True)
    uso_unico = models.BooleanField(default=False, help_text="Permite apenas um uso por usuário")
    max_usos = models.PositiveIntegerField(null=True, blank=True, help_text="Número máximo de usos totais")
    usos = models.PositiveIntegerField(default=0, help_text="Quantas vezes foi usado")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL, 
        help_text="Cupom exclusivo para um usuário",
        db_index=True
    )
    valor_minimo_pedido = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        help_text="Valor mínimo do pedido para usar o cupom",
        validators=[MinValueValidator(0)]
    )
    valor_maximo_desconto = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        help_text="Valor máximo de desconto a ser aplicado",
        validators=[MinValueValidator(0)]
    )
    primeira_compra_apenas = models.BooleanField(
        default=False, 
        help_text="Válido apenas para primeira compra",
        db_index=True
    )
    aplicar_apenas_itens_elegiveis = models.BooleanField(
        default=False, 
        help_text="Se True, aplica desconto apenas aos itens elegíveis. Se False, aplica ao total do pedido"
    )
    categorias_aplicaveis = models.ManyToManyField(
        'Categoria', 
        blank=True, 
        help_text="Categorias onde o cupom é aplicável",
        db_index=True
    )
    produtos_aplicaveis = models.ManyToManyField(
        'Produto', 
        blank=True, 
        help_text="Produtos específicos onde o cupom é aplicável",
        db_index=True
    )
    quantidade_comprar = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        help_text="Quantidade para comprar (tipo compre_leve)"
    )
    quantidade_levar = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        help_text="Quantidade para levar grátis (tipo compre_leve)"
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cupom"
        verbose_name_plural = "Cupons"
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['codigo', 'ativo']),
            models.Index(fields=['tipo', 'ativo']),
            models.Index(fields=['validade_fim', 'ativo']),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.get_tipo_display()}"

    def is_valido(self, user=None, pedido_valor=None, produtos=None):
        """Verifica se o cupom é válido para uso"""
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
        if self.primeira_compra_apenas and user and Pedido.objects.filter(
            usuario=user, 
            status__in=['PA', 'E', 'T', 'C']
        ).exists():
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
        """Aplica o desconto do cupom ao total informado"""
        if self.tipo == 'frete_gratis':
            return total, {'tipo': 'frete_gratis', 'desconto': 0}
            
        elif self.tipo == 'compre_leve' and itens_pedido:
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
            if self.aplicar_apenas_itens_elegiveis and itens_pedido and (self.produtos_aplicaveis.exists() or self.categorias_aplicaveis.exists()):
                total_elegiveis = 0
                for item in itens_pedido:
                    if self._produto_aplicavel(item.produto):
                        total_elegiveis += item.preco_unitario * item.quantidade
                
                if total_elegiveis == 0:
                    return total, {'tipo': self.tipo, 'desconto': 0}
                
                if self.desconto_percentual:
                    desconto = total_elegiveis * (self.desconto_percentual / 100)
                elif self.desconto_valor:
                    desconto = self.desconto_valor
                else:
                    desconto = 0
                    
                if self.valor_maximo_desconto:
                    desconto = min(desconto, self.valor_maximo_desconto)
                    
                desconto_aplicado = min(desconto, total_elegiveis)
                return max(total - desconto_aplicado, 0), {
                    'tipo': self.tipo, 
                    'desconto': desconto_aplicado, 
                    'total_elegiveis': total_elegiveis
                }
            else:
                if self.desconto_percentual:
                    desconto = total * (self.desconto_percentual / 100)
                elif self.desconto_valor:
                    desconto = self.desconto_valor
                else:
                    desconto = 0
                    
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
        # Invalida cache
        cache.delete(f'cupom_{self.codigo}')

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

    def save(self, *args, **kwargs):
        self.full_clean()
        # Invalida cache
        cache.delete(f'cupom_{self.codigo}')
        super().save(*args, **kwargs)

    @classmethod
    def get_cupom_por_codigo(cls, codigo: str) -> Optional['Cupom']:
        """Retorna cupom por código com cache"""
        cache_key = f'cupom_{codigo}'
        cupom = cache.get(cache_key)
        
        if cupom is None:
            cupom = cls.objects.filter(
                codigo=codigo,
                ativo=True
            ).prefetch_related(
                'produtos_aplicaveis',
                'categorias_aplicaveis'
            ).first()
            
            if cupom:
                cache.set(cache_key, cupom, CACHE_TIMEOUT)
            
        return cupom

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
        db_index=True
    )
    codigo = models.CharField(
        max_length=10,
        unique=True,
        editable=False,
        verbose_name="Código do Pedido",
        db_index=True
    )
    status = models.CharField(
        max_length=2, 
        choices=STATUS_CHOICES, 
        default="P", 
        db_index=True
    )
    endereco_entrega = models.ForeignKey(
        Endereco, 
        on_delete=models.SET_NULL, 
        null=True,
        db_index=True
    )
    total = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)]
    )
    frete_valor = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)]
    )
    codigo_rastreamento = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Código de Rastreio",
        db_index=True
    )
    metodo_pagamento = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Método de Pagamento",
        db_index=True
    )
    data_criacao = models.DateTimeField(auto_now_add=True, db_index=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    cupom = models.ForeignKey(
        Cupom, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        db_index=True
    )
    payment_intent_id = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        db_index=True
    )
    frete_id = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        db_index=True
    )
    melhor_envio_id = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        db_index=True
    )

    class Meta:
        ordering = ["-data_criacao"]
        indexes = [
            models.Index(fields=['usuario', 'status']),
            models.Index(fields=['data_criacao', 'status']),
            models.Index(fields=['codigo', 'status']),
        ]

    def __str__(self):
        return f"Pedido {self.codigo}"
    
    def calcular_total(self):
        """Calcula o total do pedido incluindo frete e descontos de cupom com cache"""
        cache_key = f'pedido_{self.pk}_total'
        total = cache.get(cache_key)
        
        if total is None:
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
                        total = total_itens
                    else:
                        total, _ = self.cupom.aplicar(total_com_frete, self.itens.all())
                else:
                    total = total_com_frete
            else:
                total = total_com_frete
                
            cache.set(cache_key, total, CACHE_TIMEOUT)
            
        return total
        
    def calcular_desconto_cupom(self):
        """Retorna informações sobre o desconto aplicado pelo cupom com cache"""
        cache_key = f'pedido_{self.pk}_desconto_cupom'
        info_desconto = cache.get(cache_key)
        
        if info_desconto is None:
            if not self.cupom:
                info_desconto = {'tem_desconto': False, 'valor_desconto': 0, 'tipo': None}
            else:
                total_sem_desconto = sum(item.preco_unitario * item.quantidade for item in self.itens.all()) + self.frete_valor
                total_com_desconto = self.calcular_total()
                
                desconto = total_sem_desconto - total_com_desconto
                
                info_desconto = {
                    'tem_desconto': desconto > 0,
                    'valor_desconto': desconto,
                    'tipo': self.cupom.tipo,
                    'codigo': self.cupom.codigo
                }
                
            cache.set(cache_key, info_desconto, CACHE_TIMEOUT)
            
        return info_desconto
        
    def atualizar_estoque(self, operacao="diminuir"):
        """Atualiza o estoque das variações dos itens do pedido com validação"""
        with transaction.atomic():
            for item in self.itens.all():
                variacao = getattr(item, 'variacao', None)
                produto = item.produto
                
                if variacao:
                    if operacao == "diminuir":
                        if variacao.estoque < item.quantidade:
                            raise ValidationError(f"Estoque insuficiente para o produto {produto.nome}")
                        variacao.estoque = max(0, variacao.estoque - item.quantidade)
                    elif operacao == "aumentar":
                        variacao.estoque += item.quantidade
                    variacao.save()
                    
                    # Registra log
                    LogEstoque.objects.create(
                        variacao=variacao,
                        quantidade=-item.quantidade if operacao == "diminuir" else item.quantidade,
                        motivo=f"{'Venda' if operacao == 'diminuir' else 'Devolução'} - Pedido {self.codigo}",
                        pedido=self
                    )

    def clean(self):
        if self.total is not None and self.total < 0:
            raise ValidationError("O total do pedido não pode ser negativo.")
        if self.frete_valor is not None and self.frete_valor < 0:
            raise ValidationError("O valor do frete não pode ser negativo.")
        if self.status not in dict(self.STATUS_CHOICES):
            raise ValidationError("Status inválido.")
    
    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = str(uuid4()).split("-")[0].upper()
        
        creating = self.pk is None
        status_antigo = None
        
        if not creating:
            status_antigo = Pedido.objects.get(pk=self.pk).status
        
        self.full_clean()
        super().save(*args, **kwargs)
        
        if not creating:
            self.total = self.calcular_total()
            super().save(update_fields=['total'])
            
            # Lógica de atualização de estoque baseada na mudança de status
            if status_antigo and status_antigo != self.status:
                if status_antigo not in ["PA", "E", "T", "C"] and self.status == "PA":
                    self.atualizar_estoque("diminuir")
                elif status_antigo in ["PA", "E", "T", "C"] and self.status in ["X", "D"]:
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
            
        # Invalida cache
        cache.delete(f'pedido_{self.pk}_total')
        cache.delete(f'pedido_{self.pk}_desconto_cupom')
        if self.usuario:
            cache.delete(f'usuario_{self.usuario_id}_pedidos')
            cache.delete(f'usuario_{self.usuario_id}_pedidos_ativos')

    @classmethod
    def get_pedidos_usuario(cls, usuario_id: int) -> List['Pedido']:
        """Retorna pedidos de um usuário com cache"""
        cache_key = f'usuario_{usuario_id}_pedidos'
        pedidos = cache.get(cache_key)
        
        if pedidos is None:
            pedidos = list(cls.objects.filter(
                usuario_id=usuario_id
            ).select_related(
                'endereco_entrega',
                'cupom'
            ).prefetch_related(
                'itens',
                'itens__produto',
                'itens__variacao'
            ).order_by('-data_criacao'))
            
            cache.set(cache_key, pedidos, CACHE_TIMEOUT)
            
        return pedidos

    @classmethod
    def get_pedidos_ativos(cls, usuario_id: int) -> List['Pedido']:
        """Retorna pedidos ativos de um usuário com cache"""
        cache_key = f'usuario_{usuario_id}_pedidos_ativos'
        pedidos = cache.get(cache_key)
        
        if pedidos is None:
            pedidos = list(cls.objects.filter(
                usuario_id=usuario_id,
                status__in=['P', 'PA', 'E', 'T']
            ).select_related(
                'endereco_entrega',
                'cupom'
            ).prefetch_related(
                'itens',
                'itens__produto',
                'itens__variacao'
            ).order_by('-data_criacao'))
            
            cache.set(cache_key, pedidos, CACHE_TIMEOUT)
            
        return pedidos

class ItemPedido(models.Model):
    pedido = models.ForeignKey(
        Pedido, 
        on_delete=models.CASCADE, 
        related_name="itens",
        db_index=True
    )
    produto = models.ForeignKey(
        Produto, 
        on_delete=models.CASCADE,
        db_index=True
    )
    quantidade = models.PositiveIntegerField(default=1)
    preco_unitario = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    variacao = models.ForeignKey(
        ProdutoVariacao, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        db_index=True
    )

    class Meta:
        indexes = [
            models.Index(fields=['pedido', 'produto']),
            models.Index(fields=['produto', 'variacao']),
        ]

    def __str__(self):
        return f"{self.produto} x {self.quantidade}"

    def preco_total(self):
        """Calcula o preço total do item com cache"""
        cache_key = f'item_pedido_{self.pk}_preco_total'
        preco_total = cache.get(cache_key)
        
        if preco_total is None:
            preco_total = self.preco_unitario * self.quantidade
            cache.set(cache_key, preco_total, CACHE_TIMEOUT)
            
        return preco_total

    def clean(self):
        if self.quantidade < 1:
            raise ValidationError("A quantidade do item deve ser pelo menos 1.")
        if self.preco_unitario is not None and self.preco_unitario < 0:
            raise ValidationError("O preço unitário não pode ser negativo.")
        if self.variacao and self.variacao.produto != self.produto:
            raise ValidationError("A variação deve pertencer ao produto selecionado.")

    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.preco_unitario:
            if self.variacao:
                self.preco_unitario = self.variacao.preco_final()
            else:
                self.preco_unitario = self.produto.preco_vigente()
        
        super().save(*args, **kwargs)
        self.pedido.save()  # Atualiza o total do pedido
        
        # Invalida cache
        cache.delete(f'item_pedido_{self.pk}_preco_total')
        cache.delete(f'pedido_{self.pedido_id}_total')
        cache.delete(f'pedido_{self.pedido_id}_desconto_cupom')

    def delete(self, *args, **kwargs):
        """Atualiza o total do pedido após deletar item"""
        pedido = self.pedido
        super().delete(*args, **kwargs)
        pedido.save()
        
        # Invalida cache
        cache.delete(f'pedido_{pedido.id}_total')
        cache.delete(f'pedido_{pedido.id}_desconto_cupom')

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
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='carrinho',
        db_index=True
    )
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['usuario', 'criado_em']),
        ]

    def calcular_total(self):
        """Calcula o total do carrinho com cache"""
        cache_key = f'carrinho_{self.pk}_total'
        total = cache.get(cache_key)
        
        if total is None:
            total = sum(item.preco_total() for item in self.itens.all())
            cache.set(cache_key, total, CACHE_TIMEOUT)
            
        return total

    def quantidade_total(self):
        """Calcula quantidade total de itens com cache"""
        cache_key = f'carrinho_{self.pk}_quantidade'
        quantidade = cache.get(cache_key)
        
        if quantidade is None:
            quantidade = sum(item.quantidade for item in self.itens.all())
            cache.set(cache_key, quantidade, CACHE_TIMEOUT)
            
        return quantidade

    def clean(self):
        if not self.usuario_id:
            raise ValidationError("Usuário é obrigatório para o carrinho.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        # Invalida cache
        cache.delete(f'carrinho_{self.pk}_total')
        cache.delete(f'carrinho_{self.pk}_quantidade')
        if self.usuario:
            cache.delete(f'usuario_{self.usuario_id}_carrinho')

    @classmethod
    def get_carrinho_usuario(cls, usuario_id: int) -> Optional['Carrinho']:
        """Retorna carrinho de um usuário com cache"""
        cache_key = f'usuario_{usuario_id}_carrinho'
        carrinho = cache.get(cache_key)
        
        if carrinho is None:
            carrinho = cls.objects.filter(
                usuario_id=usuario_id
            ).prefetch_related(
                'itens',
                'itens__produto',
                'itens__variacao'
            ).first()
            
            if carrinho:
                cache.set(cache_key, carrinho, CACHE_TIMEOUT)
            
        return carrinho

class ItemCarrinho(models.Model):
    carrinho = models.ForeignKey(
        Carrinho, 
        on_delete=models.CASCADE, 
        related_name='itens',
        db_index=True
    )
    produto = models.ForeignKey(
        Produto, 
        on_delete=models.CASCADE,
        db_index=True
    )
    quantidade = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )
    variacao = models.ForeignKey(
        ProdutoVariacao, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        db_index=True
    )

    class Meta:
        unique_together = ('carrinho', 'produto', 'variacao')
        indexes = [
            models.Index(fields=['carrinho', 'produto']),
            models.Index(fields=['produto', 'variacao']),
        ]

    def preco_unitario(self):
        """Retorna preço unitário com cache"""
        cache_key = f'item_carrinho_{self.pk}_preco_unitario'
        preco = cache.get(cache_key)
        
        if preco is None:
            if self.variacao:
                preco = self.variacao.preco_final()
            else:
                preco = self.produto.preco_vigente()
            cache.set(cache_key, preco, CACHE_TIMEOUT)
            
        return preco

    def preco_total(self):
        """Calcula preço total com cache"""
        cache_key = f'item_carrinho_{self.pk}_preco_total'
        total = cache.get(cache_key)
        
        if total is None:
            total = self.preco_unitario() * self.quantidade
            cache.set(cache_key, total, CACHE_TIMEOUT)
            
        return total

    def clean(self):
        if self.quantidade < 1:
            raise ValidationError("A quantidade do item do carrinho deve ser pelo menos 1.")
        if self.variacao and self.variacao.produto != self.produto:
            raise ValidationError("A variação deve pertencer ao produto selecionado.")
        if self.variacao and self.variacao.estoque < self.quantidade:
            raise ValidationError("Quantidade indisponível em estoque.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        # Invalida cache
        cache.delete(f'item_carrinho_{self.pk}_preco_unitario')
        cache.delete(f'item_carrinho_{self.pk}_preco_total')
        cache.delete(f'carrinho_{self.carrinho_id}_total')
        cache.delete(f'carrinho_{self.carrinho_id}_quantidade')

    def delete(self, *args, **kwargs):
        carrinho = self.carrinho
        super().delete(*args, **kwargs)
        # Invalida cache
        cache.delete(f'carrinho_{carrinho.id}_total')
        cache.delete(f'carrinho_{carrinho.id}_quantidade')

class Reembolso(models.Model):
    STATUS_CHOICES = (
        ('P', 'Pendente'),
        ('A', 'Aprovado'),
        ('R', 'Rejeitado'),
        ('C', 'Concluído'),
    )
    
    pedido = models.OneToOneField(
        Pedido, 
        related_name='reembolso', 
        on_delete=models.CASCADE,
        db_index=True
    )
    valor = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    data_criacao = models.DateTimeField(auto_now_add=True, db_index=True)
    data_processamento = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=2, 
        choices=STATUS_CHOICES, 
        default='P',
        db_index=True
    )
    motivo = models.TextField(blank=True)
    notas = models.TextField(blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['pedido', 'status']),
            models.Index(fields=['data_criacao', 'status']),
        ]

    def __str__(self):
        return f"Reembolso de Pedido #{self.pedido.codigo}"

    def clean(self):
        if self.valor <= 0:
            raise ValidationError("O valor do reembolso deve ser positivo.")
        if self.valor > self.pedido.total:
            raise ValidationError("O valor do reembolso não pode ser maior que o valor do pedido.")
        if self.status not in dict(self.STATUS_CHOICES):
            raise ValidationError("Status inválido.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        # Invalida cache
        cache.delete(f'pedido_{self.pedido_id}_reembolso')
        cache.delete(f'pedido_{self.pedido_id}_total')

class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='notifications',
        on_delete=models.CASCADE,
        db_index=True
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='actor_notifications',
        on_delete=models.CASCADE,
        null=True,
        db_index=True
    )
    verb = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    unread = models.BooleanField(default=True, db_index=True)
    target_content_type = models.ForeignKey(
        ContentType, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        db_index=True
    )
    target_object_id = models.PositiveIntegerField(null=True, blank=True)
    target = GenericForeignKey('target_content_type', 'target_object_id')

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['recipient', 'unread']),
            models.Index(fields=['timestamp', 'unread']),
        ]

    def __str__(self):
        return f"{self.recipient} - {self.verb} - {self.timestamp}"

    def clean(self):
        if not self.verb or len(self.verb.strip()) < 2:
            raise ValidationError("O verbo da notificação deve ter pelo menos 2 caracteres.")
        if self.target_object_id and not self.target_content_type:
            raise ValidationError("Content type é obrigatório quando há target_object_id.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        # Invalida cache
        cache.delete(f'usuario_{self.recipient_id}_notificacoes')
        cache.delete(f'usuario_{self.recipient_id}_notificacoes_nao_lidas')

    @classmethod
    def get_notificacoes_usuario(cls, usuario_id: int) -> List['Notification']:
        """Retorna notificações de um usuário com cache"""
        cache_key = f'usuario_{usuario_id}_notificacoes'
        notificacoes = cache.get(cache_key)
        
        if notificacoes is None:
            notificacoes = list(cls.objects.filter(
                recipient_id=usuario_id
            ).select_related(
                'actor',
                'target_content_type'
            ).order_by('-timestamp'))
            
            cache.set(cache_key, notificacoes, CACHE_TIMEOUT)
            
        return notificacoes

    @classmethod
    def get_notificacoes_nao_lidas(cls, usuario_id: int) -> List['Notification']:
        """Retorna notificações não lidas de um usuário com cache"""
        cache_key = f'usuario_{usuario_id}_notificacoes_nao_lidas'
        notificacoes = cache.get(cache_key)
        
        if notificacoes is None:
            notificacoes = list(cls.objects.filter(
                recipient_id=usuario_id,
                unread=True
            ).select_related(
                'actor',
                'target_content_type'
            ).order_by('-timestamp'))
            
            cache.set(cache_key, notificacoes, CACHE_TIMEOUT)
            
        return notificacoes

class Wishlist(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        db_index=True
    )
    nome = models.CharField(
        max_length=100, 
        default="Minha Lista",
        db_index=True
    )
    publica = models.BooleanField(default=False, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        unique_together = ('usuario', 'nome')
        indexes = [
            models.Index(fields=['usuario', 'publica']),
            models.Index(fields=['criado_em']),
        ]

    def __str__(self):
        return f"{self.usuario.username} - {self.nome}"

    def clean(self):
        if not self.nome or len(self.nome.strip()) < 2:
            raise ValidationError("O nome da lista deve ter pelo menos 2 caracteres.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        # Invalida cache
        cache.delete(f'usuario_{self.usuario_id}_wishlists')
        cache.delete(f'wishlist_{self.pk}_itens')

    @classmethod
    def get_wishlists_usuario(cls, usuario_id: int) -> List['Wishlist']:
        """Retorna wishlists de um usuário com cache"""
        cache_key = f'usuario_{usuario_id}_wishlists'
        wishlists = cache.get(cache_key)
        
        if wishlists is None:
            wishlists = list(cls.objects.filter(
                usuario_id=usuario_id
            ).prefetch_related(
                'itens',
                'itens__produto',
                'itens__variacao'
            ).order_by('-criado_em'))
            
            cache.set(cache_key, wishlists, CACHE_TIMEOUT)
            
        return wishlists

class ItemWishlist(models.Model):
    wishlist = models.ForeignKey(
        Wishlist, 
        on_delete=models.CASCADE, 
        related_name='itens',
        db_index=True
    )
    produto = models.ForeignKey(
        Produto, 
        on_delete=models.CASCADE,
        db_index=True
    )
    variacao = models.ForeignKey(
        ProdutoVariacao, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        db_index=True
    )
    adicionado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        unique_together = ('wishlist', 'produto', 'variacao')
        indexes = [
            models.Index(fields=['wishlist', 'produto']),
            models.Index(fields=['produto', 'variacao']),
        ]

    def __str__(self):
        return f"{self.wishlist.nome} - {self.produto.nome}"

    def clean(self):
        if self.variacao and self.variacao.produto != self.produto:
            raise ValidationError("A variação deve pertencer ao produto selecionado.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        # Invalida cache
        cache.delete(f'wishlist_{self.wishlist_id}_itens')

class LogEstoque(models.Model):
    variacao = models.ForeignKey(
        ProdutoVariacao, 
        on_delete=models.CASCADE, 
        related_name='logs_estoque',
        db_index=True
    )
    quantidade = models.IntegerField()
    data = models.DateTimeField(auto_now_add=True, db_index=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        db_index=True
    )
    pedido = models.ForeignKey(
        'Pedido', 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        db_index=True
    )
    motivo = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-data']
        indexes = [
            models.Index(fields=['variacao', 'data']),
            models.Index(fields=['pedido', 'data']),
            models.Index(fields=['usuario', 'data']),
        ]

    def __str__(self):
        return f"{self.variacao} | {self.quantidade} | {self.data:%d/%m/%Y %H:%M}"

    def clean(self):
        if self.quantidade == 0:
            raise ValidationError("A quantidade não pode ser zero.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        # Invalida cache
        cache.delete(f'variacao_{self.variacao_id}_logs_estoque')
        if self.pedido:
            cache.delete(f'pedido_{self.pedido_id}_logs_estoque')

    @classmethod
    def get_logs_variacao(cls, variacao_id: int) -> List['LogEstoque']:
        """Retorna logs de estoque de uma variação com cache"""
        cache_key = f'variacao_{variacao_id}_logs_estoque'
        logs = cache.get(cache_key)
        
        if logs is None:
            logs = list(cls.objects.filter(
                variacao_id=variacao_id
            ).select_related(
                'usuario',
                'pedido'
            ).order_by('-data'))
            
            cache.set(cache_key, logs, CACHE_TIMEOUT)
            
        return logs

    @classmethod
    def get_logs_pedido(cls, pedido_id: int) -> List['LogEstoque']:
        """Retorna logs de estoque de um pedido com cache"""
        cache_key = f'pedido_{pedido_id}_logs_estoque'
        logs = cache.get(cache_key)
        
        if logs is None:
            logs = list(cls.objects.filter(
                pedido_id=pedido_id
            ).select_related(
                'variacao',
                'usuario'
            ).order_by('-data'))
            
            cache.set(cache_key, logs, CACHE_TIMEOUT)
            
        return logs

class ReservaEstoque(models.Model):
    """Modelo para gerenciar reservas de estoque e prevenir overselling"""
    variacao = models.ForeignKey(
        ProdutoVariacao,
        on_delete=models.CASCADE,
        related_name='reservas',
        db_index=True
    )
    quantidade = models.PositiveIntegerField()
    sessao_id = models.CharField(max_length=100, db_index=True)
    pedido = models.ForeignKey(
        'Pedido',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reservas_estoque',
        db_index=True
    )
    data_criacao = models.DateTimeField(auto_now_add=True, db_index=True)
    data_expiracao = models.DateTimeField(db_index=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('P', 'Pendente'),
            ('C', 'Confirmada'),
            ('E', 'Expirada'),
            ('L', 'Liberada')
        ],
        default='P',
        db_index=True
    )
    lock_version = models.PositiveIntegerField(default=0)  # Para controle de concorrência

    class Meta:
        indexes = [
            models.Index(fields=['variacao', 'status']),
            models.Index(fields=['sessao_id', 'status']),
            models.Index(fields=['data_expiracao', 'status']),
            models.Index(fields=['variacao', 'sessao_id', 'status']),  # Para evitar double booking
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantidade__gt=0),
                name='quantidade_positiva'
            )
        ]

    def clean(self):
        if self.quantidade <= 0:
            raise ValidationError("A quantidade deve ser maior que zero.")
        if self.quantidade > self.variacao.estoque:
            raise ValidationError("Quantidade indisponível em estoque.")
        if self.data_expiracao <= timezone.now():
            raise ValidationError("A data de expiração deve ser futura.")

    def save(self, *args, **kwargs):
        self.full_clean()
        self.lock_version += 1  # Incrementa versão do lock
        super().save(*args, **kwargs)
        # Invalida cache
        cache.delete(f'variacao_{self.variacao_id}_estoque_disponivel')
        cache.delete(f'variacao_{self.variacao_id}_reservas_ativas')

    @classmethod
    def reservar_estoque(cls, variacao_id: int, quantidade: int, sessao_id: str, tempo_reserva: int = 30) -> 'ReservaEstoque':
        """Reserva estoque para um item por um período determinado com controle de concorrência"""
        with transaction.atomic():
            # Lock na variação para evitar race conditions
            variacao = ProdutoVariacao.objects.select_for_update().get(id=variacao_id)
            
            # Verifica reservas existentes da mesma sessão
            reserva_existente = cls.objects.filter(
                variacao_id=variacao_id,
                sessao_id=sessao_id,
                status='P',
                data_expiracao__gt=timezone.now()
            ).first()
            
            if reserva_existente:
                # Atualiza reserva existente
                reserva_existente.quantidade = quantidade
                reserva_existente.data_expiracao = timezone.now() + timezone.timedelta(minutes=tempo_reserva)
                reserva_existente.save()
                return reserva_existente
            
            # Verifica estoque disponível considerando todas as reservas ativas
            estoque_disponivel = variacao.estoque - cls.get_quantidade_reservada(variacao_id)
            if estoque_disponivel < quantidade:
                raise ValidationError("Estoque insuficiente para reserva.")
            
            # Cria nova reserva
            data_expiracao = timezone.now() + timezone.timedelta(minutes=tempo_reserva)
            reserva = cls.objects.create(
                variacao=variacao,
                quantidade=quantidade,
                sessao_id=sessao_id,
                data_expiracao=data_expiracao
            )
            
            return reserva

    @classmethod
    def confirmar_reserva(cls, reserva_id: int, pedido_id: int) -> bool:
        """Confirma uma reserva de estoque para um pedido"""
        with transaction.atomic():
            try:
                reserva = cls.objects.select_for_update().get(
                    id=reserva_id,
                    status='P',
                    data_expiracao__gt=timezone.now()
                )
                reserva.status = 'C'
                reserva.pedido_id = pedido_id
                reserva.save()
                return True
            except cls.DoesNotExist:
                return False

    @classmethod
    def get_quantidade_reservada(cls, variacao_id: int) -> int:
        """Retorna quantidade total reservada de uma variação"""
        cache_key = f'variacao_{variacao_id}_quantidade_reservada'
        quantidade = cache.get(cache_key)
        
        if quantidade is None:
            quantidade = cls.objects.filter(
                variacao_id=variacao_id,
                status='P',
                data_expiracao__gt=timezone.now()
            ).aggregate(
                total=models.Sum('quantidade')
            )['total'] or 0
            
            cache.set(cache_key, quantidade, 60)  # Cache por 1 minuto
            
        return quantidade

    @classmethod
    def liberar_reservas_expiradas(cls):
        """Libera reservas expiradas"""
        with transaction.atomic():
            reservas = cls.objects.filter(
                status='P',
                data_expiracao__lte=timezone.now()
            ).select_for_update()
            
            for reserva in reservas:
                reserva.status = 'E'
                reserva.save()
                
            # Invalida cache
            cache.delete_pattern('variacao_*_quantidade_reservada')


class AuditoriaPreco(models.Model):
    """Modelo para auditoria de mudanças de preços"""
    produto = models.ForeignKey(
        Produto,
        on_delete=models.CASCADE,
        related_name='auditoria_precos',
        db_index=True
    )
    preco_antigo = models.DecimalField(max_digits=10, decimal_places=2)
    preco_novo = models.DecimalField(max_digits=10, decimal_places=2)
    variacao_percentual = models.DecimalField(max_digits=5, decimal_places=2)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alteracoes_preco',
        db_index=True
    )
    data_alteracao = models.DateTimeField(auto_now_add=True, db_index=True)
    motivo = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-data_alteracao']
        indexes = [
            models.Index(fields=['produto', 'data_alteracao']),
            models.Index(fields=['variacao_percentual']),
        ]

    def __str__(self):
        return f"Alteração de preço: {self.produto.nome} - {self.data_alteracao}"

    def clean(self):
        if self.preco_antigo == self.preco_novo:
            raise ValidationError("O preço novo deve ser diferente do preço antigo.")
        if self.preco_novo <= 0:
            raise ValidationError("O preço novo deve ser maior que zero.")

    def save(self, *args, **kwargs):
        if not self.variacao_percentual:
            self.variacao_percentual = ((self.preco_novo - self.preco_antigo) / self.preco_antigo) * 100
        super().save(*args, **kwargs)


class VerificacaoPedido(models.Model):
    """Modelo para verificação de integridade de pedidos"""
    pedido = models.OneToOneField(
        Pedido,
        on_delete=models.CASCADE,
        related_name='verificacao',
        db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('P', 'Pendente'),
            ('V', 'Verificado'),
            ('E', 'Erro')
        ],
        default='P',
        db_index=True
    )
    data_verificacao = models.DateTimeField(auto_now_add=True, db_index=True)
    erros = models.JSONField(default=dict, blank=True)
    checksum = models.CharField(max_length=64, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'data_verificacao']),
        ]

    def __str__(self):
        return f"Verificação do Pedido {self.pedido.codigo}"

    def gerar_checksum(self):
        """Gera checksum para verificação de integridade"""
        dados = {
            'pedido_id': self.pedido.id,
            'total': str(self.pedido.total),
            'itens': [
                {
                    'produto_id': item.produto_id,
                    'variacao_id': item.variacao_id,
                    'quantidade': item.quantidade,
                    'preco': str(item.preco_unitario)
                }
                for item in self.pedido.itens.all()
            ]
        }
        return hashlib.sha256(json.dumps(dados, sort_keys=True).encode()).hexdigest()

    def verificar_integridade(self):
        """Verifica a integridade do pedido"""
        erros = []
        
        # Verifica checksum
        checksum_atual = self.gerar_checksum()
        if checksum_atual != self.checksum:
            erros.append("Checksum inválido - possível manipulação de dados")
        
        # Verifica total
        total_calculado = sum(
            item.preco_unitario * item.quantidade 
            for item in self.pedido.itens.all()
        )
        if total_calculado != self.pedido.total:
            erros.append("Total do pedido inconsistente")
        
        # Verifica estoque
        for item in self.pedido.itens.all():
            if item.variacao:
                if item.variacao.estoque < item.quantidade:
                    erros.append(f"Estoque insuficiente para {item.produto.nome}")
        
        self.erros = erros
        self.status = 'E' if erros else 'V'
        self.save()
        
        return not erros

    def save(self, *args, **kwargs):
        if not self.checksum:
            self.checksum = self.gerar_checksum()
        super().save(*args, **kwargs)


class ProtecaoCarrinho(models.Model):
    """Modelo para proteção contra manipulação de carrinho"""
    sessao_id = models.CharField(max_length=100, unique=True, db_index=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='protecoes_carrinho',
        db_index=True
    )
    data_criacao = models.DateTimeField(auto_now_add=True, db_index=True)
    ultima_atualizacao = models.DateTimeField(auto_now=True)
    tentativas_manipulacao = models.PositiveIntegerField(default=0)
    bloqueado_ate = models.DateTimeField(null=True, blank=True)
    checksum = models.CharField(max_length=64, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['sessao_id', 'bloqueado_ate']),
            models.Index(fields=['usuario', 'bloqueado_ate']),
        ]

    def __str__(self):
        return f"Proteção Carrinho - {self.sessao_id}"

    def gerar_checksum(self, itens_carrinho):
        """Gera checksum para os itens do carrinho"""
        dados = sorted([
            {
                'produto_id': item.produto_id,
                'variacao_id': item.variacao_id,
                'quantidade': item.quantidade,
                'preco': str(item.preco_unitario())
            }
            for item in itens_carrinho
        ], key=lambda x: (x['produto_id'], x['variacao_id'] or 0))
        
        return hashlib.sha256(json.dumps(dados, sort_keys=True).encode()).hexdigest()

    def verificar_manipulacao(self, itens_carrinho):
        """Verifica se houve manipulação no carrinho"""
        if self.bloqueado_ate and self.bloqueado_ate > timezone.now():
            raise ValidationError("Carrinho bloqueado por suspeita de manipulação")
        
        checksum_atual = self.gerar_checksum(itens_carrinho)
        if checksum_atual != self.checksum:
            self.tentativas_manipulacao += 1
            if self.tentativas_manipulacao >= 3:
                self.bloqueado_ate = timezone.now() + timezone.timedelta(hours=1)
            self.save()
            return False
        return True

    def registrar_tentativa_manipulacao(self):
        """Registra tentativa de manipulação"""
        self.tentativas_manipulacao += 1
        if self.tentativas_manipulacao >= 3:
            self.bloqueado_ate = timezone.now() + timezone.timedelta(hours=1)
        self.save()

    def resetar_protecao(self):
        """Reseta a proteção do carrinho"""
        self.tentativas_manipulacao = 0
        self.bloqueado_ate = None
        self.save()

    @classmethod
    def get_protecao(cls, sessao_id: str, usuario_id: int = None) -> 'ProtecaoCarrinho':
        """Obtém ou cria proteção para uma sessão"""
        protecao = cls.objects.filter(sessao_id=sessao_id).first()
        if not protecao:
            protecao = cls.objects.create(
                sessao_id=sessao_id,
                usuario_id=usuario_id
            )
        return protecao

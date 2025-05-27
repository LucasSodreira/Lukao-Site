from django.contrib import admin
from .models import (
    Categoria, Produto, Endereco, Pedido, ItemPedido, Marca, ProdutoVariacao,
    ImagemProduto, AvaliacaoProduto, Cupom, HistoricoPreco, Tag, Favorito,
    LogStatusPedido, LogAcao, Carrinho, ItemCarrinho, Perfil, Reembolso,
    HistoricoPedido, Notification, AtributoTipo, AtributoValor
)

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'categoria_pai')
    search_fields = ('nome',)
    prepopulated_fields = {"slug": ("nome",)}

# CorAdmin removido - agora usando AtributoTipo/AtributoValor

@admin.register(AtributoTipo)
class AtributoTipoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'tipo', 'obrigatorio', 'ordem', 'ativo')
    list_filter = ('tipo', 'obrigatorio', 'ativo')
    search_fields = ('nome',)
    list_editable = ('ordem', 'ativo')

@admin.register(AtributoValor)
class AtributoValorAdmin(admin.ModelAdmin):
    list_display = ('id', 'tipo', 'valor', 'codigo', 'ordem', 'valor_adicional_preco', 'ativo')
    list_filter = ('tipo', 'ativo')
    search_fields = ('valor', 'codigo')
    list_editable = ('ordem', 'valor_adicional_preco', 'ativo')

@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome')
    search_fields = ('nome',)
    prepopulated_fields = {"slug": ("nome",)}

@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'preco', 'categoria', 'ativo', 'destaque')
    list_filter = ('categoria', 'ativo', 'destaque', 'marca')
    search_fields = ('nome', 'descricao')
    list_editable = ('preco', 'ativo', 'destaque')
    prepopulated_fields = {"slug": ("nome",)}

@admin.register(ProdutoVariacao)
class ProdutoVariacaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'produto', 'estoque', 'preco_adicional', 'sku')
    list_filter = ('produto',)
    search_fields = ('produto__nome', 'sku')
    filter_horizontal = ('atributos',)

@admin.register(ImagemProduto)
class ImagemProdutoAdmin(admin.ModelAdmin):
    list_display = ('id', 'produto', 'destaque', 'ordem')

@admin.register(AvaliacaoProduto)
class AvaliacaoProdutoAdmin(admin.ModelAdmin):
    list_display = ('id', 'produto', 'usuario', 'nota', 'aprovada', 'criado_em')
    list_filter = ('aprovada', 'nota')

@admin.register(Endereco)
class EnderecoAdmin(admin.ModelAdmin):
    list_display = ('id', 'rua', 'numero', 'cidade', 'estado', 'cep', 'usuario', 'principal')
    search_fields = ('rua', 'cidade', 'estado', 'cep', 'usuario__username')

@admin.register(Cupom)
class CupomAdmin(admin.ModelAdmin):
    list_display = ('id', 'codigo', 'tipo', 'desconto_percentual', 'desconto_valor', 'ativo', 'validade_fim', 'usos', 'max_usos')
    list_filter = ('tipo', 'ativo', 'primeira_compra_apenas', 'uso_unico')
    search_fields = ('codigo', 'descricao')
    list_editable = ('ativo',)
    filter_horizontal = ('categorias_aplicaveis', 'produtos_aplicaveis')
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('codigo', 'descricao', 'tipo', 'ativo')
        }),
        ('Desconto', {
            'fields': ('desconto_percentual', 'desconto_valor', 'valor_maximo_desconto')
        }),
        ('Validade', {
            'fields': ('validade_inicio', 'validade_fim')
        }),
        ('Limites de Uso', {
            'fields': ('uso_unico', 'max_usos', 'usos', 'usuario')
        }),
        ('Regras de Aplicação', {
            'fields': ('valor_minimo_pedido', 'primeira_compra_apenas', 'categorias_aplicaveis', 'produtos_aplicaveis')
        }),
        ('Compre X Leve Y', {
            'fields': ('quantidade_comprar', 'quantidade_levar'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'codigo', 'usuario', 'data_criacao', 'status', 'total')
    list_filter = ('status', 'data_criacao')
    date_hierarchy = 'data_criacao'
    search_fields = ('codigo', 'usuario__username')

@admin.register(ItemPedido)
class ItemPedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'pedido', 'produto', 'quantidade', 'preco_unitario', 'variacao')

@admin.register(HistoricoPreco)
class HistoricoPrecoAdmin(admin.ModelAdmin):
    list_display = ('id', 'produto', 'preco', 'data')

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome')
    search_fields = ('nome',)

@admin.register(Favorito)
class FavoritoAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'produto', 'criado_em')

@admin.register(LogStatusPedido)
class LogStatusPedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'pedido', 'status_antigo', 'status_novo', 'data', 'usuario')

@admin.register(LogAcao)
class LogAcaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'acao', 'data')

@admin.register(Carrinho)
class CarrinhoAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'criado_em', 'atualizado_em')

@admin.register(ItemCarrinho)
class ItemCarrinhoAdmin(admin.ModelAdmin):
    list_display = ('id', 'carrinho', 'produto', 'quantidade', 'variacao')

@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ('id', 'endereco_rapido', 'metodo_pagamento_rapido')

@admin.register(Reembolso)
class ReembolsoAdmin(admin.ModelAdmin):
    list_display = ('id', 'pedido', 'valor', 'data_criacao', 'status')

@admin.register(HistoricoPedido)
class HistoricoPedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'pedido', 'status_antigo', 'status_novo', 'data', 'usuario')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'recipient', 'actor', 'verb', 'timestamp', 'unread')
    list_filter = ('unread', 'timestamp')

from django.contrib import admin
from .models import (
    Categoria, Produto, Endereco, Pedido, ItemPedido, Cor, Marca, ProdutoVariacao,
    ImagemProduto, AvaliacaoProduto, Cupom, HistoricoPreco, Tag, Favorito,
    LogStatusPedido, LogAcao, Carrinho, ItemCarrinho, Perfil, Reembolso,
    HistoricoPedido, Notification
)

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'categoria_pai')
    search_fields = ('nome',)
    prepopulated_fields = {"slug": ("nome",)}

@admin.register(Cor)
class CorAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'valor_css', 'ordem')
    search_fields = ('nome',)

@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome')
    search_fields = ('nome',)
    prepopulated_fields = {"slug": ("nome",)}

@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'preco', 'categoria', 'estoque', 'ativo', 'destaque')
    list_filter = ('categoria', 'ativo', 'destaque', 'marca')
    search_fields = ('nome', 'descricao')
    list_editable = ('preco', 'estoque', 'ativo', 'destaque')
    prepopulated_fields = {"slug": ("nome",)}

@admin.register(ProdutoVariacao)
class ProdutoVariacaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'produto', 'cor', 'tamanho', 'estoque')
    list_filter = ('produto', 'cor', 'tamanho')

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
    list_display = ('id', 'codigo', 'descricao', 'desconto_percentual', 'desconto_valor', 'ativo', 'validade', 'usos', 'max_usos')
    search_fields = ('codigo',)

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

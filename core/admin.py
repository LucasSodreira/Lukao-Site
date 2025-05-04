from django.contrib import admin
from .models import Categoria, Produto, Endereco, Pedido, ItemPedido

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome')
    search_fields = ('nome',)


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'preco', 'categoria', 'estoque')
    list_filter = ('categoria',)
    search_fields = ('nome', 'descricao')
    list_editable = ('preco', 'estoque')


@admin.register(Endereco)
class EnderecoAdmin(admin.ModelAdmin):
    list_display = ('id', 'rua', 'numero', 'cidade', 'estado', 'cep')
    search_fields = ('rua', 'cidade', 'estado', 'cep')


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'data_criacao', 'status', 'total')
    list_filter = ('status',)
    date_hierarchy = 'data_criacao'


@admin.register(ItemPedido)
class ItemPedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'pedido', 'produto', 'quantidade', 'preco_unitario')

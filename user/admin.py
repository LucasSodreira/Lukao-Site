from django.contrib import admin
from user.models import Perfil

@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'cpf', 'telefone', 'data_nascimento', 'sexo', 'newsletter', 'data_cadastro')
    search_fields = ('usuario__username', 'usuario__email', 'cpf', 'telefone')
    list_filter = ('sexo', 'newsletter', 'data_cadastro')
    autocomplete_fields = ['usuario', 'endereco_padrao']
    readonly_fields = ('data_cadastro', 'data_atualizacao')
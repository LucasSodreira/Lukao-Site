from django.contrib import admin
from user.models import Perfil, LogAtividadeUsuario

@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'cpf', 'telefone', 'data_nascimento', 'sexo', 'newsletter', 'data_cadastro')
    search_fields = ('usuario__username', 'usuario__email', 'cpf', 'telefone')
    list_filter = ('sexo', 'newsletter', 'data_cadastro')
    autocomplete_fields = ['usuario', 'endereco_padrao']
    readonly_fields = ('data_cadastro', 'data_atualizacao')

@admin.register(LogAtividadeUsuario)
class LogAtividadeUsuarioAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo', 'ip', 'data')
    search_fields = ('usuario__username', 'ip', 'user_agent')
    list_filter = ('tipo', 'data')
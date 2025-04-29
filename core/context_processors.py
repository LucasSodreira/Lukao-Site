from .models import Endereco

def endereco_do_usuario(request):
    """
    Retorna nome do usuário e CEP para exibição em base.html.
    Disponível em todos os templates automaticamente.
    """
    nome_usuario = None
    cep_usuario = None

    if request.user.is_authenticated:
        nome_usuario = request.user.first_name or request.user.username
        endereco = Endereco.objects.filter(usuario=request.user).first()
        if endereco:
            cep_usuario = endereco.cep

    return {
        'nome_usuario': nome_usuario,
        'cep_usuario': cep_usuario,
    }

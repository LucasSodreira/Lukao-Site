from django import template

register = template.Library()

@register.filter
def get_cor(atributos):
    """Retorna o objeto de cor da lista de atributos."""
    for attr in atributos:
        if hasattr(attr, 'tipo') and getattr(attr.tipo, 'nome', '').lower() == 'cor':
            return attr
    return None

@register.filter
def get_tamanho(atributos):
    """Retorna o objeto de tamanho da lista de atributos."""
    for attr in atributos:
        if hasattr(attr, 'tipo') and getattr(attr.tipo, 'nome', '').lower() == 'tamanho':
            return attr
    return None

@register.simple_tag
def get_variacao_id_for_cor_tamanho(disponibilidade, cor_id, tamanho_id):
    """Retorna o id da variação para cor_id e tamanho_id, ou string vazia."""
    try:
        if isinstance(disponibilidade, dict):
            cor_dict = disponibilidade.get(str(cor_id), {})
            if isinstance(cor_dict, dict):
                return cor_dict.get(str(tamanho_id), '')
        return ''
    except Exception:
        return ''

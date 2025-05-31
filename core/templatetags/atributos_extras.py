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

@register.filter
def get_atributos_principais(atributos):
    """Retorna apenas os atributos principais (Cor, Tamanho e Material)."""
    principais = []
    for attr in atributos:
        if hasattr(attr, 'tipo'):
            tipo_nome = getattr(attr.tipo, 'nome', '').lower()
            if tipo_nome in ['cor', 'tamanho']:
                principais.append(attr)
    return principais

@register.filter
def get_atributos_relevantes(atributos):
    """
    Retorna atributos relevantes, excluindo combinações que não fazem sentido.
    Por exemplo, 'Calça Jeans' não deveria ter 'Material: Lã'.
    """
    relevantes = []
    material_irrelevante = False
    estilo_irrelevante = False
    
    # Verificar se há combinações que não fazem sentido
    for attr in atributos:
        if hasattr(attr, 'tipo'):
            tipo_nome = getattr(attr.tipo, 'nome', '').lower()
            valor = getattr(attr, 'valor', '').lower()
            
            # Sempre incluir cor e tamanho
            if tipo_nome in ['cor', 'tamanho']:
                relevantes.append(attr)
            # Para material, verificar se faz sentido
            elif tipo_nome == 'material':
                # Aqui você pode adicionar lógica específica se necessário
                # Por enquanto, vamos incluir todos os materiais
                relevantes.append(attr)
            # Para estilo, verificar se faz sentido
            elif tipo_nome == 'estilo':
                # Incluir apenas se for um estilo que faça sentido
                relevantes.append(attr)
    
    return relevantes

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

#!/usr/bin/env python
"""
Teste simples para verificar se os botões de variação estão funcionando corretamente
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Projeto_Lukao.settings')
django.setup()

from core.models import Produto, ProdutoVariacao, AtributoValor

def test_variacoes_produto():
    """Testa se um produto tem variações válidas"""
    try:
        produto = Produto.objects.get(id=1)
        print(f"✓ Produto encontrado: {produto.nome}")
        
        variacoes = produto.variacoes.filter(estoque__gt=0).prefetch_related('atributos__tipo')
        print(f"✓ Variações com estoque: {variacoes.count()}")
        
        if variacoes.count() == 0:
            print("❌ ERRO: Produto não tem variações com estoque!")
            return False
            
        # Testa estrutura de dados como na view
        variacoes_por_cor = {}
        cores_disponiveis = []
        
        for variacao in variacoes:
            cor_obj = None
            tamanho_obj = None
            
            for attr in variacao.atributos.all():
                if attr.tipo.nome.lower() == 'cor':
                    cor_obj = attr
                elif attr.tipo.nome.lower() == 'tamanho':
                    tamanho_obj = attr
            
            if cor_obj and tamanho_obj:
                if cor_obj.id not in variacoes_por_cor:
                    variacoes_por_cor[cor_obj.id] = {
                        'cor': {
                            'id': cor_obj.id,
                            'valor': cor_obj.valor,
                            'codigo': cor_obj.codigo
                        },
                        'tamanhos': {}
                    }
                    cores_disponiveis.append(cor_obj.valor)
                
                variacoes_por_cor[cor_obj.id]['tamanhos'][tamanho_obj.id] = {
                    'id': tamanho_obj.id,
                    'valor': tamanho_obj.valor,
                    'variacao_id': variacao.id,
                    'estoque': variacao.estoque
                }
        
        print(f"✓ Cores disponíveis: {cores_disponiveis}")
        
        for cor_id, dados in variacoes_por_cor.items():
            cor_nome = dados['cor']['valor']
            tamanhos = [t['valor'] for t in dados['tamanhos'].values()]
            print(f"  - {cor_nome}: {tamanhos}")
        
        print("✓ SUCESSO: Estrutura de dados gerada corretamente!")
        return True
        
    except Produto.DoesNotExist:
        print("❌ ERRO: Produto ID 1 não encontrado!")
        return False
    except Exception as e:
        print(f"❌ ERRO: {e}")
        return False

if __name__ == "__main__":
    print("=== TESTE DE VARIAÇÕES DE PRODUTO ===")
    success = test_variacoes_produto()
    if success:
        print("\n🎉 TODOS OS TESTES PASSARAM!")
    else:
        print("\n💥 FALHA NOS TESTES!")

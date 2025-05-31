from django_seed import Seed
from django.contrib.auth import get_user_model
from .models import (
    Categoria, Produto, Endereco, Pedido, ItemPedido, Marca, ProdutoVariacao,
    ImagemProduto, AvaliacaoProduto, Cupom, Tag, Carrinho, ItemCarrinho,
    AtributoTipo, AtributoValor, HistoricoPreco, LogStatusPedido, LogAcao,
    Reembolso, Notification, Wishlist, ItemWishlist, LogEstoque, ReservaEstoque,
    AuditoriaPreco, VerificacaoPedido, ProtecaoCarrinho
)
import random
from decimal import Decimal
import os
from django.conf import settings
from django.utils import timezone
from django.core.files.base import ContentFile
from django.db import connection

def reset_pedido_sequence():
    with connection.cursor() as cursor:
        if connection.vendor == 'postgresql':
            cursor.execute("ALTER SEQUENCE core_pedido_id_seq RESTART WITH 1;")
            cursor.execute("SELECT setval('core_pedido_id_seq', (SELECT MAX(id) FROM core_pedido));")
        elif connection.vendor == 'sqlite':
            cursor.execute("UPDATE sqlite_sequence SET seq = (SELECT MAX(id) FROM core_pedido) WHERE name='core_pedido';")

def seed_data(qtd_categorias=5, qtd_produtos=50, qtd_usuarios=10, qtd_enderecos=15, qtd_pedidos=25):
    
    reset_pedido_sequence()

    seeder = Seed.seeder()
    User = get_user_model()

    print("Iniciando seed dos dados...")

    # 1. Categorias com hierarquia
    categorias = []
    categorias_principais = []
    for i in range(qtd_categorias):
        categoria = Categoria.objects.create(
            nome=f"Categoria {i+1}",
            descricao=seeder.faker.text(max_nb_chars=100)
        )
        categorias.append(categoria)
        categorias_principais.append(categoria)
    
    # Criar subcategorias
    for categoria_pai in categorias_principais:
        for j in range(random.randint(1, 3)):
            subcategoria = Categoria.objects.create(
                nome=f"{categoria_pai.nome} - Sub {j+1}",
                descricao=seeder.faker.text(max_nb_chars=100),
                categoria_pai=categoria_pai
            )
            categorias.append(subcategoria)
    
    print(f"Criadas {len(categorias)} categorias (incluindo subcategorias)")

    # 2. Marcas
    marcas = []
    nomes_marcas = ['Nike', 'Adidas', 'Puma', 'Reebok', 'Under Armour', 'Lacoste', 'Tommy Hilfiger', 'Calvin Klein', 'Hugo Boss', 'Zara']
    for i, nome in enumerate(nomes_marcas):
        marca = Marca.objects.create(
            nome=nome,
            descricao=seeder.faker.text(max_nb_chars=100)
        )
        marcas.append(marca)
    print(f"Criadas {len(marcas)} marcas")

    # 3. Tags
    tags = []
    nomes_tags = ['Novo', 'Promoção', 'Bestseller', 'Limitado', 'Verão', 'Inverno', 'Casual', 'Esportivo', 'Elegante', 'Confortável', 'Premium', 'Sustentável']
    cores_tags = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#ffeaa7', '#dda0dd', '#98d8c8', '#f7dc6f', '#bb8fce', '#85c1e9', '#f8c471', '#82e0aa']
    
    for i, nome in enumerate(nomes_tags):
        tag = Tag.objects.create(
            nome=nome,
            cor=cores_tags[i % len(cores_tags)]
        )
        tags.append(tag)
    print(f"Criadas {len(tags)} tags")

    # 4. AtributoTipo e AtributoValor
    # Criar tipos de atributos
    tipo_cor = AtributoTipo.objects.create(
        nome="Cor",
        tipo="color",
        obrigatorio=True,
        ordem=1
    )
    
    tipo_tamanho = AtributoTipo.objects.create(
        nome="Tamanho",
        tipo="size",
        obrigatorio=True,
        ordem=2
    )
    
    tipo_material = AtributoTipo.objects.create(
        nome="Material",
        tipo="select",
        obrigatorio=False,
        ordem=3
    )
    
    tipo_estilo = AtributoTipo.objects.create(
        nome="Estilo",
        tipo="select",
        obrigatorio=False,
        ordem=4
    )

    # Criar valores para cores
    cores_data = [
        {'valor': 'Vermelho', 'codigo': '#FF0000'},
        {'valor': 'Azul', 'codigo': '#0000FF'},
        {'valor': 'Verde', 'codigo': '#008000'},
        {'valor': 'Preto', 'codigo': '#000000'},
        {'valor': 'Branco', 'codigo': '#FFFFFF'},
        {'valor': 'Amarelo', 'codigo': '#FFFF00'},
        {'valor': 'Rosa', 'codigo': '#FFC0CB'},
        {'valor': 'Roxo', 'codigo': '#800080'},
        {'valor': 'Laranja', 'codigo': '#FFA500'},
        {'valor': 'Cinza', 'codigo': '#808080'}
    ]
    
    cores_valores = []
    for i, cor_data in enumerate(cores_data):
        cor_valor = AtributoValor.objects.create(
            tipo=tipo_cor,
            valor=cor_data['valor'],
            codigo=cor_data['codigo'],
            ordem=i,
            valor_adicional_preco=Decimal('0.00')
        )
        cores_valores.append(cor_valor)

    # Criar valores para tamanhos
    tamanhos_data = [
        {'valor': 'PP', 'codigo': 'PP'},
        {'valor': 'P', 'codigo': 'P'},
        {'valor': 'M', 'codigo': 'M'},
        {'valor': 'G', 'codigo': 'G'},
        {'valor': 'GG', 'codigo': 'GG'},
        {'valor': 'XG', 'codigo': 'XG'},
        {'valor': 'XXG', 'codigo': 'XXG'}
    ]
    
    tamanhos_valores = []
    for i, tamanho_data in enumerate(tamanhos_data):
        tamanho_valor = AtributoValor.objects.create(
            tipo=tipo_tamanho,
            valor=tamanho_data['valor'],
            codigo=tamanho_data['codigo'],
            ordem=i,
            valor_adicional_preco=Decimal('5.00') if tamanho_data['codigo'] in ['XG', 'XXG'] else Decimal('0.00')
        )
        tamanhos_valores.append(tamanho_valor)

    # Criar valores para materiais
    materiais_data = ['Algodão', 'Poliéster', 'Linho', 'Seda', 'Lã', 'Viscose', 'Elastano']
    materiais_valores = []
    for i, material in enumerate(materiais_data):
        material_valor = AtributoValor.objects.create(
            tipo=tipo_material,
            valor=material,
            codigo=material[:3].upper(),
            ordem=i,
            valor_adicional_preco=Decimal(random.uniform(0, 20)).quantize(Decimal('0.01'))
        )
        materiais_valores.append(material_valor)

    # Criar valores para estilos
    estilos_data = ['Casual', 'Formal', 'Esportivo', 'Vintage', 'Moderno', 'Clássico']
    estilos_valores = []
    for i, estilo in enumerate(estilos_data):
        estilo_valor = AtributoValor.objects.create(
            tipo=tipo_estilo,
            valor=estilo,
            codigo=estilo[:3].upper(),
            ordem=i,
            valor_adicional_preco=Decimal('0.00')
        )
        estilos_valores.append(estilo_valor)

    print(f"Criados tipos de atributos: Cor ({len(cores_valores)} valores), Tamanho ({len(tamanhos_valores)} valores), Material ({len(materiais_valores)} valores), Estilo ({len(estilos_valores)} valores)")

    # 5. Usuários
    usuarios = []
    for i in range(qtd_usuarios):
        user = User.objects.create_user(
            username=f"user_{i}_{seeder.faker.unique.user_name()}",
            email=f"user_{i}@example.com",
            password='teste123',
            first_name=seeder.faker.first_name(),
            last_name=seeder.faker.last_name(),
            is_active=True
        )
        usuarios.append(user)
    print(f"Criados {len(usuarios)} usuários")

    # 6. Produtos
    produtos = []
    imagem_padrao_path = os.path.join(settings.BASE_DIR, 'media/produtos/camisa.png')
    imagem_url = 'produtos/camisa.png'
    imagem_ja_existe = os.path.exists(imagem_padrao_path)

    generos = ['M', 'F', 'U']
    temporadas = ['verao', 'inverno', 'meia_estacao', 'todo_ano']
    nomes_produtos = [
        'Camiseta', 'Calça Jeans', 'Vestido', 'Blusa', 'Short', 'Saia', 'Jaqueta',
        'Camisa Social', 'Moletom', 'Bermuda', 'Regata', 'Casaco', 'Blazer', 'Polo'
    ]

    for i in range(qtd_produtos):
        peso = Decimal(random.uniform(0.1, 2.0)).quantize(Decimal('0.001'))
        largura = random.randint(20, 50)
        altura = random.randint(30, 60)
        profundidade = random.randint(2, 15)
        preco = Decimal(random.uniform(29.90, 299.90)).quantize(Decimal('0.01'))
        preco_original = preco + Decimal(random.uniform(10, 100)).quantize(Decimal('0.01'))
        
        # Ocasionalmente criar produtos em promoção
        preco_promocional = None
        promocao_inicio = None
        promocao_fim = None
        if random.random() < 0.3:  # 30% dos produtos em promoção
            preco_promocional = (preco * Decimal('0.8')).quantize(Decimal('0.01'))  # 20% de desconto
            promocao_inicio = timezone.now() - timezone.timedelta(days=random.randint(1, 10))
            promocao_fim = timezone.now() + timezone.timedelta(days=random.randint(5, 30))

        produto = Produto.objects.create(
            nome=f"{random.choice(nomes_produtos)} {seeder.faker.word().capitalize()}",
            descricao=seeder.faker.text(max_nb_chars=300),
            preco=preco,
            preco_original=preco_original,
            categoria=random.choice(categorias),
            peso=peso,
            width=largura,
            height=altura,
            length=profundidade,
            marca=random.choice(marcas),
            genero=random.choice(generos),
            temporada=random.choice(temporadas),
            cuidados=seeder.faker.text(max_nb_chars=150),
            ativo=True,
            destaque=random.choice([True, False]),
            visivel=True,
            imagem=imagem_url if imagem_ja_existe else None,
            preco_promocional=preco_promocional,
            promocao_inicio=promocao_inicio,
            promocao_fim=promocao_fim,
            sku=f"PRD{i+1:04d}",
            codigo_barras=f"{random.randint(1000000000000, 9999999999999)}",
            seo_title=f"{random.choice(nomes_produtos)} {seeder.faker.word().capitalize()}"[:70],
            seo_description=seeder.faker.text(max_nb_chars=160)
        )
        
        # Adiciona tags aleatórias
        produto.tags.set(random.sample(tags, k=random.randint(1, 4)))
        produtos.append(produto)
    print(f"Criados {len(produtos)} produtos")

    # 7. ProdutoVariacao com sistema de atributos
    variacoes = []
    for produto in produtos:
        # Para cada produto, criar variações com diferentes combinações de atributos
        cores_escolhidas = random.sample(cores_valores, k=random.randint(2, 4))
        tamanhos_escolhidos = random.sample(tamanhos_valores, k=random.randint(3, 5))
        
        for cor in cores_escolhidas:
            for tamanho in tamanhos_escolhidos:
                # Criar variação com atributos obrigatórios
                variacao = ProdutoVariacao.objects.create(
                    produto=produto,
                    estoque=random.randint(5, 50),
                    preco_adicional=Decimal(random.uniform(-10, 30)).quantize(Decimal('0.01')),
                    peso=Decimal(random.uniform(0.1, 2.0)).quantize(Decimal('0.001')),
                    width=random.randint(20, 50),
                    height=random.randint(30, 60),
                    length=random.randint(2, 15)
                )
                
                # IMPORTANTE: Salvar primeiro, depois adicionar os relacionamentos many-to-many
                variacao.save()
                
                # Adicionar atributos obrigatórios APÓS salvar
                variacao.atributos.add(cor, tamanho)
                
                # Ocasionalmente adicionar atributos opcionais
                if random.random() < 0.6:  # 60% chance de ter material
                    material = random.choice(materiais_valores)
                    variacao.atributos.add(material)
                
                if random.random() < 0.4:  # 40% chance de ter estilo
                    estilo = random.choice(estilos_valores)
                    variacao.atributos.add(estilo)
                
                # Gerar SKU automático e recalcular hash após adicionar todos os atributos
                variacao.gerar_sku_automatico()
                variacao.atributos_hash = variacao.calcular_hash_atributos()
                variacao.save()
                
                variacoes.append(variacao)
    print(f"Criadas {len(variacoes)} variações de produto")

    # 8. ImagemProduto
    imagens = []
    for produto in produtos:
        for j in range(random.randint(2, 5)):
            img = ImagemProduto.objects.create(
                produto=produto,
                imagem=imagem_url if imagem_ja_existe else None,
                destaque=(j == 0),
                ordem=j
            )
            imagens.append(img)
    print(f"Criadas {len(imagens)} imagens de produtos")

    # 9. AvaliacaoProduto
    avaliacoes = []
    for produto in produtos:
        for _ in range(random.randint(0, 5)):
            if usuarios:
                avaliacao = AvaliacaoProduto.objects.create(
                    produto=produto,
                    usuario=random.choice(usuarios),
                    nota=random.randint(3, 5),  # Notas mais realistas
                    comentario=seeder.faker.sentence(),
                    aprovada=random.choice([True, True, True, False])  # 75% aprovadas
                )
                avaliacoes.append(avaliacao)
    print(f"Criadas {len(avaliacoes)} avaliações de produtos")

    # 10. Endereços
    enderecos = []
    ESTADOS_SIGLAS = [uf[0] for uf in Endereco.ESTADO_CHOICES]
    for _ in range(qtd_enderecos):
        telefone = f"({random.randint(11, 99)}) {random.randint(90000, 99999)}-{random.randint(1000, 9999)}"
        endereco = Endereco.objects.create(
            nome_completo=seeder.faker.name(),
            telefone=telefone,
            rua=seeder.faker.street_name(),
            numero=str(seeder.faker.building_number()),
            complemento=seeder.faker.secondary_address() if random.random() > 0.6 else None,
            bairro=seeder.faker.city_suffix(),
            cep=f"{random.randint(10000, 99999)}-{random.randint(100, 999)}",
            cidade=seeder.faker.city(),
            estado=random.choice(ESTADOS_SIGLAS),
            pais="Brasil",
            usuario=random.choice(usuarios) if usuarios and random.random() < 0.8 else None,
            principal=random.random() < 0.3,
        )
        enderecos.append(endereco)
    print(f"Criados {len(enderecos)} endereços")

    # 11. Cupons melhorados
    cupons = []
    tipos_cupom = ['percentual', 'valor_fixo', 'frete_gratis', 'compre_leve']
    
    for i in range(8):
        tipo = random.choice(tipos_cupom)
        cupom_data = {
            'codigo': f"CUPOM{i+1:02d}",
            'descricao': f"Cupom de {tipo.replace('_', ' ')} {i+1}",
            'tipo': tipo,
            'ativo': True,
            'validade_inicio': timezone.now() - timezone.timedelta(days=random.randint(1, 10)),
            'validade_fim': timezone.now() + timezone.timedelta(days=random.randint(10, 60)),
            'uso_unico': random.choice([True, False]),
            'max_usos': random.choice([None, 10, 50, 100]),
            'usuario': random.choice(usuarios) if random.random() < 0.3 else None,
            'valor_minimo_pedido': Decimal(random.uniform(50, 200)).quantize(Decimal('0.01')) if random.random() < 0.7 else None,
            'primeira_compra_apenas': random.choice([True, False]),
            'aplicar_apenas_itens_elegiveis': random.choice([True, False])
        }
        
        if tipo == 'percentual':
            cupom_data['desconto_percentual'] = Decimal(random.uniform(5, 30)).quantize(Decimal('0.01'))
            cupom_data['valor_maximo_desconto'] = Decimal(random.uniform(20, 100)).quantize(Decimal('0.01'))
        elif tipo == 'valor_fixo':
            cupom_data['desconto_valor'] = Decimal(random.uniform(10, 50)).quantize(Decimal('0.01'))
        elif tipo == 'compre_leve':
            cupom_data['quantidade_comprar'] = random.randint(2, 5)
            cupom_data['quantidade_levar'] = 1

        cupom = Cupom.objects.create(**cupom_data)
        
        # Adicionar categorias e produtos aplicáveis para alguns cupons
        if random.random() < 0.4:
            cupom.categorias_aplicaveis.set(random.sample(categorias, k=random.randint(1, 3)))
        if random.random() < 0.3:
            cupom.produtos_aplicaveis.set(random.sample(produtos, k=random.randint(1, 5)))
        
        cupons.append(cupom)
    print(f"Criados {len(cupons)} cupons")

    # 12. Pedidos e Itens
    status_choices = ['P', 'PA', 'E', 'T', 'C', 'X', 'D']
    pedidos_criados = 0
    for i in range(qtd_pedidos):
        try:
            status = random.choice(status_choices)
            pedido = Pedido.objects.create(
                usuario=random.choice(usuarios) if usuarios and random.random() < 0.9 else None,
                status=status,
                endereco_entrega=random.choice(enderecos) if enderecos else None,
                cupom=random.choice(cupons) if cupons and random.random() < 0.3 else None,
                frete_valor=Decimal(random.uniform(10, 30)).quantize(Decimal('0.01')),
                metodo_pagamento=random.choice(['pix', 'boleto', 'cartao_credito', 'cartao_debito']),
                codigo_rastreamento=f"BR{random.randint(100000000000, 999999999999)}" if status in ['E', 'T', 'C'] else None
            )
            
            # Adicionar itens ao pedido
            itens_produtos = random.sample(produtos, k=random.randint(1, min(4, len(produtos))))
            for produto in itens_produtos:
                variacao = ProdutoVariacao.objects.filter(produto=produto, estoque__gt=0).order_by('?').first()
                if variacao:
                    quantidade = random.randint(1, min(3, variacao.estoque))
                    ItemPedido.objects.create(
                        pedido=pedido,
                        produto=produto,
                        quantidade=quantidade,
                        preco_unitario=variacao.preco_final(),
                        variacao=variacao
                    )
            
            pedidos_criados += 1
        except Exception as e:
            print(f"Erro ao criar pedido {i+1}: {str(e)}")
            continue
    print(f"Criados {pedidos_criados}/{qtd_pedidos} pedidos com itens")

    # 13. Carrinho e Itens
    carrinhos = []
    itens_carrinho = []
    for usuario in usuarios:
        carrinho = Carrinho.objects.create(usuario=usuario)
        carrinhos.append(carrinho)
        
        # Adicionar alguns itens ao carrinho
        for produto in random.sample(produtos, k=random.randint(1, min(4, len(produtos)))):
            variacao = ProdutoVariacao.objects.filter(produto=produto, estoque__gt=0).order_by('?').first()
            if variacao:
                try:
                    item = ItemCarrinho.objects.create(
                        carrinho=carrinho,
                        produto=produto,
                        quantidade=random.randint(1, 3),
                        variacao=variacao
                    )
                    itens_carrinho.append(item)
                except:
                    pass  # Item já existe no carrinho
    print(f"Criados {len(carrinhos)} carrinhos e {len(itens_carrinho)} itens de carrinho")

    # 14. Wishlist
    wishlists = []
    itens_wishlist = []
    for usuario in usuarios:
        # Criar lista padrão
        wishlist_padrao = Wishlist.objects.create(
            usuario=usuario,
            nome="Minha Lista",
            publica=random.choice([True, False])
        )
        wishlists.append(wishlist_padrao)
        
        # Ocasionalmente criar lista adicional
        if random.random() < 0.4:
            wishlist_extra = Wishlist.objects.create(
                usuario=usuario,
                nome=random.choice(["Favoritos", "Para Comprar", "Desejos", "Lista Especial"]),
                publica=random.choice([True, False])
            )
            wishlists.append(wishlist_extra)
        
        # Adicionar itens às listas
        for wishlist in [w for w in wishlists if w.usuario == usuario]:
            for produto in random.sample(produtos, k=random.randint(1, min(6, len(produtos)))):
                variacao = ProdutoVariacao.objects.filter(produto=produto).order_by('?').first()
                try:
                    item = ItemWishlist.objects.create(
                        wishlist=wishlist,
                        produto=produto,
                        variacao=variacao if random.random() < 0.7 else None
                    )
                    itens_wishlist.append(item)
                except:
                    pass  # Item já existe na wishlist
    print(f"Criadas {len(wishlists)} wishlists e {len(itens_wishlist)} itens de wishlist")

    # 15. Notifications
    notifications = []
    verbos = [
        'pedido criado', 'pagamento aprovado', 'produto enviado', 'produto entregue',
        'avaliação aprovada', 'cupom disponível', 'produto favoritado', 'estoque baixo'
    ]
    
    for usuario in usuarios:
        for _ in range(random.randint(3, 8)):
            notification = Notification.objects.create(
                recipient=usuario,
                actor=random.choice(usuarios) if random.random() < 0.6 else None,
                verb=random.choice(verbos),
                description=seeder.faker.sentence(),
                unread=random.choice([True, False]),
                target_content_type=None,  # Simplificado para o seed
                target_object_id=None
            )
            notifications.append(notification)
    print(f"Criadas {len(notifications)} notifications")

    # 16. Reembolsos
    reembolsos = []
    pedidos_concluidos = Pedido.objects.filter(status__in=['C', 'X'])
    for pedido in random.sample(list(pedidos_concluidos), k=min(3, len(pedidos_concluidos))):
        try:
            reembolso = Reembolso.objects.create(
                pedido=pedido,
                valor=pedido.total * Decimal(random.uniform(0.5, 1.0)),
                status=random.choice(['P', 'A', 'C']),
                motivo=random.choice([
                    'Produto defeituoso',
                    'Não atendeu expectativas',
                    'Tamanho incorreto',
                    'Cancelamento do pedido',
                    'Produto danificado no transporte'
                ]),
                data_processamento=timezone.now() if random.random() < 0.7 else None
            )
            reembolsos.append(reembolso)
        except:
            pass  # Reembolso já existe para este pedido
    print(f"Criados {len(reembolsos)} reembolsos")

    # 17. Logs de Estoque
    logs_estoque = []
    for variacao in random.sample(variacoes, k=min(50, len(variacoes))):
        for _ in range(random.randint(1, 3)):
            log = LogEstoque.objects.create(
                variacao=variacao,
                quantidade=random.randint(-10, 20),
                usuario=random.choice(usuarios) if random.random() < 0.8 else None,
                pedido=None,  # Simplificado para o seed
                motivo=random.choice([
                    'Entrada de estoque',
                    'Ajuste de inventário',
                    'Venda',
                    'Devolução',
                    'Produto danificado',
                    'Correção manual'
                ])
            )
            logs_estoque.append(log)
    print(f"Criados {len(logs_estoque)} logs de estoque")

    # 18. Logs de Ação
    logs_acao = []
    acoes = [
        'Login realizado', 'Produto visualizado', 'Item adicionado ao carrinho',
        'Pedido criado', 'Pagamento processado', 'Produto avaliado',
        'Cupom utilizado', 'Wishlist atualizada', 'Perfil editado'
    ]
    
    for _ in range(100):
        log = LogAcao.objects.create(
            usuario=random.choice(usuarios) if random.random() < 0.9 else None,
            acao=random.choice(acoes),
            detalhes=seeder.faker.sentence()
        )
        logs_acao.append(log)
    print(f"Criados {len(logs_acao)} logs de ação")

    # 19. Histórico de Preços
    historicos = []
    for produto in random.sample(produtos, k=min(30, len(produtos))):
        for _ in range(random.randint(1, 4)):
            historico = HistoricoPreco.objects.create(
                produto=produto,
                preco=Decimal(random.uniform(20, 400)).quantize(Decimal('0.01'))
            )
            historicos.append(historico)
    print(f"Criados {len(historicos)} históricos de preço")

    # 20. Reservas de Estoque
    reservas = []
    for variacao in random.sample(variacoes, k=min(20, len(variacoes))):
        if variacao.estoque > 0:
            try:
                reserva = ReservaEstoque.objects.create(
                    variacao=variacao,
                    quantidade=random.randint(1, min(3, variacao.estoque)),
                    sessao_id=f"session_{random.randint(1000, 9999)}",
                    data_expiracao=timezone.now() + timezone.timedelta(minutes=30),
                    status=random.choice(['P', 'C', 'E', 'L'])
                )
                reservas.append(reserva)
            except:
                pass  # Ignora erros de validação
    print(f"Criadas {len(reservas)} reservas de estoque")

    # 21. Auditoria de Preços
    auditorias = []
    for produto in random.sample(produtos, k=min(15, len(produtos))):
        preco_antigo = produto.preco
        preco_novo = Decimal(random.uniform(20, 400)).quantize(Decimal('0.01'))
        if preco_novo != preco_antigo:
            auditoria = AuditoriaPreco.objects.create(
                produto=produto,
                preco_antigo=preco_antigo,
                preco_novo=preco_novo,
                usuario=random.choice(usuarios) if usuarios else None,
                motivo=random.choice([
                    'Ajuste de preço',
                    'Promoção',
                    'Aumento de custos',
                    'Correção de preço',
                    'Ajuste sazonal'
                ])
            )
            auditorias.append(auditoria)
    print(f"Criadas {len(auditorias)} auditorias de preço")

    # 22. Verificações de Pedido
    verificacoes = []
    for pedido in random.sample(list(Pedido.objects.all()), k=min(10, Pedido.objects.count())):
        verificacao = VerificacaoPedido.objects.create(
            pedido=pedido,
            status=random.choice(['P', 'V', 'E']),
            erros={} if random.random() < 0.8 else {
                'erro_teste': 'Erro simulado para teste'
            }
        )
        verificacao.checksum = verificacao.gerar_checksum()
        verificacao.save()
        verificacoes.append(verificacao)
    print(f"Criadas {len(verificacoes)} verificações de pedido")

    # 23. Proteções de Carrinho
    protecoes = []
    for usuario in usuarios:
        protecao = ProtecaoCarrinho.objects.create(
            sessao_id=f"session_{random.randint(1000, 9999)}",
            usuario=usuario,
            tentativas_manipulacao=random.randint(0, 2),
            bloqueado_ate=timezone.now() + timezone.timedelta(hours=1) if random.random() < 0.2 else None
        )
        protecoes.append(protecao)
    print(f"Criadas {len(protecoes)} proteções de carrinho")

    print("\n" + "="*50)
    print("SEED CONCLUÍDO COM SUCESSO!")
    print("="*50)
    print(f"Resumo dos dados criados:")
    print(f"• {len(categorias)} categorias")
    print(f"• {len(marcas)} marcas")
    print(f"• {len(tags)} tags")
    print(f"• {len(cores_valores + tamanhos_valores + materiais_valores + estilos_valores)} valores de atributos")
    print(f"• {len(usuarios)} usuários")
    print(f"• {len(produtos)} produtos")
    print(f"• {len(variacoes)} variações de produtos")
    print(f"• {len(imagens)} imagens de produtos")
    print(f"• {len(avaliacoes)} avaliações")
    print(f"• {len(enderecos)} endereços")
    print(f"• {len(cupons)} cupons")
    print(f"• {pedidos_criados} pedidos")
    print(f"• {len(carrinhos)} carrinhos")
    print(f"• {len(wishlists)} wishlists")
    print(f"• {len(notifications)} notificações")
    print(f"• {len(reembolsos)} reembolsos")
    print(f"• {len(logs_estoque)} logs de estoque")
    print(f"• {len(logs_acao)} logs de ação")
    print(f"• {len(historicos)} históricos de preço")
    print(f"• {len(reservas)} reservas de estoque")
    print(f"• {len(auditorias)} auditorias de preço")
    print(f"• {len(verificacoes)} verificações de pedido")
    print(f"• {len(protecoes)} proteções de carrinho")
    print("="*50)
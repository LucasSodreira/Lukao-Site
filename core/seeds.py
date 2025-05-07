from django_seed import Seed
from django.contrib.auth import get_user_model
from .models import (
    Categoria, Produto, Endereco, Pedido, ItemPedido, Cor, Marca, ProdutoVariacao,
    ImagemProduto, AvaliacaoProduto, Cupom, Tag, Favorito, Carrinho, ItemCarrinho, Perfil
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

def seed_data(qtd_categorias=3, qtd_produtos=20, qtd_usuarios=0, qtd_enderecos=0, qtd_pedidos=0):
    
    
    reset_pedido_sequence()

    seeder = Seed.seeder()
    User = get_user_model()

    # 1. Categorias
    seeder.add_entity(Categoria, qtd_categorias, {
        'nome': lambda x: seeder.faker.word().capitalize(),
    })
    seeder.execute()
    categorias = list(Categoria.objects.all())
    print(f"Criadas {len(categorias)} categorias")

    # 2. Marcas
    marcas = []
    for i in range(3):
        marca = Marca.objects.create(
            nome=f"Marca {i+1}",
            descricao=seeder.faker.text(max_nb_chars=100)
        )
        marcas.append(marca)
    print(f"Criadas {len(marcas)} marcas")

    # 3. Tags
    tags = []
    for i in range(5):
        tag = Tag.objects.create(nome=f"Tag{i+1}")
        tags.append(tag)
    print(f"Criadas {len(tags)} tags")

    # 4. Cores
    cores_possiveis = [
        {'nome': 'vermelho', 'valor_css': 'red'},
        {'nome': 'azul', 'valor_css': 'blue'},
        {'nome': 'verde', 'valor_css': 'green'},
        {'nome': 'amarelo', 'valor_css': 'yellow'},
        {'nome': 'preto', 'valor_css': 'black'},
        {'nome': 'branco', 'valor_css': 'white'},
    ]
    cor_objs = []
    for cor_dict in cores_possiveis:
        cor_obj = Cor.objects.create(nome=cor_dict['nome'], valor_css=cor_dict['valor_css'])
        cor_objs.append(cor_obj)
    print(f"Criadas {len(cor_objs)} cores")

    # 5. Usuários
    usuarios = []
    for i in range(qtd_usuarios):
        user = User.objects.create_user(
            username=f"user_{i}_{seeder.faker.unique.user_name()}",
            email=f"user_{i}@example.com",
            password='teste123',
            is_active=True
        )
        usuarios.append(user)
    print(f"Criados {len(usuarios)} usuários")

    # 6. Produtos
    produtos = []
    imagem_padrao_path = os.path.join(settings.BASE_DIR, 'media/produtos/camisa.png')
    imagem_url = 'produtos/camisa.png'
    imagem_ja_existe = os.path.exists(imagem_padrao_path)
    imagem_content = None
    if imagem_ja_existe:
        with open(imagem_padrao_path, 'rb') as img_file:
            imagem_content = img_file.read()

    for i in range(qtd_produtos):
        peso = Decimal(random.uniform(0.1, 5.0)).quantize(Decimal('0.001'))
        largura = random.randint(10, 60)
        altura = random.randint(5, 40)
        profundidade = random.randint(1, 30)
        preco = Decimal(random.uniform(10, 1000)).quantize(Decimal('0.01'))
        preco_original = preco + Decimal(random.uniform(1, 50)).quantize(Decimal('0.01'))
        produto = Produto.objects.create(
            nome=f"{seeder.faker.word().capitalize()} {seeder.faker.word().capitalize()}",
            descricao=seeder.faker.text(max_nb_chars=200),
            preco=preco,
            preco_original=preco_original,
            categoria=random.choice(categorias),
            estoque=random.randint(10, 100),
            peso=peso,
            width=largura,
            height=altura,
            length=profundidade,
            marca=random.choice(marcas),
            ativo=True,
            destaque=random.choice([True, False]),
            imagem=imagem_url if imagem_ja_existe else None,
        )
        # Adiciona tags
        produto.tags.set(random.sample(tags, k=random.randint(1, len(tags))))
        produtos.append(produto)
    print(f"Criados {len(produtos)} produtos")

    # 7. ProdutoVariacao
    variacoes = []
    for produto in produtos:
        cores_escolhidas = random.sample(cor_objs, k=random.randint(1, 3))
        tamanhos = [t[0] for t in Produto.SIZE_CHOICES]
        for cor in cores_escolhidas:
            for tamanho in random.sample(tamanhos, k=random.randint(1, len(tamanhos))):
                variacao = ProdutoVariacao.objects.create(
                    produto=produto,
                    cor=cor,
                    tamanho=tamanho,
                    estoque=random.randint(1, 30),
                    peso=Decimal(random.uniform(0.1, 5.0)).quantize(Decimal('0.001')),
                    width=random.randint(10, 60),
                    height=random.randint(5, 40),
                    length=random.randint(1, 30),
                )
                variacoes.append(variacao)
    print(f"Criadas {len(variacoes)} variações de produto")

    # 8. ImagemProduto
    imagens = []
    for produto in produtos:
        for j in range(random.randint(1, 3)):
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
        for _ in range(random.randint(0, 3)):
            if usuarios:
                avaliacao = AvaliacaoProduto.objects.create(
                    produto=produto,
                    usuario=random.choice(usuarios),
                    nota=random.randint(1, 5),
                    comentario=seeder.faker.sentence(),
                    aprovada=True
                )
                avaliacoes.append(avaliacao)
    print(f"Criadas {len(avaliacoes)} avaliações de produtos")

    # 10. Endereços
    enderecos = []
    ESTADOS_SIGLAS = [uf[0] for uf in Endereco.ESTADO_CHOICES]
    for _ in range(qtd_enderecos):
        telefone = f"({random.randint(10, 99)}) {random.randint(90000, 99999)}-{random.randint(1000, 9999)}"
        endereco = Endereco.objects.create(
            nome_completo=seeder.faker.name(),
            telefone=telefone,
            rua=seeder.faker.street_name(),
            numero=str(seeder.faker.building_number()),
            complemento=seeder.faker.secondary_address() if random.random() > 0.7 else None,
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

    # 11. Cupons
    cupons = []
    for i in range(2):
        cupom = Cupom.objects.create(
            codigo=f"CUPOM{i+1}",
            descricao=f"Cupom de desconto {i+1}",
            desconto_percentual=random.choice([None, Decimal('10.00'), Decimal('20.00')]),
            desconto_valor=random.choice([None, Decimal('15.00'), Decimal('30.00')]),
            ativo=True,
            validade=timezone.now() + timezone.timedelta(days=random.randint(5, 30)),
            uso_unico=random.choice([True, False]),
            max_usos=random.choice([None, 10, 50]),
            usuario=random.choice(usuarios) if usuarios and random.random() < 0.5 else None
        )
        cupons.append(cupom)
    print(f"Criados {len(cupons)} cupons")

    # 12. Pedidos e Itens
    status_choices = ['P', 'E', 'C', 'X']
    pedidos_criados = 0
    for i in range(qtd_pedidos):
        try:
            pedido = Pedido.objects.create(
                usuario=random.choice(usuarios) if usuarios and random.random() < 0.9 else None,
                status=random.choice(status_choices),
                endereco_entrega=random.choice(enderecos) if enderecos else None,
                cupom=random.choice(cupons) if cupons and random.random() < 0.5 else None,
                data_criacao=timezone.now()
            )
            itens_produtos = random.sample(produtos, k=random.randint(1, min(5, len(produtos))))
            for produto in itens_produtos:
                variacao = ProdutoVariacao.objects.filter(produto=produto).order_by('?').first()
                ItemPedido.objects.create(
                    pedido=pedido,
                    produto=produto,
                    quantidade=random.randint(1, 5),
                    preco_unitario=produto.preco,
                    variacao=variacao
                )
            pedidos_criados += 1
        except Exception as e:
            print(f"Erro ao criar pedido {i+1}: {str(e)}")
            continue
    print(f"Criados {pedidos_criados}/{qtd_pedidos} pedidos com itens")

    # 13. Favoritos
    favoritos = []
    for usuario in usuarios:
        for produto in random.sample(produtos, k=random.randint(1, min(5, len(produtos)))):
            favorito, _ = Favorito.objects.get_or_create(usuario=usuario, produto=produto)
            favoritos.append(favorito)
    print(f"Criados {len(favoritos)} favoritos")

    # 14. Carrinho e Itens
    carrinhos = []
    itens_carrinho = []
    for usuario in usuarios:
        carrinho = Carrinho.objects.create(usuario=usuario)
        carrinhos.append(carrinho)
        for produto in random.sample(produtos, k=random.randint(1, min(3, len(produtos)))):
            variacao = ProdutoVariacao.objects.filter(produto=produto).order_by('?').first()
            item = ItemCarrinho.objects.create(
                carrinho=carrinho,
                produto=produto,
                quantidade=random.randint(1, 3),
                variacao=variacao
            )
            itens_carrinho.append(item)
    print(f"Criados {len(carrinhos)} carrinhos e {len(itens_carrinho)} itens de carrinho")

    # 15. Perfil
    perfis = []
    for usuario in usuarios:
        endereco = Endereco.objects.filter(usuario=usuario).first()
        perfil = Perfil.objects.create(
            endereco_rapido=endereco,
            metodo_pagamento_rapido=random.choice(['pix', 'boleto', 'cartao']) if random.random() < 0.7 else None
        )
        perfis.append(perfil)
    print(f"Criados {len(perfis)} perfis")

    print("Seed concluído com sucesso!")
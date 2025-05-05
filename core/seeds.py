from django_seed import Seed
from django.contrib.auth import get_user_model
from .models import Categoria, Produto, Endereco, Pedido, ItemPedido
# Adicione os imports dos novos models
from .models import Cor, ProdutoCor, ProdutoVariacao
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

def seed_data(qtd_categorias=3, qtd_produtos=12, qtd_usuarios=0, qtd_enderecos=1, qtd_pedidos=0):
    # Limpa pedidos e reseta sequência
    Pedido.objects.all().delete()
    reset_pedido_sequence()

    seeder = Seed.seeder()
    User = get_user_model()

    # 1. Criar Categorias
    seeder.add_entity(Categoria, qtd_categorias, {
        'nome': lambda x: seeder.faker.word().capitalize(),
    })
    inserted = seeder.execute()
    print(f"Criadas {qtd_categorias} categorias")
    categorias = list(Categoria.objects.all())

    # 2. Criar Usuários
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

    # 3. Criar Cores (caso não existam)
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
        cor_obj, _ = Cor.objects.get_or_create(nome=cor_dict['nome'], defaults={'valor_css': cor_dict['valor_css']})
        cor_objs.append(cor_obj)

    # 4. Criar Produtos e associar cores via ProdutoCor
    produtos = []
    imagem_padrao_path = os.path.join(settings.BASE_DIR, 'media/produtos/camisa.png')
    imagem_content = None
    imagem_url = 'produtos/camisa.png'
    imagem_ja_existe = os.path.exists(imagem_padrao_path)

    if imagem_ja_existe:
        with open(imagem_padrao_path, 'rb') as img_file:
            imagem_content = img_file.read()
    else:
        print(f"AVISO: Imagem padrão não encontrada em {imagem_padrao_path}")

    for i in range(qtd_produtos):
        peso = Decimal(random.uniform(0.1, 5.0)).quantize(Decimal('0.001'))
        largura = random.randint(10, 60)
        altura = random.randint(5, 40)
        profundidade = random.randint(1, 30)

        produto_data = {
            'nome': f"{seeder.faker.word().capitalize()} {seeder.faker.word().capitalize()}",
            'descricao': seeder.faker.text(max_nb_chars=200),
            'preco': Decimal(random.uniform(10, 1000)).quantize(Decimal('0.01')),
            'preco_original': Decimal(random.uniform(10, 1000)).quantize(Decimal('0.01')),
            'categoria': random.choice(categorias),
            'estoque': random.randint(10, 100),
            'tamanho': random.choice([t[0] for t in Produto.SIZE_CHOICES]),
            'tamanhos_disponiveis': ",".join(random.sample(
                [t[0] for t in Produto.SIZE_CHOICES], k=min(random.randint(1, len(Produto.SIZE_CHOICES)), 5)
            )),
            'peso': peso,
            'width': largura,
            'height': altura,
            'length': profundidade,
            'avaliacao': round(random.uniform(0, 5), 1),
        }

        # Ajusta o preço original para ser maior que o preço atual
        if produto_data['preco_original'] < produto_data['preco']:
            produto_data['preco_original'] = produto_data['preco'] + Decimal(random.uniform(1, 50)).quantize(Decimal('0.01'))

        # Se a imagem já existe no media, apenas use o caminho relativo
        if imagem_ja_existe:
            produto_data['imagem'] = imagem_url
        elif imagem_content:
            produto_data['imagem'] = ContentFile(
                imagem_content,
                name=f"produto_{i+1}.png"
            )
        # Se não houver imagem, o campo usará o default do model

        produto = Produto.objects.create(**produto_data)
        produtos.append(produto)

        # Associa de 1 a 3 cores aleatórias ao produto, cada uma com estoque aleatório
        cores_escolhidas = random.sample(cor_objs, k=random.randint(1, 3))
        for cor in cores_escolhidas:
            ProdutoCor.objects.create(
                produto=produto,
                cor=cor,
                estoque=random.randint(1, 30)
            )
            # Cria variações para cada cor e tamanho disponível
            for tamanho in produto.get_tamanhos_disponiveis():
                ProdutoVariacao.objects.create(
                    produto=produto,
                    cor=cor,
                    tamanho=tamanho,
                    estoque=random.randint(1, 30),
                    peso=Decimal(random.uniform(0.1, 5.0)).quantize(Decimal('0.001')),
                    width=random.randint(10, 60),
                    height=random.randint(5, 40),
                    length=random.randint(1, 30),
                )
    print(f"Criados {len(produtos)} produtos com cores")

    # 5. Criar Endereços
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

    # 6. Criar Pedidos
    status_choices = ['P', 'E', 'C', 'X']
    pedidos_criados = 0
    next_id = Pedido.objects.last().id + 1 if Pedido.objects.exists() else 1
    for i in range(qtd_pedidos):
        try:
            pedido = Pedido.objects.create(
                id=next_id + i,
                usuario=random.choice(usuarios) if usuarios and random.random() < 0.9 else None,
                status=random.choice(status_choices),
                endereco_entrega=random.choice(enderecos) if enderecos else None,
                data_criacao=timezone.now()
            )
            itens_produtos = random.sample(produtos, k=random.randint(1, min(5, len(produtos))))
            for produto in itens_produtos:
                ItemPedido.objects.create(
                    pedido=pedido,
                    produto=produto,
                    quantidade=random.randint(1, 5),
                    preco_unitario=produto.preco
                )
            pedidos_criados += 1
        except Exception as e:
            print(f"Erro ao criar pedido {i+1}: {str(e)}")
            continue
    print(f"Criados {pedidos_criados}/{qtd_pedidos} pedidos com itens")
    print("Seed concluído com sucesso!")
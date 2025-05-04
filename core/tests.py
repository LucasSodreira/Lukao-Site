from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from core.models import Produto, Carrinho, ItemCarrinho, Categoria
from checkout.utils import migrar_carrinho_sessao_para_banco

User = get_user_model()

class CarrinhoMigracaoTest(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username='testeuser', email='teste@teste.com', password='123456')
        self.categoria = Categoria.objects.create(nome='Categoria Teste')
        self.produto = Produto.objects.create(
            nome='Produto Teste',
            preco=50.0,
            peso=1,
            categoria=self.categoria
        )
        self.factory = RequestFactory()

    def test_migrar_carrinho_sessao_para_banco(self):
        # Simula login do usuário
        self.client.force_login(self.usuario)
        session = self.client.session
        session['carrinho'] = {
            str(self.produto.id): {
                'produto_id': self.produto.id,
                'quantidade': 2,
                'size': None
            }
        }
        session.save()

        # Cria uma request real com sessão
        request = self.factory.get('/')
        request.user = self.usuario
        request.session = self.client.session  # Usa a sessão real do client

        # Executa a migração
        migrar_carrinho_sessao_para_banco(request)

        # Verifica se o item foi migrado
        carrinho = Carrinho.objects.get(usuario=self.usuario)
        itens = ItemCarrinho.objects.filter(carrinho=carrinho)
        self.assertEqual(itens.count(), 1)
        item = itens.first()
        self.assertEqual(item.produto, self.produto)
        self.assertEqual(item.quantidade, 2)
        self.assertIsNone(item.tamanho)
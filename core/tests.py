from django.test import TestCase
from django.contrib.auth import get_user_model
from core.models import Categoria, Produto, Pedido, ItemPedido, LogStatusPedido

User = get_user_model()

class LogStatusPedidoTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cliente', password='123')
        self.categoria = Categoria.objects.create(nome='Camisetas')
        self.produto = Produto.objects.create(
            nome='Camiseta Básica',
            preco=50,
            categoria=self.categoria,
            estoque=10
        )
        self.pedido = Pedido.objects.create(usuario=self.user, status='P')
        ItemPedido.objects.create(pedido=self.pedido, produto=self.produto, quantidade=1, preco_unitario=50)

    def test_log_status_criado_ao_mudar_status(self):
        # Muda status de Pendente para Concluído
        self.pedido.status = 'C'
        self.pedido.save()
        log = LogStatusPedido.objects.filter(pedido=self.pedido).last()
        self.assertIsNotNone(log)
        self.assertEqual(log.status_antigo, 'P')
        self.assertEqual(log.status_novo, 'C')

        # Muda status de Concluído para Cancelado
        self.pedido.status = 'X'
        self.pedido.save()
        log2 = LogStatusPedido.objects.filter(pedido=self.pedido).last()
        self.assertIsNotNone(log2)
        self.assertEqual(log2.status_antigo, 'C')
        self.assertEqual(log2.status_novo, 'X')
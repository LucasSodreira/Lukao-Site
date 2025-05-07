from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Produto, Categoria, Marca

class ProdutoModelTest(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(nome="Roupas")
        self.marca = Marca.objects.create(nome="Marca Teste")

    def test_criacao_produto_sem_preco_original(self):
        produto = Produto.objects.create(
            nome="Camiseta",
            preco=100,
            categoria=self.categoria,
            marca=self.marca
        )
        self.assertEqual(produto.preco_original, produto.preco)
        self.assertEqual(produto.desconto, 0)

    def test_produto_com_preco_original_maior(self):
        produto = Produto.objects.create(
            nome="Camiseta",
            preco=80,
            preco_original=100,
            categoria=self.categoria,
            marca=self.marca
        )
        self.assertEqual(produto.desconto, 20)

    def test_produto_com_preco_original_menor_erro(self):
        produto = Produto(
            nome="Camiseta",
            preco=100,
            preco_original=90,
            categoria=self.categoria,
            marca=self.marca
        )
        with self.assertRaises(ValidationError):
            produto.full_clean()

    def test_produto_com_preco_promocional(self):
        agora = timezone.now()
        produto = Produto.objects.create(
            nome="Camiseta",
            preco=100,
            preco_original=120,
            preco_promocional=80,
            promocao_inicio=agora,
            promocao_fim=agora + timezone.timedelta(days=1),
            categoria=self.categoria,
            marca=self.marca
        )
        self.assertEqual(produto.preco_vigente(), 80)
        self.assertEqual(produto.calcular_desconto(), 33)  # 120 -> 80 = 33%

    def test_preco_promocional_maior_erro(self):
        produto = Produto(
            nome="Camiseta",
            preco=100,
            preco_promocional=120,
            categoria=self.categoria,
            marca=self.marca
        )
        with self.assertRaises(ValidationError):
            produto.full_clean()

    def test_diminuir_e_aumentar_estoque(self):
        produto = Produto.objects.create(
            nome="Camiseta",
            preco=100,
            categoria=self.categoria,
            marca=self.marca,
            estoque=10
        )
        produto.diminuir_estoque(2)
        self.assertEqual(produto.estoque, 8)
        produto.aumentar_estoque(5)
        self.assertEqual(produto.estoque, 13)
        with self.assertRaises(ValueError):
            produto.diminuir_estoque(0)
        with self.assertRaises(ValueError):
            produto.diminuir_estoque(100)

    def test_estoque_negativo_erro(self):
        produto = Produto(
            nome="Camiseta",
            preco=100,
            categoria=self.categoria,
            marca=self.marca,
            estoque=-1
        )
        with self.assertRaises(ValidationError):
            produto.full_clean()
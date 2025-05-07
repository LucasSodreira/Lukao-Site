document.addEventListener('DOMContentLoaded', () => {
    // Gráfico de Vendas por Dia (Linha)
    const vendasCtx = document.getElementById('vendasChart').getContext('2d');
    new Chart(vendasCtx, {
        type: 'line',
        data: {
            labels: vendasLabels,
            datasets: [{
                label: 'Vendas (R$)',
                data: vendasValues,
                borderColor: '#0d6efd',
                backgroundColor: 'rgba(13, 110, 253, 0.2)',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            scales: {
                x: { title: { display: true, text: 'Data' } },
                y: { title: { display: true, text: 'Valor (R$)' }, beginAtZero: true }
            }
        }
    });

    // Gráfico de Produtos Mais Vendidos (Barras)
    const produtosCtx = document.getElementById('produtosChart').getContext('2d');
    new Chart(produtosCtx, {
        type: 'bar',
        data: {
            labels: produtosLabels,
            datasets: [{
                label: 'Quantidade Vendida',
                data: produtosValues,
                backgroundColor: '#28a745',
            }]
        },
        options: {
            responsive: true,
            scales: {
                x: { title: { display: true, text: 'Produto' } },
                y: { title: { display: true, text: 'Quantidade' }, beginAtZero: true }
            }
        }
    });

    // Gráfico de Estoque por Categoria (Pizza)
    const estoqueCtx = document.getElementById('estoqueChart').getContext('2d');
    new Chart(estoqueCtx, {
        type: 'pie',
        data: {
            labels: estoqueLabels,
            datasets: [{
                label: 'Estoque',
                data: estoqueValues,
                backgroundColor: [
                    '#0d6efd', '#28a745', '#dc3545', '#ffc107', '#17a2b8'
                ],
            }]
        },
        options: {
            responsive: true,
        }
    });
});
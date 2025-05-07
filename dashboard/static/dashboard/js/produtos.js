document.addEventListener('DOMContentLoaded', () => {
    // Gráfico de Estoque por Categoria (Pizza)
    const estoqueCtx = document.getElementById('estoqueChart').getContext('2d');
    new Chart(estoqueCtx, {
        type: 'pie',
        data: {
            labels: estoqueLabels,
            datasets: [{
                label: 'Estoque',
                data: estoqueValues,
                backgroundColor: ['#0d6efd', '#28a745', '#dc3545', '#ffc107', '#17a2b8'],
            }]
        },
        options: {
            responsive: true,
        }
    });

    // Gráfico de Produtos Mais Avaliados (Barras)
    const avaliacoesCtx = document.getElementById('avaliacoesChart').getContext('2d');
    new Chart(avaliacoesCtx, {
        type: 'bar',
        data: {
            labels: avaliacoesLabels,
            datasets: [{
                label: 'Média de Avaliações',
                data: avaliacoesValues,
                backgroundColor: '#17a2b8',
            }]
        },
        options: {
            responsive: true,
            scales: {
                x: { title: { display: true, text: 'Produto' } },
                y: { title: { display: true, text: 'Nota Média' }, beginAtZero: true, max: 5 }
            }
        }
    });
});
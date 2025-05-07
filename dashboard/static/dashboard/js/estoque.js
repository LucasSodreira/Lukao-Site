document.addEventListener('DOMContentLoaded', function () {
    const ctx = document.getElementById('estoqueChart').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: estoqueLabels,
            datasets: [{
                label: 'Estoque Total',
                data: estoqueValues,
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 1
            }]
        },
        options: {
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Quantidade'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Categoria'
                    }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                }
            }
        }
    });
});
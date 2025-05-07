document.addEventListener('DOMContentLoaded', function () {
    const ctx = document.getElementById('cuponsChart').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: cuponsLabels,
            datasets: [{
                label: 'Uso de Cupons',
                data: cuponsValues,
                backgroundColor: 'rgba(153, 102, 255, 0.2)',
                borderColor: 'rgba(153, 102, 255, 1)',
                borderWidth: 1
            }]
        },
        options: {
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Número de Usos'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Cupom'
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
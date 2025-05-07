document.addEventListener('DOMContentLoaded', function () {
    const ctx = document.getElementById('clientesChart').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: clientesLabels,
            datasets: [{
                label: 'Número de Pedidos',
                data: clientesValues,
                backgroundColor: 'rgba(54, 162, 235, 0.2)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            }]
        },
        options: {
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Pedidos'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Cliente'
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
document.addEventListener('DOMContentLoaded', function () {
    const ctx = document.getElementById('reembolsosChart').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: reembolsosLabels,
            datasets: [{
                label: 'Total Reembolsado (R$)',
                data: reembolsosValues,
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
                        text: 'Valor (R$)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Mês'
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
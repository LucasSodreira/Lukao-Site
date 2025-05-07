document.addEventListener('DOMContentLoaded', () => {
    // Gráfico de Pedidos por Status (Pizza)
    const statusCtx = document.getElementById('statusChart').getContext('2d');
    new Chart(statusCtx, {
        type: 'pie',
        data: {
            labels: statusLabels,
            datasets: [{
                label: 'Pedidos',
                data: statusValues,
                backgroundColor: ['#0d6efd', '#dc3545', '#28a745', '#ffc107', '#17a2b8'],
            }]
        },
        options: {
            responsive: true,
        }
    });

    // Gráfico de Evolução de Pedidos (Linha)
    const pedidosCtx = document.getElementById('pedidosChart').getContext('2d');
    new Chart(pedidosCtx, {
        type: 'line',
        data: {
            labels: pedidosLabels,
            datasets: [{
                label: 'Pedidos',
                data: pedidosValues,
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
                y: { title: { display: true, text: 'Quantidade' }, beginAtZero: true }
            }
        }
    });
});
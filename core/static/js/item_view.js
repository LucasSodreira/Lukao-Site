function decreaseQuantity() {
    const quantitySpan = document.getElementById('quantity');
    let currentValue = parseInt(quantitySpan.textContent);
    if (currentValue > 1) {  // Definindo mínimo como 1
        quantitySpan.textContent = currentValue - 1;
    }
}

function increaseQuantity() {
    const quantitySpan = document.getElementById('quantity');
    let currentValue = parseInt(quantitySpan.textContent);
    // Definindo um máximo opcional (remova se não quiser limite)
    const maxQuantity = 10;  // Ou obtenha de algum atributo data-max
    if (currentValue < maxQuantity) {
        quantitySpan.textContent = currentValue + 1;
    }
}


document.addEventListener('DOMContentLoaded', function() {
    // Captura a seleção de tamanho
    const sizeRadios = document.querySelectorAll('.size-radio');
    const selectedSizeInput = document.getElementById('selected-size');
    
    sizeRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            selectedSizeInput.value = this.value;
        });
    });
    
    // Lógica para o botão Buy Now (pode ser igual ao Add to Cart ou diferente)
    const buyNowBtn = document.querySelector('.buy-now-btn');
    buyNowBtn.addEventListener('click', function() {
        const form = document.querySelector('.add-to-cart-form');
        form.submit();
        // Ou redirecionar direto para o checkout
        // window.location.href = "{% url 'review-cart' %}";
    });
});
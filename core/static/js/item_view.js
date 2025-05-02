function updateQuantityDisplay(quantity) {
    document.getElementById("quantity").textContent = quantity;
    document.getElementById("selected-quantity").value = quantity; // Atualiza o campo oculto
}

function decreaseQuantity() {
    let quantity = parseInt(document.getElementById("quantity").textContent);
    if (quantity > 1) {
        quantity--;
        updateQuantityDisplay(quantity);
    }
}

function increaseQuantity() {
    let quantity = parseInt(document.getElementById("quantity").textContent);
    quantity++;
    updateQuantityDisplay(quantity);
}


// Função para alternar a exibição do Bottom Sheet (filtros no mobile)
function toggleBottomSheet() {
    const bottomSheet = document.getElementById('bottomSheet');
    bottomSheet.classList.toggle('open');
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
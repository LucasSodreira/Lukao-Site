function toggleBottomSheet() {
    const bottomSheet = document.getElementById('bottomSheet');
    bottomSheet.classList.toggle('active');
}

// Função para aplicar os filtros
function applyFilters() {
    const selectedSizes = Array.from(document.querySelectorAll('.sizes input:checked')).map(input => input.id);
    const selectedColors = Array.from(document.querySelectorAll('.colors div.selected')).map(div => div.style.backgroundColor);
    const priceRange = document.querySelector('.price-range input').value;

    const products = document.querySelectorAll('.product-card');
    products.forEach(product => {
        const productPrice = parseInt(product.querySelector('.price').textContent.replace('$', ''));
        const productSize = product.dataset.size;
        const productColor = product.dataset.color;

        const matchesSize = selectedSizes.length === 0 || selectedSizes.includes(productSize);
        const matchesColor = selectedColors.length === 0 || selectedColors.includes(productColor);
        const matchesPrice = productPrice <= priceRange;

        if (matchesSize && matchesColor && matchesPrice) {
            product.style.display = 'block';
        } else {
            product.style.display = 'none';
        }
    });
}

// Adiciona evento de clique para os filtros de cores
document.querySelectorAll('.colors div').forEach(colorDiv => {
    colorDiv.addEventListener('click', () => {
        colorDiv.classList.toggle('selected');
    });
});

// Adiciona evento ao botão de aplicar filtros
document.querySelectorAll('.apply-filter').forEach(button => {
    button.addEventListener('click', () => {
        applyFilters();
        toggleBottomSheet(); // Fecha o Bottom Sheet no mobile
    });
});

function toggleSizeFilter(size) {
    const urlParams = new URLSearchParams(window.location.search);
    let sizes = urlParams.get('tamanhos') ? 
                decodeURIComponent(urlParams.get('tamanhos')).split(',') : [];
    
    // Adiciona ou remove o tamanho
    const index = sizes.indexOf(size);
    if (index > -1) {
        sizes.splice(index, 1);
    } else {
        sizes.push(size);
    }
    
    // Atualiza os parâmetros da URL
    if (sizes.length > 0) {
        urlParams.set('tamanhos', sizes.join(','));
    } else {
        urlParams.delete('tamanhos');
    }
    
    // Mantém outros parâmetros existentes (como cores, preço)
    const currentCores = urlParams.get('cores') || '';
    const currentPreco = urlParams.get('preco_max') || '';
    
    // Constrói a nova URL
    let newUrl = window.location.pathname;
    const params = [];
    
    if (sizes.length > 0) params.push(`tamanhos=${sizes.join(',')}`);
    if (currentCores) params.push(`cores=${currentCores}`);
    if (currentPreco) params.push(`preco_max=${currentPreco}`);
    
    if (params.length > 0) {
        newUrl += `?${params.join('&')}`;
    }
    
    window.location.href = newUrl;
}


function toggleMobileColorFilter(color) {
    const colorFilters = document.getElementById('mobileColorFilters');
    let colors = colorFilters.value ? colorFilters.value.split(',') : [];
    if (colors.includes(color)) {
        colors = colors.filter(c => c !== color);
    } else {
        colors.push(color);
    }
    colorFilters.value = colors.join(',');
    document.getElementById('mobileFilterForm').submit();
}

function toggleColorFilter(cor) {
    const colorFiltersInput = document.getElementById('colorFilters');

    // Define a cor selecionada diretamente no campo oculto
    colorFiltersInput.value = cor;

    // Submete o formulário para aplicar o filtro
    
}
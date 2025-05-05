document.addEventListener('DOMContentLoaded', function() {
    const cepInput = document.getElementById('cep-frete');
    const btnCalcular = document.getElementById('btn-calcular-frete');
    const freteStatus = document.getElementById('frete-status');
    const freteValorSpan = document.getElementById('frete-valor-span');
    const totalComFrete = document.getElementById('total-com-frete');
    const subtotal = parseFloat(document.querySelector('.summary-row span:last-child').textContent.replace('R$', '').replace(',', '.'));

    function atualizarTotal(frete) {
        if (!isNaN(frete)) {
            totalComFrete.textContent = 'R$ ' + (subtotal + frete).toFixed(2);
        } else {
            totalComFrete.textContent = 'R$ ' + subtotal.toFixed(2);
        }
    }

    function calcularFrete() {
        const cep = cepInput.value.replace(/\D/g, '');
        if (cep.length !== 8) {
            freteStatus.textContent = 'Digite um CEP válido!';
            freteValorSpan.textContent = 'R$ --';
            atualizarTotal(0);
            return;
        }
        freteStatus.textContent = 'Consultando...';
        freteValorSpan.textContent = 'Calculando...';
        fetch('/calcular-frete/?cep=' + cep)
            .then(resp => resp.json())
            .then(data => {
                if (data.sucesso) {
                    freteValorSpan.textContent = 'R$ ' + data.valor.toFixed(2);
                    freteStatus.textContent = data.descricao || '';
                    atualizarTotal(data.valor);
                } else {
                    freteValorSpan.textContent = 'R$ --';
                    freteStatus.textContent = data.erro || 'Erro ao calcular frete';
                    atualizarTotal(0);
                }
            })
            .catch(() => {
                freteValorSpan.textContent = 'R$ --';
                freteStatus.textContent = 'Erro ao consultar frete';
                atualizarTotal(0);
            });
    }

    if (btnCalcular) {
        btnCalcular.addEventListener('click', calcularFrete);
    }
    if (cepInput) {
        cepInput.addEventListener('keyup', function(e) {
            if (e.key === 'Enter') calcularFrete();
        });
    }

    // Se já tem CEP preenchido (usuário logado), calcula automaticamente
    if (cepInput && cepInput.value.length === 9) {
        calcularFrete();
    }
});

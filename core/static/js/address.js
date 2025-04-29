
document.addEventListener('DOMContentLoaded', function() {
    // Máscara para telefone
    const telefone = document.getElementById('id_telefone');
    if (telefone) {
        telefone.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\D/g, '');
            if (value.length > 2) {
                value = `(${value.substring(0,2)}) ${value.substring(2)}`;
            }
            if (value.length > 10) {
                value = `${value.substring(0,10)}-${value.substring(10,14)}`;
            }
            e.target.value = value;
        });
    }

    // Máscara para CEP
    const cep = document.getElementById('id_cep');
    if (cep) {
        cep.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\D/g, '');
            if (value.length > 5) {
                value = `${value.substring(0,5)}-${value.substring(5,8)}`;
            }
            e.target.value = value;
        });
    }
});
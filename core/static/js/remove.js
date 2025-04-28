
document.querySelectorAll('.remover-form').forEach(function(form) {
  form.addEventListener('submit', function(event) {
    if (!confirm('Tem certeza que deseja remover este item?')) {
      event.preventDefault(); // Se clicar "Cancelar", não envia o form
    }
  });
});

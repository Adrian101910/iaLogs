document.querySelectorAll('[data-analysis-form]').forEach(form => {
  const checkboxes = Array.from(form.querySelectorAll('input[type="checkbox"]'));
  const counter = form.querySelector('[data-selection-count]');
  const count = () => checkboxes.filter(item => item.checked).length;
  checkboxes.forEach(input => input.addEventListener('change', () => {
    if (counter) counter.textContent = count() ? `${count()} eventos seleccionados` : 'Selecciona los eventos relevantes';
  }));
  form.addEventListener('submit', event => {
    if (checkboxes.length && count() === 0) { event.preventDefault(); counter.textContent = 'Selecciona al menos un evento.'; counter.focus(); return; }
    const button = form.querySelector('button[type="submit"]');
    if (button) { button.disabled = true; button.textContent = 'Preparando diagnóstico…'; }
    const progress = form.querySelector('.analysis-progress');
    if (progress) progress.hidden = false;
    form.setAttribute('aria-busy', 'true');
  });
});

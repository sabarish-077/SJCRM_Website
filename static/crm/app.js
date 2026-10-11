(() => {
  const menu = document.querySelector('[data-menu-toggle]');
  const sidebar = document.getElementById('sidebar');
  menu?.addEventListener('click', () => sidebar?.classList.toggle('open'));
  document.querySelectorAll('[data-auto-submit]').forEach((select) => {
    select.addEventListener('change', () => select.form?.requestSubmit());
  });
  document.querySelectorAll('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!window.confirm(form.dataset.confirm || 'Continue?')) event.preventDefault();
    });
  });
  document.addEventListener('click', (event) => {
    if (sidebar?.classList.contains('open') && !sidebar.contains(event.target) && !menu?.contains(event.target)) sidebar.classList.remove('open');
  });
})();

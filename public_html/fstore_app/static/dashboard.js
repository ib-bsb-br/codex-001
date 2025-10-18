(function () {
  const tabs = Array.from(document.querySelectorAll('button.nav-tab'));
  const panels = Array.from(document.querySelectorAll('.panel'));
  if (!tabs.length || !panels.length) return;

  const storageKey = 'fstore_panel';
  const params = new URLSearchParams(location.search);
  let initial = params.get('view') || localStorage.getItem(storageKey) || 'files';
  if (!['files', 'boards'].includes(initial)) initial = 'files';

  function activate(target) {
    tabs.forEach((tab) => {
      const isActive = tab.dataset.target === target;
      tab.classList.toggle('is-active', isActive);
      if (isActive) {
        tab.setAttribute('aria-current', 'page');
      } else {
        tab.removeAttribute('aria-current');
      }
    });
    panels.forEach((panel) => {
      const isActive = panel.dataset.panel === target;
      panel.classList.toggle('is-active', isActive);
      panel.setAttribute('aria-hidden', isActive ? 'false' : 'true');
    });
    localStorage.setItem(storageKey, target);
  }

  activate(initial);
  tabs.forEach((tab) => {
    tab.addEventListener('click', () => activate(tab.dataset.target));
    tab.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
        event.preventDefault();
        const idx = tabs.indexOf(tab);
        const delta = event.key === 'ArrowRight' ? 1 : -1;
        const next = tabs[(idx + delta + tabs.length) % tabs.length];
        next.focus();
        activate(next.dataset.target);
      }
    });
  });
})();

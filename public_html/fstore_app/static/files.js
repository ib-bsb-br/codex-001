(function () {
  const root = document.getElementById('file-app');
  if (!root) return;

  const origin = root.dataset.origin;
  const tableBody = root.querySelector('#files-table tbody');
  const statusEl = document.getElementById('files-status');
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const refreshBtn = document.getElementById('refresh-files');
  const newNoteBtn = document.getElementById('new-note');

  let files = [];
  try {
    files = JSON.parse(root.dataset.files || '[]');
  } catch (err) {
    files = [];
  }

  function encodeName(name) {
    return encodeURIComponent(name);
  }

  function fileUrl(name) {
    return `${origin}/files/${encodeName(name)}`;
  }

  function noteUrl(name) {
    return `${origin}/files/editor/${encodeName(name)}`;
  }

  function notify(message, tone = 'info') {
    if (!statusEl) return;
    statusEl.textContent = message;
    statusEl.dataset.tone = tone;
  }

  function render() {
    if (!tableBody) return;
    tableBody.innerHTML = '';
    files.forEach((entry) => {
      const row = document.createElement('tr');
      row.dataset.name = entry.name;
      row.innerHTML = `
        <td><a href="${fileUrl(entry.name)}" class="file-link">${entry.name}</a></td>
        <td>${entry.mod_time_str}</td>
        <td class="actions">
          <button type="button" class="action" data-action="open">Open</button>
          <button type="button" class="action" data-action="rename">Rename</button>
          <button type="button" class="action warn" data-action="delete">Delete</button>
          ${entry.name.endsWith('.note') ? `<a class="action" data-action="edit" href="${noteUrl(entry.name)}">Edit note</a>` : ''}
        </td>`;
      tableBody.appendChild(row);
    });
  }

  function upsert(entry) {
    const existing = files.findIndex((item) => item.name === entry.name);
    if (existing >= 0) {
      files[existing] = entry;
    } else {
      files.push(entry);
    }
    files.sort((a, b) => b.mod_time - a.mod_time);
    render();
  }

  async function refresh() {
    try {
      const resp = await fetch(`${origin}/api/files`);
      if (!resp.ok) throw new Error(await resp.text());
      files = await resp.json();
      render();
      notify('Refreshed file list', 'ok');
    } catch (err) {
      console.error(err);
      notify('Failed to refresh files', 'error');
    }
  }

  async function uploadSingle(file) {
    const form = new FormData();
    form.append('file', file, file.name);
    try {
      const resp = await fetch(`${origin}/api/files/upload`, {
        method: 'POST',
        body: form,
      });
      if (!resp.ok) throw new Error(await resp.text());
      const payload = await resp.json();
      notify(`Uploaded ${payload.name}`, 'ok');
      await refresh();
    } catch (err) {
      console.error(err);
      notify(`Failed to upload ${file.name}`, 'error');
    }
  }

  function handleFiles(list) {
    const arr = Array.from(list);
    if (!arr.length) return;
    notify(`Uploading ${arr.length} file(s)…`, 'pending');
    arr.reduce((p, file) => p.then(() => uploadSingle(file)), Promise.resolve());
  }

  async function deleteFile(name) {
    const encoded = encodeName(name);
    try {
      const resp = await fetch(`${origin}/api/files/delete/${encoded}`, { method: 'POST' });
      if (!resp.ok) throw new Error(await resp.text());
      notify(`Deleted ${name}`, 'ok');
      files = files.filter((entry) => entry.name !== name);
      render();
    } catch (err) {
      console.error(err);
      notify(`Failed to delete ${name}`, 'error');
    }
  }

  async function renameFile(name) {
    const next = window.prompt('New filename', name);
    if (!next || next === name) return;
    try {
      const resp = await fetch(`${origin}/api/files/rename`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_name: name, new_name: next })
      });
      if (resp.status === 409) {
        notify('Target filename already exists', 'error');
        return;
      }
      if (!resp.ok) throw new Error(await resp.text());
      notify(`Renamed to ${next}`, 'ok');
      await refresh();
    } catch (err) {
      console.error(err);
      notify('Rename failed', 'error');
    }
  }

  function handleAction(event) {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const action = target.dataset.action;
    if (!action) return;
    const row = target.closest('tr');
    if (!row) return;
    const name = row.dataset.name;
    if (!name) return;

    event.preventDefault();

    if (action === 'open') {
      window.open(fileUrl(name), '_blank');
    } else if (action === 'edit') {
      window.location.href = noteUrl(name);
    } else if (action === 'rename') {
      renameFile(name);
    } else if (action === 'delete') {
      if (window.confirm(`Delete ${name}?`)) {
        deleteFile(name);
      }
    }
  }

  async function createNote() {
    const suggested = `note-${new Date().toISOString().slice(0, 10)}.note`;
    let name = window.prompt('Note filename', suggested);
    if (!name) return;
    if (!name.endsWith('.note')) name += '.note';
    name = name.replace(/[^a-zA-Z0-9_.\-\s]/g, '_');
    try {
      const resp = await fetch(`${origin}/api/files/upload-data`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: name, content: '' })
      });
      if (!resp.ok) throw new Error(await resp.text());
      notify(`Created ${name}`, 'ok');
      await refresh();
      window.location.href = noteUrl(name);
    } catch (err) {
      console.error(err);
      notify('Could not create note', 'error');
    }
  }

  // Event bindings
  if (fileInput) {
    fileInput.addEventListener('change', (event) => {
      const list = event.target.files;
      if (list) handleFiles(list);
      fileInput.value = '';
    });
  }

  if (dropZone) {
    ['dragenter', 'dragover'].forEach((type) => {
      dropZone.addEventListener(type, (event) => {
        event.preventDefault();
        dropZone.classList.add('is-dragover');
      });
    });
    ['dragleave', 'drop'].forEach((type) => {
      dropZone.addEventListener(type, (event) => {
        event.preventDefault();
        if (type === 'drop') {
          handleFiles(event.dataTransfer?.files || []);
        }
        dropZone.classList.remove('is-dragover');
      });
    });
    dropZone.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        fileInput?.click();
      }
    });
  }

  tableBody?.addEventListener('click', handleAction);
  refreshBtn?.addEventListener('click', () => refresh());
  newNoteBtn?.addEventListener('click', () => createNote());

  render();
})();

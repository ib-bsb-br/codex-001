(function () {
  const root = document.querySelector('[data-board-slug]');
  if (!root) return;
  const slug = root.dataset.boardSlug;
  const origin = root.dataset.origin;

  const $ = (sel) => document.querySelector(sel);
  const list = $('#list');
  const input = $('#newtodo');
  const title = $('#title');
  const statusEl = $('#status');
  const offlineBanner = $('#offline');
  const slugInput = $('#slug');
  const shareUrl = $('#shareUrl');
  const countsEl = $('#counts');
  const updatedEl = $('#updated');
  const undoBtn = $('#undo');
  const srmsg = $('#srmsg');
  const chips = document.querySelectorAll('.chip');
  const boardsDL = $('#boards');

  let boardETag = null;
  let boardLastMod = null;
  let isSyncing = false;
  let boardData = { title: 'My Todo', tasks: [], created: Date.now() / 1000 | 0, updated: Date.now() / 1000 | 0 };
  let filter = localStorage.getItem('memor_filter') || 'all';
  let searchQuery = localStorage.getItem('memor_search') || '';
  let pendingEdit = null;
  let lastAction = null;
  let undoTimer = null;

  const outboxKey = (b) => `memor_outbox_${b}`;
  const recentBoardsKey = 'memor_recent_boards_v1';
  const boardURL = `${origin}/?b=${encodeURIComponent(slug)}`;

  const generateKey = () => {
    if (window.crypto?.randomUUID) return crypto.randomUUID();
    return `key-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  };

  shareUrl.value = boardURL;
  slugInput.value = slug;

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {});
    });
  }

  function updateOnlineUI() {
    if (navigator.onLine) {
      offlineBanner.classList.remove('show');
    } else {
      offlineBanner.classList.add('show');
    }
  }

  window.addEventListener('online', () => {
    updateOnlineUI();
    flushOutbox();
    fetchBoard(true);
  });
  window.addEventListener('offline', updateOnlineUI);
  updateOnlineUI();

  $('#copy').onclick = async () => {
    try {
      await navigator.clipboard.writeText(boardURL);
      flash('Copied link', 1200);
    } catch (err) {
      flash('Copy failed', 1500);
    }
  };

  let flashTimer = null;
  function flash(msg, persistMs = 1500) {
    clearTimeout(flashTimer);
    statusEl.textContent = msg;
    if (persistMs > 0) {
      flashTimer = setTimeout(() => {
        statusEl.textContent = '';
      }, persistMs);
    }
    srmsg.textContent = msg;
  }

  function showUndo(action) {
    lastAction = action;
    undoBtn.style.display = 'inline-block';
    clearTimeout(undoTimer);
    undoTimer = setTimeout(() => {
      hideUndo();
    }, 10000);
  }

  function hideUndo() {
    lastAction = null;
    undoBtn.style.display = 'none';
  }

  undoBtn.onclick = async () => {
    if (!lastAction) return;
    const act = lastAction;
    hideUndo();
    if (act.type === 'del') {
      const t = act.payload;
      await op({ op: 'add', text: t.text });
      flash('Undid delete', 1000);
    } else if (act.type === 'clear_done') {
      for (const t of act.payload) {
        await op({ op: 'add', text: t.text });
      }
      flash('Restored completed', 1200);
    }
  };

  function fmtRelTime(ts) {
    const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
    if (s < 5) return 'just now';
    if (s < 60) return `${s}s ago`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h / 24);
    return `${d}d ago`;
  }

  function updateMeta(d) {
    const activeCount = (d.tasks || []).filter((t) => !t.done).length;
    const total = (d.tasks || []).length;
    countsEl.textContent = total ? `${activeCount} item${activeCount !== 1 ? 's' : ''} left • ${total} total` : 'No tasks';
    updatedEl.textContent = `Updated ${fmtRelTime(d.updated || Date.now() / 1000 | 0)}`;
    $('#toggleAll').textContent = activeCount > 0 ? 'Complete all' : 'Uncheck all';
  }

  function applyFilter(tasks) {
    let arr = tasks.slice();
    const q = (searchQuery || '').toLowerCase();
    if (filter === 'active') arr = arr.filter((t) => !t.done);
    if (filter === 'done') arr = arr.filter((t) => t.done);
    if (q) arr = arr.filter((t) => (t.text || '').toLowerCase().includes(q));
    return arr;
  }

  function updateFilterUI() {
    chips.forEach((ch) => {
      const isActive = ch.getAttribute('data-filter') === filter;
      ch.classList.toggle('active', isActive);
      ch.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });
    $('#search').value = searchQuery;
  }

  function reorderAllowed() {
    return filter === 'all' && !searchQuery;
  }

  function pushRecentBoard(slugValue) {
    try {
      const raw = localStorage.getItem(recentBoardsKey);
      let arr = raw ? JSON.parse(raw) : [];
      arr = arr.filter((s) => s !== slugValue);
      arr.unshift(slugValue);
      if (arr.length > 10) arr.length = 10;
      localStorage.setItem(recentBoardsKey, JSON.stringify(arr));
      renderBoardsList();
    } catch (err) {
      // ignore
    }
  }

  function renderBoardsList() {
    try {
      const raw = localStorage.getItem(recentBoardsKey);
      const arr = raw ? JSON.parse(raw) : [];
      boardsDL.innerHTML = arr.map((s) => `<option value="${s}"></option>`).join('');
    } catch (err) {
      // ignore
    }
  }

  function render(board) {
    boardData = board;
    title.value = board.title || 'My Todo';
    updateMeta(board);
    renderBoardsList();

    const tasks = applyFilter(board.tasks || []);
    list.innerHTML = '';
    const allowDrag = reorderAllowed();
    if (!allowDrag) {
      list.setAttribute('data-drag-disabled', 'true');
    } else {
      list.removeAttribute('data-drag-disabled');
    }

    tasks.forEach((task) => {
      const li = document.createElement('li');
      li.setAttribute('tabindex', '0');
      if (task.done) li.classList.add('done');
      li.dataset.id = task.id;
      li.draggable = allowDrag;
      li.innerHTML = `
        <span class="drag" title="${allowDrag ? 'Drag to reorder' : 'Reorder disabled while filtering/searching'}">⋮⋮</span>
        <input type="checkbox" ${task.done ? 'checked' : ''} data-id="${task.id}" aria-label="Mark task done">
        <span class="txt" contenteditable="true" data-id="${task.id}" spellcheck="false" role="textbox" aria-multiline="false"></span>
        <button class="secondary" data-del="${task.id}" aria-label="Delete task">Delete</button>`;
      li.querySelector('.txt').textContent = task.text;

      if (allowDrag) {
        li.addEventListener('dragstart', (e) => {
          e.dataTransfer.setData('text/plain', task.id);
          li.classList.add('dragging');
        });
        li.addEventListener('dragend', () => {
          li.classList.remove('dragging');
        });
        li.addEventListener('dragover', (e) => {
          e.preventDefault();
          const dragging = list.querySelector('.dragging');
          if (!dragging || dragging === li) return;
          const rect = li.getBoundingClientRect();
          const before = (e.clientY - rect.top) < rect.height / 2;
          list.insertBefore(dragging, before ? li : li.nextSibling);
        });
        li.addEventListener('drop', async (e) => {
          e.preventDefault();
          const order = Array.from(list.querySelectorAll('li')).map((node) => node.dataset.id);
          await op({ op: 'reorder', order });
          flash('Reordered', 800);
        });
      }

      list.appendChild(li);
    });
  }

  function reorderByKeyboard(id, delta) {
    const tasks = (boardData.tasks || []).map((t) => t.id);
    const index = tasks.indexOf(id);
    if (index < 0) return;
    const target = Math.max(0, Math.min(tasks.length - 1, index + delta));
    if (target === index) return;
    tasks.splice(index, 1);
    tasks.splice(target, 0, id);
    op({ op: 'reorder', order: tasks }).then(() => flash('Reordered', 800));
  }

  async function fetchBoard(force = false) {
    const url = `/api/boards/${encodeURIComponent(slug)}`;
    const headers = {};
    if (boardETag && !force) headers['If-None-Match'] = boardETag;
    if (boardLastMod && !force) headers['If-Modified-Since'] = boardLastMod;
    try {
      const res = await fetch(url, { headers });
      if (res.status === 304) return;
      if (!res.ok) throw new Error('Network error');
      const data = await res.json();
      boardETag = res.headers.get('ETag');
      boardLastMod = res.headers.get('Last-Modified');
      render(data);
      pushRecentBoard(slug);
      flash('Loaded', 800);
    } catch (err) {
      flash('Offline (cached view)', 1500);
    }
  }

  function queueOp(payload, token, etag) {
    const key = outboxKey(slug);
    const arr = JSON.parse(localStorage.getItem(key) || '[]');
    arr.push({ payload, key: token, etag });
    localStorage.setItem(key, JSON.stringify(arr));
    offlineBanner.classList.add('show');
  }

  async function flushOutbox() {
    if (isSyncing) return;
    const key = outboxKey(slug);
    let arr = JSON.parse(localStorage.getItem(key) || '[]');
    if (!arr.length || !navigator.onLine) return;
    isSyncing = true;
    try {
      while (arr.length && navigator.onLine) {
        const entry = arr[0];
        const payload = entry.payload || entry;
        const token = entry.key || generateKey();
        const etag = entry.etag || boardETag;
        const result = await op(payload, {
          silent: true,
          idempotencyKey: token,
          etag,
          fromQueue: true,
        });
        if (!result) break;
        arr.shift();
        localStorage.setItem(key, JSON.stringify(arr));
      }
      if (arr.length === 0) {
        offlineBanner.classList.remove('show');
        flash('Synced', 1000);
        fetchBoard(true);
      }
    } catch (err) {
      // keep queue for retry
    } finally {
      isSyncing = false;
    }
  }

  async function op(payload, opts = {}) {
    const idKey = opts.idempotencyKey || generateKey();
    let etag = opts.etag || boardETag;
    if (!etag) {
      await fetchBoard(true);
      etag = boardETag;
    }
    if (!etag) {
      if (!opts.fromQueue) {
        queueOp(payload, idKey, null);
        if (!opts.silent) flash('Queued (offline)', 1500);
      }
      return null;
    }
    try {
      const res = await fetch(`/api/boards/${encodeURIComponent(slug)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'If-Match': etag,
          'Idempotency-Key': idKey,
        },
        body: JSON.stringify(payload),
      });
      if (res.status === 409) {
        if (!opts.silent) flash('Update conflict detected. Refreshing…', 1800);
        await fetchBoard(true);
        return null;
      }
      if (res.status === 428) {
        if (!opts.silent) flash('Missing concurrency headers', 1800);
        return null;
      }
      if (!res.ok) throw new Error('Bad response');
      const data = await res.json();
      boardETag = res.headers.get('ETag') || boardETag;
      boardLastMod = res.headers.get('Last-Modified') || boardLastMod;
      if (!opts.silent) render(data);
      return data;
    } catch (err) {
      if (!opts.fromQueue) {
        queueOp(payload, idKey, etag);
        if (!opts.silent) flash('Queued (offline)', 1500);
      }
      return null;
    }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    chips.forEach((chip) => {
      chip.addEventListener('click', () => {
        filter = chip.getAttribute('data-filter');
        localStorage.setItem('memor_filter', filter);
        updateFilterUI();
        render(boardData);
      });
    });

    $('#search').addEventListener('input', (e) => {
      searchQuery = e.target.value.trim();
      localStorage.setItem('memor_search', searchQuery);
      render(boardData);
    });

    updateFilterUI();
    await fetchBoard(true);
    await flushOutbox();

    $('#add').onclick = () => {
      const value = input.value.trim();
      if (value) {
        op({ op: 'add', text: value }).then(() => {
          input.value = '';
          input.focus();
          flash('Added', 800);
        });
      }
    };

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        $('#add').click();
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        input.value = '';
        input.blur();
      }
      if (e.ctrlKey && e.key === '/') {
        e.preventDefault();
        input.focus();
      }
    });

    let titleOrig = '';
    title.addEventListener('focus', () => {
      titleOrig = title.value;
    });

    $('#saveTitle').onclick = () => {
      const ttl = title.value.trim() || 'My Todo';
      op({ op: 'title', title: ttl }).then(() => flash('Saved', 900));
    };

    title.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        $('#saveTitle').click();
        title.blur();
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        title.value = titleOrig;
        title.blur();
        flash('Canceled', 800);
      }
    });

    title.addEventListener('blur', () => $('#saveTitle').click());

    $('#clearDone').onclick = () => {
      const cleared = (boardData.tasks || []).filter((t) => t.done);
      if (!cleared.length) {
        flash('No completed tasks', 1200);
        return;
      }
      op({ op: 'clear_done' }).then(() => {
        flash('Cleared completed', 1000);
        showUndo({ type: 'clear_done', payload: cleared });
      });
    };

    $('#clearAll').onclick = () => {
      const total = (boardData.tasks || []).length;
      if (!total) {
        flash('No tasks to clear', 1200);
        return;
      }
      if (confirm(`Delete all ${total} tasks?`)) {
        op({ op: 'clear_all' }).then(() => flash('All cleared', 1000));
      }
    };

    $('#toggleAll').onclick = () => {
      const anyActive = (boardData.tasks || []).some((t) => !t.done);
      op({ op: 'set_all', done: anyActive }).then(() => flash(anyActive ? 'Completed all' : 'Unchecked all', 1000));
    };

    $('#switch').onclick = () => {
      const s = (slugInput.value || '').trim();
      if (!s) return;
      window.location = `${origin}/?b=${encodeURIComponent(s)}`;
    };

    $('#newBoard').onclick = () => {
      window.location = '/boards/new';
    };

    document.addEventListener('keydown', (e) => {
      if (e.ctrlKey && e.key === '/') {
        e.preventDefault();
        input.focus();
      }
      if (!e.ctrlKey && !e.metaKey && !e.altKey && e.key === '/') {
        e.preventDefault();
        $('#search').focus();
      }
      if (e.key === 'n' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        if (document.activeElement !== input && document.activeElement !== title) {
          input.focus();
        }
      }
      if (!e.ctrlKey && !e.metaKey && !e.altKey && (e.key === 'j' || e.key === 'k')) {
        const items = Array.from(list.querySelectorAll('li'));
        if (!items.length) return;
        const active = document.activeElement?.closest?.('li');
        let index = items.indexOf(active);
        if (index === -1) index = e.key === 'j' ? -1 : items.length;
        const next = e.key === 'j' ? Math.min(items.length - 1, index + 1) : Math.max(0, index - 1);
        items[next].focus();
      }
      if ((e.ctrlKey || e.metaKey) && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
        const active = document.activeElement?.closest?.('li');
        if (!active) return;
        const id = active.dataset.id;
        if (!id) return;
        e.preventDefault();
        const delta = e.key === 'ArrowUp' ? -1 : 1;
        reorderByKeyboard(id, delta);
      }
    });

    list.addEventListener('change', (e) => {
      const id = e.target.getAttribute('data-id');
      if (id && e.target.type === 'checkbox') {
        op({ op: 'toggle', id });
      }
    });

    list.addEventListener('click', (e) => {
      const id = e.target.getAttribute('data-del');
      if (id) {
        const task = (boardData.tasks || []).find((x) => x.id === id);
        op({ op: 'del', id }).then(() => {
          flash('Deleted', 900);
          if (task) showUndo({ type: 'del', payload: task });
        });
      }
    });

    list.addEventListener('keydown', (e) => {
      const li = e.target.closest('li');
      if (!li) return;
      if (e.target === li) {
        if (e.key === ' ') {
          e.preventDefault();
          const cb = li.querySelector('input[type=checkbox]');
          if (cb) {
            cb.checked = !cb.checked;
            cb.dispatchEvent(new Event('change'));
          }
        }
        if (e.key === 'Delete' || e.key === 'Backspace') {
          e.preventDefault();
          const id = li.querySelector('[data-del]')?.getAttribute('data-del');
          if (id) {
            const task = (boardData.tasks || []).find((x) => x.id === id);
            op({ op: 'del', id }).then(() => {
              flash('Deleted', 900);
              if (task) showUndo({ type: 'del', payload: task });
            });
          }
        }
        if (e.key.toLowerCase() === 'e') {
          e.preventDefault();
          const txt = li.querySelector('.txt');
          if (txt) txt.focus();
        }
      }

      if (e.target.classList.contains('txt')) {
        if (e.key === 'Enter') {
          e.preventDefault();
          e.target.blur();
        } else if (e.key === 'Escape') {
          e.preventDefault();
          if (pendingEdit && pendingEdit.id === e.target.getAttribute('data-id')) {
            e.target.textContent = pendingEdit.orig;
          }
          e.target.blur();
          flash('Canceled', 800);
        } else if (e.key === 'Tab') {
          e.preventDefault();
          const elements = Array.from(list.querySelectorAll('.txt'));
          const index = elements.indexOf(e.target);
          const next = elements[index + (e.shiftKey ? -1 : 1)];
          e.target.blur();
          if (next) next.focus();
        }
      }
    });

    list.addEventListener('focusin', (e) => {
      if (e.target.classList.contains('txt')) {
        pendingEdit = { id: e.target.getAttribute('data-id'), orig: e.target.textContent };
        const range = document.createRange();
        range.selectNodeContents(e.target);
        range.collapse(false);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
      }
    });

    list.addEventListener('blur', (e) => {
      if (e.target.classList.contains('txt')) {
        const id = e.target.getAttribute('data-id');
        const text = e.target.textContent.trim();
        if (pendingEdit && pendingEdit.id === id) {
          if (text !== pendingEdit.orig) {
            op({ op: 'edit', id, text }).then(() => flash('Saved', 800));
          }
        }
        pendingEdit = null;
      }
    }, true);
  });

  (function initUI() {
    updateFilterUI();
  })();
})();

/* 本地管理端：编辑、实时预览和切换词条前自动保存。 */
(function () {
  const $ = (selector) => document.querySelector(selector);
  const state = { items: [], current: null, dirty: false, saving: false };
  const api = (url, options) => fetch(url, options).then((response) => response.json());
  if (!['127.0.0.1', 'localhost'].includes(location.hostname)) {
    $('.editor').innerHTML = '<div class="empty">管理端仅在本地服务器模式可用。</div>';
    return;
  }
  const escapeHtml = (value) => String(value || '').replace(/[&<>"']/g, (c) => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));

  function preview(source) {
    if (/<\/?[a-z][^>]*>/i.test(source || '')) return source;
    let html = escapeHtml(source || '')
      .replace(/^={2,6}\s*(.*?)\s*={2,6}$/gm, '<h2>$1</h2>')
      .replace(/'''(.*?)'''/g, '<strong>$1</strong>')
      .replace(/''(.*?)''/g, '<em>$1</em>')
      .replace(/\[\[(?:File|文件):([^\]|]+)(?:\|[^\]]*)?\]\]/gi, '<span class="attachment">附件：$1</span>')
      .replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (_, target, label) => `<a href="#">${label || target}</a>`);
    return html.split(/\n\s*\n/).filter(Boolean).map((part) => `<p>${part.replace(/\n/g, '<br>')}</p>`).join('');
  }

  function collectForm() {
    return { ...state.current, title: $('#title').value.trim() || '未命名词条', date: $('#date').value, tags: $('#tags').value.split(',').map((x) => x.trim()).filter(Boolean), body: $('#source').value };
  }

  async function saveDraft(silent = false) {
    if (!state.current || !state.current.slug || !state.dirty || state.saving) return;
    state.saving = true;
    try {
      const item = collectForm();
      await api('/api/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(item) });
      state.current = item;
      state.dirty = false;
      if (!silent) $('#admin-status').textContent = '已自动保存到本地文件';
    } finally { state.saving = false; }
  }

  function renderList() {
    const query = ($('#admin-filter').value || '').toLowerCase();
    $('#admin-list').innerHTML = state.items.filter((item) => (item.title || '').toLowerCase().includes(query)).map((item) => `<button data-slug="${escapeHtml(item.slug)}">${escapeHtml(item.title || '未命名词条')}</button>`).join('');
    document.querySelectorAll('#admin-list button').forEach((button) => { button.onclick = async () => { await saveDraft(true); load(button.dataset.slug); }; });
  }

  function fill(item) {
    state.current = item; state.dirty = false;
    $('#title').value = item.title || '未命名词条'; $('#date').value = item.date || '';
    $('#tags').value = (item.tags || []).join(','); $('#source').value = item.body || '';
    $('#preview').innerHTML = preview(item.body || '');
  }
  function load(slug) { api('/api/entry?slug=' + encodeURIComponent(slug)).then((item) => item && item.title ? fill(item) : Promise.reject(new Error('词条详情加载失败'))).catch((error) => { $('#admin-status').textContent = error.message; }); }
  function refresh() { api('/api/entries').then((items) => { state.items = items.filter((item) => item.title); renderList(); if (!state.current && state.items[0]) load(state.items[0].slug); }); }

  ['title', 'date', 'tags', 'source'].forEach((id) => $('#' + id).addEventListener('input', () => { state.dirty = true; if (id === 'source') $('#preview').innerHTML = preview($('#source').value); }));
  $('#admin-filter').oninput = async () => { await saveDraft(true); renderList(); };
  $('#save').onclick = () => saveDraft(false).then(refresh);
  $('#delete').onclick = async () => { if (!state.current || !confirm('确认删除该词条？')) return; await saveDraft(true); await api('/api/delete', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ slug:state.current.slug }) }); state.current = null; refresh(); };
  $('#new-entry').onclick = async () => { await saveDraft(true); fill({ slug:'', title:'新词条', date:new Date().toISOString().slice(0,10), tags:['文章'], body:'== 简介 ==\n\n在这里编写词条。' }); };
  window.addEventListener('beforeunload', () => { if (state.dirty) saveDraft(true); });
  refresh();
})();

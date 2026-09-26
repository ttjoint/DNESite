/* 中国人Wiki：主题切换与首页搜索控制器。 */
(function () {
  const $ = (selector) => document.querySelector(selector);
  const saved = localStorage.getItem('wiki-theme');
  const theme = saved || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  document.documentElement.dataset.theme = theme;

  const toggle = document.createElement('button');
  toggle.className = 'theme-toggle';
  toggle.type = 'button';
  toggle.textContent = theme === 'dark' ? '☀ 白天' : '☾ 夜间';
  toggle.onclick = () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    localStorage.setItem('wiki-theme', next);
    toggle.textContent = next === 'dark' ? '☀ 白天' : '☾ 夜间';
  };
  const header = document.querySelector('.site-header');
  if (header) header.append(toggle);
  else document.querySelector('.hero-inner')?.prepend(toggle);

  const input = $('#search');
  const list = $('#result-list');
  if (!input || !list) return;
  const normalize = (value) => String(value || '').toLocaleLowerCase('zh-CN').normalize('NFKC').replace(/\s+/g, '');
  const escapeHtml = (value) => String(value || '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  let entries = [];

  function score(query, entry, exact) {
    const title = normalize(entry.title);
    const body = normalize(`${entry.title} ${entry.text} ${(entry.tags || []).join(' ')}`);
    if (exact) return title === query ? 200 : body.includes(query) ? 20 : 0;
    return (title === query ? 120 : title.includes(query) ? 80 : 0) + (body.includes(query) ? 35 : 0);
  }

  function render() {
    const query = normalize(input.value);
    const exact = $('#exact')?.checked;
    const sort = $('#sort')?.value || 'relevance';
    const tag = $('#tag-filter')?.value || '';
    const rows = entries.map((entry) => ({ ...entry, score: query ? score(query, entry, exact) : 1 }))
      .filter((entry) => (!query || entry.score > 0) && (!tag || entry.tags?.includes(tag)));
    rows.sort((a, b) => sort === 'date' ? (b.date || '').localeCompare(a.date || '') : sort === 'length' ? (a.text || '').length - (b.text || '').length : sort === 'title' ? a.title.localeCompare(b.title, 'zh-CN') : b.score - a.score || a.title.localeCompare(b.title, 'zh-CN'));
    list.innerHTML = rows.slice(0, 500).map((entry) => `<a class="result-item" href="${entry.url}">${entry.media ? `<div class="result-media-preview">${entry.media.type.startsWith("image/") ? `<img src="${entry.media.path}" alt="">` : entry.media.type.startsWith("video/") ? `<video muted src="${entry.media.path}"></video>` : "♫"}</div>` : ""}<div class="result-title">${escapeHtml(entry.title)}</div><div class="result-meta">${(entry.tags || []).map(escapeHtml).join(' · ')} · ${escapeHtml(entry.date || '')}</div><div class="result-snippet">${escapeHtml((entry.text || '').slice(0, 180))}${(entry.text || '').length > 180 ? '…' : ''}</div></a>`).join('') || '<div class="empty">没有找到匹配词条。</div>';
    $('#search-count').textContent = query ? `${rows.length} 条结果` : '';
  }

  fetch('search-index.json').then((r) => r.json()).then((index) => { entries = index; return fetch('metadata.json'); }).then((r) => r.ok ? r.json() : []).then((metadata) => {
    const bySlug = new Map(metadata.map((entry) => [entry.slug, entry]));
    entries = entries.map((entry) => ({ ...entry, ...(bySlug.get(entry.url.split('/').pop()) || {}) }));
    const select = $('#tag-filter');
    if (select) select.innerHTML = '<option value="">全部分类</option>' + [...new Set(entries.flatMap((entry) => entry.tags || []))].map((tag) => `<option>${escapeHtml(tag)}</option>`).join('');
    return fetch('media-index.json').then((r) => r.ok ? r.json() : []).then((media) => {
      entries = entries.concat(media.map((item) => ({ title: item.name, text: item.type, tags: ['媒体'], date: item.date ? new Date(item.date * 1000).toISOString().slice(0, 10) : '', url: `media/${item.slug}.html`, media: item })));
      render();
    });
  });
  input.addEventListener('input', render);
  ['exact', 'sort', 'tag-filter'].forEach((id) => $(`#${id}`)?.addEventListener('change', render));
})();


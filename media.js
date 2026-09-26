/* 媒体资源页：紧凑预览、关键词过滤和排序。 */
(function () {
  const query = document.querySelector('#media-search');
  const sort = document.querySelector('#media-sort');
  const list = document.querySelector('#media-list');
  let media = [];
  const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (c) => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
  const preview = (item) => item.type.startsWith('image/') ? `<img loading="lazy" src="${item.path}" alt="${escapeHtml(item.name)}">` : item.type.startsWith('video/') ? `<video muted preload="metadata" src="${item.path}"></video>` : item.type.startsWith('audio/') ? '<span class="media-icon">♫</span>' : '<span class="media-icon">FILE</span>';
  function render() {
    const q = (query.value || '').toLowerCase();
    const rows = media.filter((item) => (item.name + item.type).toLowerCase().includes(q));
    rows.sort((a, b) => sort.value === 'size' ? b.size - a.size : sort.value === 'date' ? b.date - a.date : q ? (a.name.toLowerCase().indexOf(q) - b.name.toLowerCase().indexOf(q)) : a.name.localeCompare(b.name));
    list.innerHTML = rows.slice(0, 800).map((item) => `<a class="media-card" href="media/${item.slug}.html"><div class="media-thumb">${preview(item)}</div><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.type)} · ${item.size.toLocaleString()} bytes</small></a>`).join('') || '<div class="empty">没有找到媒体文件。</div>';
  }
  fetch('media-index.json').then((r) => r.json()).then((items) => { media = items; render(); });
  query.oninput = render; sort.onchange = render;
})();

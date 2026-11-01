// Feedback only: no fetch, timer, refresh, build or image preloading.
for (const form of document.querySelectorAll('form[data-busy]')) {
  form.addEventListener('submit', event => {
    if (form.dataset.running) { event.preventDefault(); return; }
    form.dataset.running = 'true';
    form.setAttribute('aria-busy', 'true');
    const message = document.createElement('span');
    message.setAttribute('role', 'status');
    message.textContent = form.dataset.busy + ' Keep this window open.';
    form.append(message);
    for (const button of form.querySelectorAll('button')) button.disabled = true;
  });
}
for (const img of document.querySelectorAll('.video-thumbnail,.channel-avatar')) {
  const fallback = () => { img.hidden = true; };
  img.addEventListener('error', fallback);
  if (img.complete && img.naturalWidth === 0) fallback();
}

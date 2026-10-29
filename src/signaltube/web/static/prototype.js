// Visual preview only. All interactions live in memory; no fetch, storage or form submission.
(() => {
  const ids = [...new Set([...document.querySelectorAll('[data-video]')].map(el => el.dataset.video))];
  let state, last = null, view = 'watch', category = 'all';
  const toast = document.getElementById('toast');
  const player = document.getElementById('sample-player');
  const hero = document.querySelector('.hero');
  const placeholder = document.createElement('div');
  placeholder.className = 'hero-placeholder'; placeholder.hidden = true;
  const heading = document.createElement('h2'); heading.textContent = 'One less thing to decide.';
  const note = document.createElement('p'); note.textContent = 'You’ve dealt with this sample pick. The other uploads are still waiting. Use Undo to bring it back.';
  placeholder.append(heading, note); hero.after(placeholder);
  function notify(message, undo = false) {
    document.getElementById('toast-text').textContent = message;
    document.getElementById('undo').hidden = !undo; toast.hidden = false;
  }
  function render() {
    const pending = ids.filter(id => !state[id].handled).length;
    const saved = ids.filter(id => state[id].saved).length;
    document.querySelectorAll('[data-count]').forEach(el => el.textContent = {pending, saved, handled:ids.length-pending}[el.dataset.count]);
    document.querySelectorAll('[data-action="save"]').forEach(el => {
      const yes = state[el.dataset.id].saved;
      el.setAttribute('aria-pressed', String(yes));
      el.querySelector('.save-label').textContent = yes ? 'Saved' : 'Save';
    });
    const query = document.getElementById('sample-search').value.toLowerCase();
    document.querySelectorAll('[data-video]').forEach(el => {
      const id = el.dataset.video;
      el.hidden = !!state[id].handled || (el.classList.contains('queue-card') &&
        ((category !== 'all' && el.dataset.categoryName !== category) || !el.dataset.search.includes(query)));
    });
    placeholder.hidden = !hero.hidden;
    document.querySelectorAll('[data-saved-video]').forEach(el => el.hidden = !state[el.dataset.savedVideo].saved);
    document.querySelectorAll('[data-group]').forEach(el => el.hidden = !el.querySelector('.queue-card:not([hidden])'));
    document.getElementById('catchup-empty').hidden = !!document.querySelector('[data-group]:not([hidden])');
    document.getElementById('saved-empty').hidden = saved > 0;
    document.querySelectorAll('[data-panel]').forEach(el => el.hidden = el.dataset.panel !== view);
    document.querySelectorAll('.nav-item').forEach(el => {
      el.classList.toggle('active', el.dataset.view === view);
      if (el.dataset.view === view) el.setAttribute('aria-current','page'); else el.removeAttribute('aria-current');
    });
    document.getElementById('view-label').textContent = {watch:'Watch next',catchup:'Catch up',saved:'Saved'}[view];
  }
  function reset() {
    state = Object.fromEntries(ids.map(id => [id,{saved:['game','tools'].includes(id),handled:null}]));
    last = null; category = 'all'; document.getElementById('sample-search').value = '';
    document.querySelectorAll('[data-category]').forEach(el => {
      const yes = el.dataset.category === 'all'; el.classList.toggle('selected',yes); el.setAttribute('aria-pressed',String(yes));
    });
    toast.hidden = true; render();
  }
  document.querySelectorAll('[data-view]').forEach(el => el.addEventListener('click',() => {
    view = el.dataset.view; render();
    const heading = document.querySelector(`[data-panel="${view}"] h1`);
    heading.tabIndex = -1; heading.focus({preventScroll:true}); window.scrollTo({top:0,behavior:'instant'});
  }));
  document.querySelectorAll('[data-category]').forEach(el => el.addEventListener('click',() => {
    category = el.dataset.category;
    document.querySelectorAll('[data-category]').forEach(other => {
      const yes = other === el; other.classList.toggle('selected',yes); other.setAttribute('aria-pressed',String(yes));
    }); render();
  }));
  document.getElementById('sample-search').addEventListener('input',render);
  document.querySelectorAll('[data-action]').forEach(el => el.addEventListener('click',() => {
    last = structuredClone(state);
    const item = state[el.dataset.id], action = el.dataset.action;
    if(action === 'save') item.saved = !item.saved; else item.handled = action;
    render();
    notify(action === 'save' ? (item.saved ? 'Saved in this demo. It stays in Catch up until you deal with it.' : 'Removed from the demo saved queue.') : (action === 'watched' ? 'Marked watched in this demo.' : 'Dismissed in this demo.'), true);
    if(action !== 'save') document.getElementById('undo').focus({preventScroll:true});
  }));
  document.getElementById('undo').addEventListener('click',() => {
    if(last){state=last;last=null;render();notify('Undone. Your sample queue is restored.');}
  });
  document.querySelectorAll('[data-play]').forEach(el => el.addEventListener('click',() => {
    document.getElementById('player-title').textContent = el.dataset.play; player.showModal();
  }));
  ['close-player','player-done'].forEach(id => document.getElementById(id).addEventListener('click',() => player.close()));
  document.getElementById('reset-demo').addEventListener('click',reset);
  document.getElementById('rebuild-demo').textContent = 'About this sample shortlist';
  document.getElementById('rebuild-demo').addEventListener('click',() => notify('These are fixed design examples, not generated recommendations. The working app still builds only when you choose.'));
  reset();
})();

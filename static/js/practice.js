// ================================================================
// practice.js  ·  LeetCode-style coding environment
// ================================================================

'use strict';

// ── state ──────────────────────────────────────────────────────
let editor = null;
let currentQuestion = null;
let currentBoilerplate = '';
let customCases = [];
let activeCaseIdx = 0;
let editorFontSize = 14;

// ================================================================
// CUSTOM DRAG-DIVIDER ENGINE  (zero dependencies)
// ================================================================
//
// Three independent drag handles:
//   1. #div-sidebar    — sidebar width      (col-resize)
//   2. #div-horizontal — left vs right pane (col-resize)
//   3. #div-vertical   — editor vs console  (row-resize)
//
// Each divider reads its adjacent panes' bounding boxes on
// mousedown, then applies pixel widths/heights on mousemove so
// Monaco can recalculate. Min-size limits prevent full collapse.

const MIN_SIDEBAR   = 160;   // px  — sidebar minimum
const MIN_DESC      = 260;   // px  — description pane minimum
const MIN_EDITOR_R  = 320;   // px  — right side minimum width
const MIN_EDITOR_H  = 80;    // px  — editor pane min height
const MIN_CONSOLE_H = 60;    // px  — console pane min height

/** makeDivider(divEl, options)
 *  divEl    — the .drag-divider element
 *  dir      — 'h' (horizontal col-resize) | 'v' (vertical row-resize)
 *  paneA    — element resized on the left / top
 *  paneB    — element resized on the right / bottom
 *  minA/minB — minimum sizes in px
 *  onDone   — callback after mouse-up (e.g. trigger Monaco layout)
 */
function makeDivider({ divEl, dir, paneA, paneB, minA, minB, onDone }) {
  if (!divEl || !paneA || !paneB) return;

  divEl.addEventListener('mousedown', startDrag);
  divEl.addEventListener('touchstart', startDrag, { passive: false });

  function startDrag(e) {
    e.preventDefault();

    // snapshot starting conditions
    const isTouch   = e.type === 'touchstart';
    const startX    = isTouch ? e.touches[0].clientX : e.clientX;
    const startY    = isTouch ? e.touches[0].clientY : e.clientY;
    const startSizeA = dir === 'h' ? paneA.offsetWidth : paneA.offsetHeight;
    const startSizeB = dir === 'h' ? paneB.offsetWidth : paneB.offsetHeight;
    const total      = startSizeA + startSizeB;

    divEl.classList.add('dragging');
    document.body.classList.add('is-dragging');
    document.body.style.cursor = dir === 'h' ? 'col-resize' : 'row-resize';

    function onMove(ev) {
      const clientX = ev.touches ? ev.touches[0].clientX : ev.clientX;
      const clientY = ev.touches ? ev.touches[0].clientY : ev.clientY;
      const delta   = dir === 'h' ? (clientX - startX) : (clientY - startY);

      let newA = startSizeA + delta;
      let newB = startSizeB - delta;

      // clamp to minimum sizes
      if (newA < minA) { newA = minA; newB = total - minA; }
      if (newB < minB) { newB = minB; newA = total - minB; }

      if (dir === 'h') {
        paneA.style.width = newA + 'px';
        paneA.style.flex  = 'none';
        paneB.style.width = newB + 'px';
        paneB.style.flex  = 'none';
      } else {
        paneA.style.height = newA + 'px';
        paneA.style.flex   = 'none';
        paneB.style.height = newB + 'px';
        paneB.style.flex   = 'none';
      }

      // keep Monaco in sync every frame
      if (typeof editor !== 'undefined' && editor) editor.layout();
    }

    function onUp() {
      divEl.classList.remove('dragging');
      document.body.classList.remove('is-dragging');
      document.body.style.cursor = '';
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      document.removeEventListener('touchmove', onMove);
      document.removeEventListener('touchend', onUp);
      if (onDone) onDone();
    }

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
    document.addEventListener('touchmove', onMove, { passive: false });
    document.addEventListener('touchend', onUp);
  }
}

// ── 1. Sidebar divider ────────────────────────────────────────
// Runs immediately (sidebar is always visible)
makeDivider({
  divEl: document.getElementById('div-sidebar'),
  dir:   'h',
  paneA: document.getElementById('sidebar-pane'),
  paneB: document.getElementById('workspace-pane'),
  minA:  MIN_SIDEBAR,
  minB:  500,
  onDone: () => { if (editor) editor.layout(); },
});

// Set sidebar default width explicitly so flex math is predictable
(function setSidebarDefault() {
  const sb = document.getElementById('sidebar-pane');
  const ws = document.getElementById('workspace-pane');
  if (sb && ws) {
    const totalW = sb.parentElement.offsetWidth;
    const sbW    = Math.round(totalW * 0.22);
    sb.style.width = sbW + 'px';
    sb.style.flex  = 'none';
    // workspace-pane keeps flex:1 so it fills the rest
  }
})();

// ── 2. Left/Right divider (lazy — created when workspace opens) ──
let leftRightDividerMade = false;
function initHorizontalDivider() {
  if (leftRightDividerMade) return;
  leftRightDividerMade = true;

  const paneA = document.getElementById('left-pane');
  const paneB = document.getElementById('right-pane');

  // Default: 40 / 60 split of the available workspace width
  const aw = document.getElementById('active-workspace').offsetWidth;
  const leftW = Math.round(aw * 0.40);
  paneA.style.width = leftW + 'px';
  paneA.style.flex  = 'none';
  // paneB keeps flex:1

  makeDivider({
    divEl: document.getElementById('div-horizontal'),
    dir:   'h',
    paneA,
    paneB,
    minA:  MIN_DESC,
    minB:  MIN_EDITOR_R,
    onDone: () => { if (editor) editor.layout(); },
  });
}

// ── 3. Editor/Console divider (lazy — created when workspace opens) ──
let editorConsoleDividerMade = false;
function initVerticalDivider() {
  if (editorConsoleDividerMade) return;
  editorConsoleDividerMade = true;

  const paneA = document.getElementById('editor-pane');
  const paneB = document.getElementById('console-pane');

  // Default: 60 / 40 split of right pane height
  const rh = document.getElementById('right-pane').offsetHeight;
  const edH = Math.round(rh * 0.60);
  paneA.style.height = edH + 'px';
  paneA.style.flex   = 'none';
  // paneB keeps flex:1

  makeDivider({
    divEl: document.getElementById('div-vertical'),
    dir:   'v',
    paneA,
    paneB,
    minA:  MIN_EDITOR_H,
    minB:  MIN_CONSOLE_H,
    onDone: () => { if (editor) editor.layout(); },
  });
}

// ── Sidebar toggle ────────────────────────────────────────────
window.toggleSidebar = function () {
  const sb = document.getElementById('sidebar-pane');
  if (!sb) return;
  if (sb.offsetWidth <= MIN_SIDEBAR + 10) {
    // re-open to default
    const totalW = sb.parentElement.offsetWidth;
    sb.style.width = Math.round(totalW * 0.22) + 'px';
  } else {
    // collapse — but keep the divider grabable: leave 4px
    sb.style.width = '4px';
  }
  if (editor) editor.layout();
};

// ── Console expand / collapse helpers (rewired below) ─────────
window.collapseConsole = function () {
  const paneA = document.getElementById('editor-pane');
  const paneB = document.getElementById('console-pane');
  if (!paneA || !paneB) return;
  const rh = document.getElementById('right-pane').offsetHeight;
  paneA.style.height = (rh - MIN_CONSOLE_H - 5) + 'px';
  paneA.style.flex   = 'none';
  paneB.style.height = MIN_CONSOLE_H + 'px';
  paneB.style.flex   = 'none';
  if (editor) editor.layout();
};
window.expandConsole = function () {
  const paneA = document.getElementById('editor-pane');
  const paneB = document.getElementById('console-pane');
  if (!paneA || !paneB) return;
  const rh = document.getElementById('right-pane').offsetHeight;
  paneA.style.height = MIN_EDITOR_H + 'px';
  paneA.style.flex   = 'none';
  paneB.style.height = (rh - MIN_EDITOR_H - 5) + 'px';
  paneB.style.flex   = 'none';
  if (editor) editor.layout();
};

// ================================================================
// MONACO EDITOR
// ================================================================
try {
  require.config({
    paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs' },
  });
  require(['vs/editor/editor.main'], () => {
    editor = monaco.editor.create(document.getElementById('monaco-editor'), {
      value: currentBoilerplate || '# Select a question to start',
      language: 'python',
      theme: 'vs-dark',
      automaticLayout: true,
      minimap: { enabled: false },
      fontSize: editorFontSize,
      fontFamily: '"JetBrains Mono","Fira Code","Cascadia Code",Menlo,Consolas,monospace',
      fontLigatures: true,
      lineHeight: 22,
      padding: { top: 14, bottom: 14 },
      scrollBeyondLastLine: false,
      renderLineHighlight: 'gutter',
      scrollbar: { verticalScrollbarSize: 6, horizontalScrollbarSize: 6 },
    });

    // update Ln/Col status bar
    editor.onDidChangeCursorPosition(pos => {
      const el = document.getElementById('editor-ln-col');
      if (el) el.textContent = `Ln ${pos.position.lineNumber}, Col ${pos.position.column}`;
    });

    // Ctrl+Enter → run
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => executeCode('run'));

    // mark saved on change
    let saveTimer;
    editor.onDidChangeModelContent(() => {
      const lbl = document.getElementById('editor-saved-lbl');
      if (lbl) { lbl.textContent = 'Unsaved'; lbl.style.color = '#fbbf24'; }
      clearTimeout(saveTimer);
      saveTimer = setTimeout(() => {
        if (lbl) { lbl.textContent = 'Saved'; lbl.style.color = ''; }
      }, 1200);
    });
  });
} catch (e) {
  console.error('Monaco failed', e);
}

// ── font size ──────────────────────────────────────────────────
document.getElementById('font-decrease-btn').addEventListener('click', () => {
  editorFontSize = Math.max(10, editorFontSize - 1);
  editor?.updateOptions({ fontSize: editorFontSize });
  document.getElementById('plain-editor').style.fontSize = editorFontSize + 'px';
});
document.getElementById('font-increase-btn').addEventListener('click', () => {
  editorFontSize = Math.min(24, editorFontSize + 1);
  editor?.updateOptions({ fontSize: editorFontSize });
  document.getElementById('plain-editor').style.fontSize = editorFontSize + 'px';
});

// ── fullscreen ─────────────────────────────────────────────────
document.getElementById('fullscreen-btn').addEventListener('click', () => {
  if (!document.fullscreenElement) {
    document.getElementById('active-workspace')?.requestFullscreen?.();
  } else {
    document.exitFullscreen?.();
  }
  const icon = document.querySelector('#fullscreen-btn i');
  if (icon) icon.className = document.fullscreenElement ? 'fas fa-compress-alt' : 'fas fa-expand-alt';
});

// ── console expand / close ─────────────────────────────────────
document.getElementById('console-expand-btn').addEventListener('click', () => window.expandConsole());
document.getElementById('console-close-btn').addEventListener('click',  () => window.collapseConsole());

// ── reset ──────────────────────────────────────────────────────
document.getElementById('reset-btn').addEventListener('click', () => {
  if (!currentBoilerplate) return;
  if (document.getElementById('editor-mode').value === 'interview') {
    document.getElementById('plain-editor').value = currentBoilerplate;
  } else {
    editor?.setValue(currentBoilerplate);
  }
});

// ── sync from file ─────────────────────────────────────────────
document.getElementById('sync-btn').addEventListener('click', async () => {
  try {
    const r = await fetch('/practice/api/code');
    const d = await r.json();
    if (d.code === null) return;
    if (document.getElementById('editor-mode').value === 'interview') {
      document.getElementById('plain-editor').value = d.code;
    } else {
      editor?.setValue(d.code);
    }
  } catch (e) { console.error('sync failed', e); }
});

// ── editor mode toggle ─────────────────────────────────────────
document.getElementById('editor-mode').addEventListener('change', e => {
  const isPlain = e.target.value === 'interview';
  const mono = document.getElementById('monaco-editor');
  const plain = document.getElementById('plain-editor');
  if (isPlain) {
    plain.value = editor?.getValue() ?? '';
    mono.style.display = 'none';
    plain.style.display = 'block';
  } else {
    editor?.setValue(plain.value);
    plain.style.display = 'none';
    mono.style.display = 'block';
    setTimeout(() => editor?.layout(), 50);
  }
});

// ================================================================
// INIT DATA LOAD
// ================================================================
// sidebar divider is already wired above at module load time
loadInitData();

window.closeSidebar = function() {
  document.getElementById('sidebar-pane').style.display = 'none';
  document.getElementById('div-sidebar').style.display = 'none';
  document.getElementById('sidebar-toggle-btn').style.display = 'flex';
};

window.openSidebar = function() {
  document.getElementById('sidebar-pane').style.display = 'flex';
  document.getElementById('div-sidebar').style.display = 'flex';
  document.getElementById('sidebar-toggle-btn').style.display = 'none';
};

// Sidebar toggle functionality
document.getElementById('sidebar-close-btn')?.addEventListener('click', closeSidebar);
document.getElementById('sidebar-toggle-btn')?.addEventListener('click', openSidebar);

async function loadInitData() {
  try {
    const res = await fetch('/practice/api/init');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    window.sheetsData = data.sheets;

    const sel = document.getElementById('sheet-select');
    sel.innerHTML = '';

    const urlQ = window.INITIAL_SHEET || new URLSearchParams(location.search).get('sheet');
    for (const name in data.sheets) {
      const opt = document.createElement('option');
      opt.value = opt.textContent = name;
      if (name === urlQ) opt.selected = true;
      sel.appendChild(opt);
    }
    sel.addEventListener('change', populateSidebar);
    if (Object.keys(data.sheets).length) populateSidebar();
  } catch (err) {
    console.error('init failed', err);
    document.getElementById('patterns-container').innerHTML =
      '<div style="color:#888;font-size:13px;padding:20px;text-align:center">Failed to load problems</div>';
  }
}

// ================================================================
// SIDEBAR  –  pattern groups + question items
// ================================================================
function populateSidebar() {
  const sel = document.getElementById('sheet-select');
  const sheet = sel.value;
  if (!sheet || !window.sheetsData) return;

  const questions = window.sheetsData[sheet] || [];
  const container = document.getElementById('patterns-container');
  container.innerHTML = '';

  const groups = { "Questions": questions };
  let globalIdx = 0;

  const firstKey = Object.keys(groups)[0];

  for (const [cat, qs] of Object.entries(groups)) {
    const done = qs.filter(q => q.completed).length;

    // ── header ──
    const hdr = document.createElement('div');
    hdr.className = 'pat-hdr';
    hdr.setAttribute('role', 'button');
    hdr.setAttribute('tabindex', '0');
    hdr.setAttribute('aria-expanded', cat === firstKey ? 'true' : 'false');
    hdr.innerHTML = `
      <span class="pat-hdr-l">
        <i class="fas fa-chevron-right pat-chevron"></i>
        <span>${cat}</span>
      </span>
      <span class="pat-count">${done}/${qs.length}</span>`;

    // ── list ──
    const ul = document.createElement('ul');
    ul.className = 'q-list';
    ul.setAttribute('role', 'list');

    qs.forEach(q => {
      globalIdx++;
      const li = document.createElement('li');
      li.className = 'q-item';
      li.setAttribute('role', 'listitem');
      li.setAttribute('tabindex', '0');
      li.dataset.qid = q.id;
      li.innerHTML = `
        <span class="q-num">${globalIdx}.</span>
        <span class="q-name">${q.name}</span>
        <span class="q-check">${q.completed ? '<i class="fas fa-check"></i>' : ''}</span>`;

      const pick = () => {
        document.querySelectorAll('.q-item.selected').forEach(el => el.classList.remove('selected'));
        li.classList.add('selected');
        loadQuestion(q.category, q.id, q.name);
      };
      li.addEventListener('click', pick);
      li.addEventListener('keydown', e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), pick()));
      ul.appendChild(li);
    });

    // toggle
    const toggle = () => {
      const open = ul.classList.toggle('open');
      hdr.querySelector('.pat-chevron').style.transform = open ? 'rotate(90deg)' : '';
      hdr.setAttribute('aria-expanded', String(open));
    };
    hdr.addEventListener('click', toggle);
    hdr.addEventListener('keydown', e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), toggle()));

    if (cat === firstKey) { ul.classList.add('open'); hdr.querySelector('.pat-chevron').style.transform = 'rotate(90deg)'; }

    container.appendChild(hdr);
    container.appendChild(ul);
  }
  
  // auto-load if in url or window var
  const targetQ = window.INITIAL_QID || new URLSearchParams(location.search).get('q');
  if (targetQ) {
    // If the sidebar is hidden via CSS, clicking the DOM element might not trigger visually or might be tricky
    // It's safer to locate the target question object in the array and load it directly
    const qObj = questions.find(q => String(q.id) === String(targetQ) || q.slug === targetQ);
    
    if (qObj) {
      const el = document.querySelector(`.q-item[data-qid="${qObj.slug}"]`) || document.querySelector(`.q-item[data-qid="${qObj.id}"]`);
      if (el) {
        el.click(); // Keep active classes in sync if sidebar is showing
      } else {
        // Fallback direct load if sidebar item wasn't rendered
        loadQuestion(sheet, qObj.slug || qObj.id, qObj.name);
      }
    } else {
      // Fallback if not found in current sheet (e.g. cross-sheet deep link)
      loadQuestion(sheet, targetQ, "Question");
    }
    
    // clear to prevent reopening
    window.INITIAL_QID = null;
    const url = new URL(window.location);
    if (url.searchParams.has('q')) {
      url.searchParams.delete('q');
      window.history.replaceState({}, '', url);
    }
  }
}

// ================================================================
// QUESTION LOAD
// ================================================================
async function loadQuestion(category, q_id, q_name) {
  try {
    const res = await fetch(`/practice/api/question/${category}/${q_id}`);
    const data = await res.json();
    if (data.error) return alert(data.error);

    const meta = data.metadata ?? {};
    const qInfoData = data.q_info ?? {};
    currentQuestion = { category, q_id, metadata: meta, param_names: data.param_names };
    currentBoilerplate = data.boilerplate ?? '';

    showActive();
    setTimeout(() => {
      initHorizontalDivider();
      initVerticalDivider();
    }, 60);

    // ── title ──
    const titleText = qInfoData.id ? `${qInfoData.id}. ${qInfoData.name || q_name}` : (qInfoData.name || q_name);
    document.getElementById('current-question-title').textContent = titleText;
    
    // Update URL to use titleSlug if available, fallback to id
    const slug_or_id = qInfoData.titleSlug || q_id;
    window.history.pushState({}, "", `/practice/${category}/${slug_or_id}`);

    // ── badges row (Difficulty, Topics, Companies) ──
    const diff = (qInfoData.difficulty ?? 'medium').toLowerCase();
    const db = document.getElementById('diff-badge');
    db.className = `badge badge-${diff}`;
    db.textContent = qInfoData.difficulty ?? 'Medium';

    const tb = document.getElementById('topics-badge');
    if (qInfoData.topics?.length) tb.title = qInfoData.topics.join(', ');

    const cb = document.getElementById('companies-badge');
    if (qInfoData.companies?.length) cb.title = qInfoData.companies.join(', ');

    const hb = document.getElementById('hint-badge');
    if (meta.hint) { hb.style.display = 'inline-flex'; hb.title = meta.hint; }
    else hb.style.display = 'none';

    // ── completion ──
    const sheet = document.getElementById('sheet-select').value;
    const qInfo = window.sheetsData?.[sheet]?.find(q => String(q.id) === String(q_id));
    const cs = document.getElementById('completion-status');
    cs.style.display = (qInfo?.completed) ? 'inline-flex' : 'none';

    // ── markdown & parsing for structure ──
    const mc = document.getElementById('markdown-content');
    
    // Parse description, examples, constraints
    let descriptionText = data.description ?? '';
    let constraints = data.constraints ?? [];
    let examples = data.examples ?? [];
    
    // Check if testcases exist for Examples
    let examplesHtml = '';
    if (examples.length > 0) {
      examplesHtml = '<div style="margin-top:24px;">';
      examples.forEach((tc, idx) => {
        examplesHtml += `<p><strong>Example ${idx + 1}:</strong></p>`;
        examplesHtml += `<pre style="background:var(--lc-panel);padding:10px;border-radius:var(--lc-r2);margin-bottom:16px;">`;
        examplesHtml += `<strong>Input:</strong> ${typeof tc.input === 'string' ? tc.input : JSON.stringify(tc.input).replace(/^\[|\]$/g, '')}\n`;
        examplesHtml += `<strong>Output:</strong> ${typeof tc.output === 'string' ? tc.output : (typeof tc.expected === 'string' ? tc.expected : JSON.stringify(tc.output || tc.expected || ''))}\n`;
        if (tc.explanation) {
          examplesHtml += `<strong>Explanation:</strong> ${tc.explanation}\n`;
        }
        examplesHtml += `</pre>`;
      });
      examplesHtml += '</div>';
    }

    let parsedDesc = typeof marked !== 'undefined' && typeof marked.parse === 'function' ? marked.parse(descriptionText) : descriptionText;
    let parsedConstraints = '';
    if (constraints && constraints.length > 0) {
      parsedConstraints = `<div style="margin-top:24px;"><p><strong>Constraints:</strong></p><ul>`;
      constraints.forEach(c => {
        let text = typeof marked !== 'undefined' && typeof marked.parseInline === 'function' ? marked.parseInline(c) : c;
        parsedConstraints += `<li><code>${text}</code></li>`;
      });
      parsedConstraints += `</ul></div>`;
    }
    
    // Real Acceptance Rate
    const stats = qInfoData.stats || {};
    const totalAccepted = stats.totalAccepted || 0;
    const totalSubmissions = stats.totalSubmissions || 0;
    
    const formatNumber = (num) => {
        if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
        if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
        return num;
    };
    
    let accRate = stats.acceptanceRate || 0;
    if (totalSubmissions > 0 && accRate === 0) {
        accRate = (totalAccepted / totalSubmissions * 100);
    }
    accRate = accRate.toFixed(1);
    
    let statsHtml = `
      <div style="margin-top:24px;padding-top:16px;border-top:1px solid var(--lc-border);display:flex;gap:24px;font-size:13px;color:var(--lc-t2);">
        <div>Accepted <strong style="color:var(--lc-t1)">${formatNumber(totalAccepted)}</strong><span style="opacity:0.5">/${formatNumber(totalSubmissions)}</span></div>
        <div>Acceptance Rate <strong style="color:var(--lc-t1)">${accRate}%</strong></div>
      </div>
    `;
    
    // Topics Accordion
    let topicsAccordion = '';
    if (qInfoData.topics?.length) {
      topicsAccordion = `
        <div style="margin-top:16px;border-top:1px solid var(--lc-border);">
          <details style="padding:12px 0;">
            <summary style="cursor:pointer;display:flex;align-items:center;gap:8px;font-size:14px;color:var(--lc-t1);">
              <i class="bi bi-tag" style="color:var(--lc-t2);"></i> Topics <i class="bi bi-chevron-down" style="margin-left:auto;font-size:12px;color:var(--lc-t3);"></i>
            </summary>
            <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">
              ${qInfoData.(topics ?? []).map(t => `<span style="background:#333;padding:4px 12px;border-radius:12px;font-size:12px;color:var(--lc-t2);">${t}</span>`).join('')}
            </div>
          </details>
        </div>
      `;
    }

    // Companies Accordion
    let companiesAccordion = '';
    if (qInfoData.companies?.length) {
      companiesAccordion = `
        <div style="border-top:1px solid var(--lc-border);">
          <details style="padding:12px 0;">
            <summary style="cursor:pointer;display:flex;align-items:center;gap:8px;font-size:14px;color:var(--lc-yellow);">
              <i class="bi bi-briefcase"></i> Companies <i class="bi bi-chevron-down" style="margin-left:auto;font-size:12px;color:var(--lc-t3);"></i>
            </summary>
            <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">
              ${qInfoData.(companies ?? []).map(c => `<span style="background:#333;padding:4px 12px;border-radius:12px;font-size:12px;color:var(--lc-t2);">${c}</span>`).join('')}
            </div>
          </details>
        </div>
      `;
    }
    
    // Similar Questions
    let similarQuestions = '';
    if (qInfoData.similarQuestions && qInfoData.similarQuestions.length > 0) {
      similarQuestions = `
        <div style="border-top:1px solid var(--lc-border);border-bottom:1px solid var(--lc-border);">
          <details style="padding:12px 0;">
            <summary style="cursor:pointer;display:flex;align-items:center;gap:8px;font-size:14px;color:var(--lc-t1);">
              <i class="bi bi-diagram-2" style="color:var(--lc-green);"></i> Similar Questions <i class="bi bi-chevron-down" style="margin-left:auto;font-size:12px;color:var(--lc-t3);"></i>
            </summary>
            <div style="display:flex;flex-direction:column;gap:8px;margin-top:12px;padding-left:24px;">
              ${qInfoData.similarQuestions.map(sq => `
                <a href="/practice/${currentQuestion.category}/${sq.titleSlug || sq.questionId || sq.slug}" style="color:var(--lc-t1);text-decoration:none;font-size:13px;">
                  ${sq.title} <span class="badge badge-${(sq.difficulty || 'medium').toLowerCase()}" style="float:right;">${sq.difficulty || 'Medium'}</span>
                </a>
              `).join('')}
            </div>
          </details>
        </div>
      `;
    }

    mc.innerHTML = parsedDesc + examplesHtml + parsedConstraints + statsHtml + topicsAccordion + companiesAccordion + similarQuestions;

    // ── editor ──
    if (editor) editor.setValue(currentBoilerplate);
    document.getElementById('plain-editor').value = currentBoilerplate;

    // ── test cases ──
    customCases = (meta.test_cases ?? []).slice(0, 3).map(tc => JSON.parse(JSON.stringify(tc)));
    activeCaseIdx = 0;
    renderTestcases();

    // ── reset result ──
    document.getElementById('result-display').innerHTML =
      '<div class="result-empty" style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;color:var(--lc-t3);">You must run your code first</div>';
    document.getElementById('result-display').classList.add('result-empty');
    switchConsoleTab('testcase');
    switchDescTab('description');
    startStopwatch();
  } catch (e) {
    console.error('loadQuestion error', e);
    alert('Error loading question: ' + e.message);
  }
}

// ── show/hide panels ───────────────────────────────────────────
function showEmpty() {
  document.getElementById('empty-workspace').style.display = 'flex';
  document.getElementById('active-workspace').style.display = 'none';
}
function showActive() {
  document.getElementById('empty-workspace').style.display = 'none';
  document.getElementById('active-workspace').style.display = 'flex';
}

// ================================================================
// STOPWATCH
// ================================================================
let swTimer = null, swSec = 0;

function startStopwatch() {
  swSec = 0;
  clearInterval(swTimer);
  swTimer = setInterval(() => {
    swSec++;
    const el = document.getElementById('timer-display');
    if (el) el.textContent = fmtTime(swSec);
  }, 1000);
}
function fmtTime(s) {
  const m = Math.floor(s / 60).toString().padStart(2, '0');
  const ss = (s % 60).toString().padStart(2, '0');
  return `${m}:${ss}`;
}

// ================================================================
// TAB SWITCHING
// ================================================================
function switchDescTab(id) {
  document.querySelectorAll('[data-desc-tab]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.descTab === id);
    btn.setAttribute('aria-selected', btn.dataset.descTab === id);
  });
  document.querySelectorAll('[id^="desc-panel-"]').forEach(panel => {
    panel.classList.toggle('active', panel.id === `desc-panel-${id}`);
  });
  
  if (id === 'submissions') loadSubmissions();
  if (id === 'solutions') loadSolutions();
}

function switchConsoleTab(id) {
  document.querySelectorAll('[data-tab]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === id);
  });
  document.getElementById('tab-testcase').style.display = id === 'testcase' ? 'block' : 'none';
  document.getElementById('tab-result').style.display   = id === 'result'   ? 'block' : 'none';
}

document.getElementById('close-submission-tab')?.addEventListener('click', (e) => {
  e.stopPropagation();
  document.getElementById('desc-tab-submission').style.display = 'none';
  switchDescTab('description');
});

// wire up desc tabs
document.querySelectorAll('[data-desc-tab]').forEach(btn => {
  btn.addEventListener('click', () => switchDescTab(btn.dataset.descTab));
  btn.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); switchDescTab(btn.dataset.descTab); } });
});

// wire up console tabs
document.querySelectorAll('[data-tab]').forEach(btn => {
  btn.addEventListener('click', () => switchConsoleTab(btn.dataset.tab));
  btn.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); switchConsoleTab(btn.dataset.tab); } });
});

// legacy alias
window.switchTab = switchConsoleTab;

// ================================================================
// TEST CASES
// ================================================================
function renderTestcases() {
  const pills = document.getElementById('tc-pills');
  pills.innerHTML = '';

  customCases.forEach((_, idx) => {
    const p = document.createElement('div');
    p.className = 'tc-pill' + (idx === activeCaseIdx ? ' active' : '');
    p.textContent = `Case ${idx + 1}`;
    p.setAttribute('role', 'button');
    p.setAttribute('tabindex', '0');
    const pick = () => { activeCaseIdx = idx; renderTestcases(); };
    p.addEventListener('click', pick);
    p.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); } });
    pills.appendChild(p);
  });

  renderTCEditor();
}

function renderTCEditor() {
  const wrap = document.getElementById('tc-editor');
  wrap.innerHTML = '';
  if (!customCases.length || !currentQuestion) return;

  const tc = customCases[activeCaseIdx];
  const params = currentQuestion.param_names ?? [];

  params.forEach((param, idx) => {
    const g = document.createElement('div');
    g.className = 'tc-group';

    const lbl = document.createElement('label');
    lbl.className = 'tc-label';
    lbl.textContent = `${param} =`;
    lbl.setAttribute('for', `tc-in-${idx}`);

    const inp = document.createElement('input');
    inp.type = 'text';
    inp.className = 'tc-input';
    inp.id = `tc-in-${idx}`;
    inp.value = tc.input[idx] != null ? JSON.stringify(tc.input[idx]) : '';
    inp.addEventListener('change', e => {
      try { tc.input[idx] = JSON.parse(e.target.value); }
      catch { tc.input[idx] = e.target.value; }
    });

    g.appendChild(lbl);
    g.appendChild(inp);
    wrap.appendChild(g);
  });
}

document.getElementById('add-tc-btn').addEventListener('click', () => {
  if (!currentQuestion) return;
  customCases.push({ input: currentQuestion.param_names.map(() => null), expected: null });
  activeCaseIdx = customCases.length - 1;
  renderTestcases();
});

document.getElementById('rm-tc-btn').addEventListener('click', () => {
  if (customCases.length > 1) {
    customCases.splice(activeCaseIdx, 1);
    activeCaseIdx = Math.max(0, activeCaseIdx - 1);
    renderTestcases();
  }
});

// ================================================================
// EXECUTION
// ================================================================
function getCode() {
  return document.getElementById('editor-mode').value === 'interview'
    ? document.getElementById('plain-editor').value
    : (editor?.getValue() ?? '');
}

function setBtnLoading(id, loading) {
  const btn = document.getElementById(id);
  if (!btn) return;
  // find run-play or cloud icon
  const icon = btn.querySelector('.run-play, .fa-cloud-upload-alt');
  const spin = btn.querySelector('.fa-spinner, .spin-hidden') || btn.querySelector('[id$="-spin"]');
  if (loading) {
    btn.classList.add('btn-loading');
    btn.disabled = true;
    if (icon) icon.style.display = 'none';
    if (spin) spin.style.display = 'inline-block';
  } else {
    btn.classList.remove('btn-loading');
    btn.disabled = !window.USER_IS_AUTHENTICATED;
    if (icon) icon.style.display = '';
    if (spin) spin.style.display = 'none';
  }
}

async function executeCode(mode) {
  if (!currentQuestion) return alert('Select a question first.');

  // spinner states
  setBtnLoading('run-btn', true);
  setBtnLoading('submit-btn', true);
  setBtnLoading('console-run-btn', true);
  setBtnLoading('console-submit-btn', true);
  document.getElementById('loading-overlay').style.display = 'flex';

  const payload = {
    code: getCode(),
    test_cases: mode === 'run' ? customCases : currentQuestion.metadata.test_cases,
    metadata: currentQuestion.metadata,
    mode,
    q_id: currentQuestion.q_id,
  };

  try {
    const res = await fetch('/practice/api/execute', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': window.CSRF_TOKEN ?? '',
      },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (mode === 'submit') {
      renderSubmitResult(data);
    } else {
      renderResult(data, mode);
      switchConsoleTab('result');
    }

    if (data.completed) {
      document.getElementById('completion-status').style.display = 'inline-flex';
      const sheet = document.getElementById('sheet-select').value;
      const qInfo = window.sheetsData?.[sheet]?.find(q => q.id === currentQuestion.q_id);
      if (qInfo) {
        qInfo.completed = true;
        const li = document.querySelector(`.q-item[data-qid="${currentQuestion.q_id}"] .q-check`);
        if (li) li.innerHTML = '<i class="fas fa-check"></i>';
      }
    }
  } catch (err) {
    console.error('execute failed', err);
    document.getElementById('result-display').innerHTML = `
      <div style="color:#ef4743;font-size:13px;padding:4px">
        <i class="fas fa-exclamation-circle"></i> Network error: ${esc(err.message)}
      </div>`;
    document.getElementById('result-display').classList.remove('result-empty');
    switchConsoleTab('result');
  } finally {
    document.getElementById('loading-overlay').style.display = 'none';
    ['run-btn','submit-btn','console-run-btn','console-submit-btn'].forEach(id => setBtnLoading(id, false));
  }
}

// wire buttons
document.getElementById('run-btn').addEventListener('click', () => executeCode('run'));
document.getElementById('submit-btn').addEventListener('click', () => executeCode('submit'));
document.getElementById('console-run-btn').addEventListener('click', () => executeCode('run'));
document.getElementById('console-submit-btn').addEventListener('click', () => executeCode('submit'));

// ================================================================
// RESULT RENDERING  (exact LeetCode result layout)
// ================================================================

function buildTestPanelHtml(r) {
  let html = '';
  // Input
  if (r.input != null) {
    html += `<div class="res-section"><div class="res-section-label">Input</div>`;
    if (Array.isArray(r.input) && currentQuestion && currentQuestion.param_names && currentQuestion.param_names.length === r.input.length) {
      currentQuestion.param_names.forEach((name, i) => {
        let valStr = JSON.stringify(r.input[i]);
        if (Array.isArray(r.input[i])) {
           valStr = valStr.replace(/,/g, ', '); // prettier arrays
        }
        html += `<div class="res-box" style="margin-bottom:8px;"><div style="color:var(--lc-t3);margin-bottom:4px;font-size:13px;font-family:var(--mono);">${esc(name)} =</div><div>${esc(valStr)}</div></div>`;
      });
    } else {
      html += `<div class="res-box">${esc(JSON.stringify(r.input).replace(/^\[|\]$/g,'').replace(/,/g,'\n'))}</div>`;
    }
    html += `</div>`;
  }
  
  // Output
  if (r.error) {
     html += `<div class="res-section"><div class="res-section-label">Error</div><div class="res-box fail-val">${esc(r.error)}</div></div>`;
  } else {
     const outCls = r.pass ? '' : 'fail-val';
     html += `<div class="res-section"><div class="res-section-label">Output</div><div class="res-box ${outCls}">${esc(JSON.stringify(r.actual))}</div></div>`;
  }

  // Expected
  if (r.expected !== undefined) {
     html += `<div class="res-section"><div class="res-section-label">Expected</div><div class="res-box ok-val">${esc(JSON.stringify(r.expected))}</div></div>`;
  }
  return html;
}

function renderSubmitResult(data) {
  const tabBtn = document.getElementById('desc-tab-submission');
  const tabText = document.getElementById('submission-tab-text');
  const panelContent = document.getElementById('submission-panel-content');
  
  if (!tabBtn || !panelContent) return;

  if (data.success === false || data.error) {
    tabText.textContent = "Error";
    tabBtn.style.color = '#ef4743';
    panelContent.innerHTML = `<div style="color:#ef4743;padding:20px"><i class="fas fa-exclamation-circle"></i> ${esc(data.error || 'Unknown error')}</div>`;
  } else {
    const ok = data.status === 'Accepted';
    tabText.textContent = ok ? 'Accepted' : 'Wrong Answer';
    tabBtn.style.color = ok ? 'var(--lc-green)' : '#ef4743';

    let html = `
      <div style="padding: 20px;">
        <div class="res-headline ${ok ? 'ok' : 'fail'}" style="margin-bottom: 24px;">
          ${esc(data.status)}
          <small>${data.passed} / ${data.total} testcases passed</small>
        </div>`;

    if (data.error_msg) {
      html += `
        <div class="res-section">
          <div class="res-section-label">Runtime Error</div>
          <div class="res-box fail-val">${esc(data.error_msg)}</div>
        </div>`;
    } else if (ok) {
      html += `
        <div style="display:flex;gap:24px;margin-top:16px;">
          <div style="background:#333;padding:16px;border-radius:var(--lc-r2);border:1px solid var(--lc-border);flex:1;">
            <div style="color:var(--lc-t3);font-size:13px;margin-bottom:8px;display:flex;align-items:center;gap:6px;">
               <i class="far fa-clock"></i> Runtime
            </div>
            <div style="font-size:24px;font-weight:600;color:var(--lc-t1);">${esc(data.runtime).replace(' ms', '')} <span style="font-size:14px;font-weight:400;">ms</span></div>
          </div>
          <div style="background:#333;padding:16px;border-radius:var(--lc-r2);border:1px solid var(--lc-border);flex:1;">
             <div style="color:var(--lc-t3);font-size:13px;margin-bottom:8px;display:flex;align-items:center;gap:6px;">
               <i class="fas fa-memory"></i> Memory
             </div>
             <div style="font-size:24px;font-weight:600;color:var(--lc-t1);">${esc(data.memory).replace(' MB', '')} <span style="font-size:14px;font-weight:400;">MB</span></div>
          </div>
        </div>
        <div style="margin-top: 16px; display: flex; justify-content: flex-end;">
          <button onclick="shareAsSolution()" class="sm-btn sm-btn-run" style="padding:6px 12px; background:var(--lc-green); color:#1a1a1a; font-weight:600; border:none; border-radius: 4px; display:flex; align-items:center; gap:6px;">
            <i class="fas fa-share-square"></i> Share as Solution
          </button>
        </div>`;
    } else {
      const failedTest = data.results.find(r => !r.pass);
      if (failedTest) {
        html += buildTestPanelHtml(failedTest);
      }
    }
    
    if (data.stdout) {
      html += `<div class="res-section" style="margin-top:20px;"><div class="res-section-label">Stdout</div><div class="res-box">${esc(data.stdout)}</div></div>`;
    }
    
    html += `</div>`;
    panelContent.innerHTML = html;
  }
  
  tabBtn.style.display = 'flex';
  switchDescTab('submission');
}

function renderResult(data, mode = 'run') {
  const container = document.getElementById('result-display');
  container.classList.remove('result-empty');
  
  if (data.success === false || data.error) {
    container.innerHTML = `
      <div style="color:#ef4743;font-size:13px;padding:4px">
        <i class="fas fa-exclamation-circle"></i> Error: ${esc(data.error || 'Unknown error occurred')}
      </div>`;
    return;
  }

  const ok = data.status === 'Accepted';

  let html = `
    <div class="result-wrap">
      <div class="res-headline ${ok ? 'ok' : 'fail'}" style="justify-content: space-between; display: flex;">
        <div style="display:flex;align-items:baseline;gap:8px">
          ${esc(data.status)}
          <small>${data.passed} / ${data.total} testcases passed</small>
        </div>
      </div>`;

  if (data.error_msg) {
    html += `<div class="res-section"><div class="res-section-label">Runtime Error</div><div class="res-box fail-val">${esc(data.error_msg)}</div></div></div>`;
    container.innerHTML = html;
    return;
  }

  if (data.results && data.results.length > 0) {
    // Generate tabs
    html += `<div class="tc-tabs">`;
    data.results.forEach((r, idx) => {
      const isOk = r.pass;
      const icon = isOk ? '<i class="fas fa-check"></i>' : '<i class="fas fa-times"></i>';
      const activeCls = idx === 0 ? 'active' : '';
      html += `<button class="tc-tab ${activeCls}" onclick="switchResultTab(${idx})">
        ${icon} Case ${idx + 1}
      </button>`;
    });
    html += `</div>`;

    // Generate content for each tab
    html += `<div id="tc-content-panels">`;
    data.results.forEach((r, idx) => {
      const display = idx === 0 ? 'block' : 'none';
      html += `<div class="tc-panel" id="tc-panel-${idx}" style="display: ${display};">`;
      html += buildTestPanelHtml(r);
      html += `</div>`;
    });
    html += `</div>`;
  }

  if (data.stdout) {
    html += `<div class="res-section"><div class="res-section-label">Stdout</div><div class="res-box">${esc(data.stdout)}</div></div>`;
  }

  html += '</div>';
  container.innerHTML = html;
}

window.switchResultTab = function(idx) {
  document.querySelectorAll('.tc-tab').forEach((el, i) => {
    if (i === idx) el.classList.add('active');
    else el.classList.remove('active');
  });
  document.querySelectorAll('.tc-panel').forEach((el, i) => {
    el.style.display = i === idx ? 'block' : 'none';
  });
}

// ================================================================
// SOLUTIONS AND SUBMISSIONS
// ================================================================

async function loadSubmissions() {
  if (!currentQuestion) return;
  const container = document.getElementById('submissions-list');
  container.innerHTML = '<div class="result-empty">Loading...</div>';
  try {
    const res = await fetch(`/practice/api/submissions/${currentQuestion.q_id}`);
    const data = await res.json();
    if (!data.submissions || data.submissions.length === 0) {
      container.innerHTML = '<div class="result-empty">No submissions yet.</div>';
      return;
    }
    let html = `
      <div style="margin-bottom:12px; display:flex; justify-content:flex-end;">
        <select id="sub-filter" onchange="renderFilteredSubmissions()" style="background:#222; border:1px solid var(--lc-border); color:var(--lc-t1); padding:4px 8px; border-radius:4px; font-size:13px;">
          <option value="All">All Statuses</option>
          <option value="Accepted">Accepted</option>
          <option value="Wrong Answer">Wrong Answer</option>
          <option value="Runtime Error">Runtime Error</option>
        </select>
      </div>
      <div id="submissions-list-container" style="display:flex;flex-direction:column;gap:12px;"></div>
      <div id="submission-detail-container" style="display:none;"></div>
    `;
    container.innerHTML = html;
    window.loadedSubmissions = data.submissions;
    renderFilteredSubmissions();
  } catch (err) {
    container.innerHTML = `<div class="result-empty" style="color:#ef4743">Failed to load submissions</div>`;
  }
}

window.renderFilteredSubmissions = function() {
  const container = document.getElementById('submissions-list-container');
  if (!container) return;
  const filter = document.getElementById('sub-filter')?.value || 'All';
  
  let html = '';
  window.loadedSubmissions.forEach((sub, i) => {
    if (filter !== 'All' && sub.status !== filter) return;
    
    const ok = sub.status === 'Accepted';
    const color = ok ? 'var(--lc-green)' : '#ef4743';
    const date = new Date(sub.timestamp).toLocaleString();
    html += `
      <div onclick="showSubmissionDetail(${i})" style="background:#333; padding:12px; border-radius:var(--lc-r2); border:1px solid var(--lc-border); display:flex; justify-content:space-between; align-items:center; cursor:pointer; transition:background 0.15s;" onmouseover="this.style.background='#444'" onmouseout="this.style.background='#333'">
        <div>
          <div style="color:${color}; font-weight:600; font-size:15px; margin-bottom:4px;">${esc(sub.status)}</div>
          <div style="color:var(--lc-t3); font-size:12px; display:flex; gap:8px; align-items:center;">
             <span style="background:#444; padding:2px 6px; border-radius:4px; font-size:11px;">${esc(sub.language || 'Python 3')}</span>
             <span>${date}</span>
          </div>
        </div>
        <div style="text-align:right;">
          <div style="color:var(--lc-t2); font-size:13px; margin-bottom:4px;">${sub.passed} / ${sub.total} testcases</div>
          <div style="color:var(--lc-t3); font-size:12px;"><i class="far fa-clock"></i> ${esc(sub.runtime)} &nbsp; <i class="fas fa-memory"></i> ${esc(sub.memory)}</div>
        </div>
      </div>
    `;
  });
  
  if (html === '') {
    html = `<div class="result-empty">No ${filter !== 'All' ? filter.toLowerCase() + ' ' : ''}submissions found.</div>`;
  }
  
  container.innerHTML = html;
}

window.showSubmissionDetail = function(idx) {
  const sub = window.loadedSubmissions[idx];
  if (!sub) return;

  const ok = sub.status === 'Accepted';
  const color = ok ? 'var(--lc-green)' : '#ef4743';
  const date = new Date(sub.timestamp).toLocaleString();

  const detailHtml = `
    <button onclick="hideSubmissionDetail()" style="background:none;border:none;color:var(--lc-t2);cursor:pointer;margin-bottom:16px;display:flex;align-items:center;gap:6px;font-size:14px;padding:0;"><i class="fas fa-arrow-left"></i> All Submissions</button>
    <div style="margin-bottom:20px;">
      <div style="color:${color}; font-size:20px; font-weight:600; margin-bottom:4px;">${esc(sub.status)}</div>
      <div style="color:var(--lc-t3); font-size:13px; display:flex; gap:16px;">
        <span><i class="far fa-calendar-alt"></i> ${date}</span>
        <span><i class="fas fa-tasks"></i> ${sub.passed} / ${sub.total} testcases</span>
      </div>
    </div>
    
    <div style="display:flex; gap:16px; margin-bottom:20px;">
      <div style="background:#333; padding:12px; border-radius:var(--lc-r2); border:1px solid var(--lc-border); flex:1;">
        <div style="color:var(--lc-t3); font-size:12px; margin-bottom:4px;"><i class="far fa-clock"></i> Runtime</div>
        <div style="color:var(--lc-t1); font-size:16px; font-weight:600; margin-bottom:4px;">${esc(sub.runtime)}</div>
        ${ok && sub.runtime_percentile !== undefined ? `<div style="font-size:12px; color:var(--lc-t2);">Beats <strong style="color:var(--lc-t1);">${sub.runtime_percentile}%</strong></div>` : ''}
      </div>
      <div style="background:#333; padding:12px; border-radius:var(--lc-r2); border:1px solid var(--lc-border); flex:1;">
        <div style="color:var(--lc-t3); font-size:12px; margin-bottom:4px;"><i class="fas fa-memory"></i> Memory</div>
        <div style="color:var(--lc-t1); font-size:16px; font-weight:600; margin-bottom:4px;">${esc(sub.memory)}</div>
        ${ok && sub.memory_percentile !== undefined ? `<div style="font-size:12px; color:var(--lc-t2);">Beats <strong style="color:var(--lc-t1);">${sub.memory_percentile}%</strong></div>` : ''}
      </div>
    </div>
    
    <div style="margin-bottom:20px; background:#333; padding:12px; border-radius:var(--lc-r2); border:1px solid var(--lc-border);">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <div style="font-weight:600; color:var(--lc-t2); font-size:13px;"><i class="fas fa-sticky-note"></i> Personal Note</div>
        <button onclick="saveSubmissionNote('${sub._id}', ${idx}, this)" class="sm-btn sm-btn-run" style="padding:2px 8px; font-size:11px;">Save Note</button>
      </div>
      <textarea id="submission-note-${idx}" placeholder="Add a note (e.g. O(n) approach using hashmap)" style="width:100%; height:60px; padding:8px; background:#222; border:1px solid var(--lc-border); color:var(--lc-t1); border-radius:4px; font-family:var(--font-sans); font-size:13px; resize:vertical;">${esc(sub.note || '')}</textarea>
    </div>
    
    <div style="display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:8px;">
      <div style="font-weight:600; color:var(--lc-t2); font-size:13px;">Submitted Code:</div>
      <div style="display:flex; gap:8px;">
        ${ok ? `<button onclick="shareSubmissionAsSolution(${idx})" class="sm-btn" style="padding:4px 8px; font-size:12px; background:var(--lc-green); color:#1a1a1a; border:none; font-weight:600;"><i class="fas fa-share-square"></i> Share</button>` : ''}
        <button onclick="restoreCode(${idx})" class="sm-btn" style="padding:4px 8px; font-size:12px; background:transparent; border:1px solid var(--lc-border);"><i class="fas fa-undo"></i> Restore Editor</button>
        <button onclick="copySubmissionCode(${idx}, this)" class="sm-btn" style="padding:4px 8px; font-size:12px; background:transparent; border:1px solid var(--lc-border);"><i class="far fa-copy"></i> Copy</button>
      </div>
    </div>
    <div id="sub-readonly-editor-${idx}" style="background:#1e1e1e; border-radius:var(--lc-r2); font-family:var(--mono); font-size:13px; color:var(--lc-t1); padding:16px; border:1px solid var(--lc-border); overflow-x:auto;"></div>
  `;

  document.getElementById('submissions-list-container').style.display = 'none';
  const detailContainer = document.getElementById('submission-detail-container');
  detailContainer.innerHTML = detailHtml;
  detailContainer.style.display = 'block';

  // Apply Monaco syntax highlighting if available
  const codeContainer = document.getElementById(`sub-readonly-editor-${idx}`);
  if (window.monaco) {
    monaco.editor.colorize(sub.code, 'python', { theme: 'vs-dark' }).then(colored => {
      codeContainer.innerHTML = colored;
    });
  } else {
    codeContainer.innerHTML = `<pre style="margin:0;"><code>${esc(sub.code)}</code></pre>`;
  }
}

window.restoreCode = function(idx) {
  const sub = window.loadedSubmissions[idx];
  if (!sub) return;
  if (typeof editor !== 'undefined' && editor) {
    editor.setValue(sub.code);
  } else {
    document.getElementById('plain-editor').value = sub.code;
  }
  hideSubmissionDetail();
}

window.copySubmissionCode = function(idx, btnEl) {
  const sub = window.loadedSubmissions[idx];
  if (!sub) return;
  navigator.clipboard.writeText(sub.code).then(() => {
    const originalHtml = btnEl.innerHTML;
    btnEl.innerHTML = '<i class="fas fa-check"></i> Copied!';
    setTimeout(() => { btnEl.innerHTML = originalHtml; }, 2000);
  });
}

window.saveSubmissionNote = async function(subId, idx, btnEl) {
  const sub = window.loadedSubmissions[idx];
  if (!sub) return;
  const textarea = document.getElementById(`submission-note-${idx}`);
  const newNote = textarea.value.trim();
  
  const originalHtml = btnEl.innerHTML;
  btnEl.innerHTML = 'Saving...';
  
  try {
    const res = await fetch(`/practice/api/submissions/${subId}/note`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': window.CSRF_TOKEN ?? ''
      },
      body: JSON.stringify({ note: newNote })
    });
    const data = await res.json();
    if (data.success) {
      sub.note = newNote; // Update local cache
      btnEl.innerHTML = '<i class="fas fa-check"></i> Saved';
      setTimeout(() => { btnEl.innerHTML = originalHtml; }, 2000);
    } else {
      btnEl.innerHTML = originalHtml;
      console.error("Failed to save note: " + (data.error || 'Unknown error'));
    }
  } catch(err) {
    btnEl.innerHTML = originalHtml;
    console.error("Network error while saving note.");
  }
}

window.hideSubmissionDetail = function() {
  document.getElementById('submission-detail-container').style.display = 'none';
  document.getElementById('submissions-list-container').style.display = 'flex';
}

async function loadSolutions() {
  if (!currentQuestion) return;
  const container = document.getElementById('solutions-list');
  container.innerHTML = '<div class="result-empty">Loading...</div>';
  try {
    const res = await fetch(`/practice/api/solutions/${currentQuestion.q_id}`);
    const data = await res.json();
    if (!data.solutions || data.solutions.length === 0) {
      container.innerHTML = '<div class="result-empty">No solutions posted yet. Be the first!</div>';
      return;
    }
    window.loadedSolutions = data.solutions;
    
    let html = '<div id="solutions-list-container" style="display:flex;flex-direction:column;gap:1px;background:var(--lc-border);border:1px solid var(--lc-border);border-radius:var(--lc-r2);overflow:hidden;">';
    
    data.solutions.forEach((sol, i) => {
      const date = new Date(sol.timestamp);
      const now = new Date();
      const diffMs = now - date;
      const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
      let timeAgo = diffHrs < 24 ? `${diffHrs} hours ago` : `${Math.floor(diffHrs/24)} days ago`;
      if (diffHrs === 0) timeAgo = 'Just now';

      let tagsHtml = (sol.tags || ["Python 3"]).map(t => `<span style="background:#444; padding:2px 8px; border-radius:12px; font-size:11px; color:var(--lc-t2);">${esc(t)}</span>`).join('');
      
      const upStyle = sol.user_vote === 'up' ? 'color:var(--lc-green)' : 'color:var(--lc-t2)';
      const downStyle = sol.user_vote === 'down' ? 'color:#ef4743' : 'color:var(--lc-t2)';

      html += `
        <div style="background:#222; padding:16px; cursor:pointer; transition:background 0.15s;" onmouseover="this.style.background='#333'" onmouseout="this.style.background='#222'" onclick="showSolutionDetail(${i})">
          <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
            <div style="width:24px; height:24px; border-radius:50%; background:var(--lc-border); display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:bold;">${esc(sol.author_name.charAt(0).toUpperCase())}</div>
            <div style="font-size:13px; color:var(--lc-t2);">${esc(sol.author_name)} <span style="opacity:0.5">• ${timeAgo}</span></div>
          </div>
          <div style="color:var(--lc-t1); font-weight:600; font-size:15px; margin-bottom:8px;">${esc(sol.title)}</div>
          <div style="display:flex; gap:6px; margin-bottom:12px; flex-wrap:wrap;">
            ${tagsHtml}
          </div>
          <div style="display:flex; gap:16px; font-size:13px; color:var(--lc-t2); align-items:center;">
            <div style="display:flex; align-items:center; gap:4px; ${upStyle}"><i class="fas fa-arrow-up"></i> ${sol.upvote_count || 0}</div>
            <div style="display:flex; align-items:center; gap:4px; ${downStyle}"><i class="fas fa-arrow-down"></i></div>
            <div style="display:flex; align-items:center; gap:4px;"><i class="far fa-eye"></i> ${sol.views || 0}</div>
          </div>
        </div>
      `;
    });
    html += '</div>';
    html += '<div id="solution-detail-container" style="display:none;"></div>';
    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<div class="result-empty" style="color:#ef4743">Failed to load solutions</div>`;
  }
}

window.showSolutionDetail = function(idx) {
  const sol = window.loadedSolutions[idx];
  if (!sol) return;

  // Hit view endpoint in background
  fetch(`/practice/api/solutions/${sol._id}/view`, { method: 'POST', headers: { 'X-CSRFToken': window.CSRF_TOKEN ?? '' }});
  
  const date = new Date(sol.timestamp).toLocaleString();
  let tagsHtml = (sol.tags || ["Python 3"]).map(t => `<span style="background:#444; padding:2px 8px; border-radius:12px; font-size:11px; color:var(--lc-t2);">${esc(t)}</span>`).join('');

  const upStyle = sol.user_vote === 'up' ? 'color:var(--lc-green)' : 'color:var(--lc-t2)';
  const downStyle = sol.user_vote === 'down' ? 'color:#ef4743' : 'color:var(--lc-t2)';

  const detailHtml = `
    <button onclick="hideSolutionDetail()" style="background:none;border:none;color:var(--lc-t2);cursor:pointer;margin-bottom:16px;display:flex;align-items:center;gap:6px;font-size:14px;padding:0;"><i class="fas fa-arrow-left"></i> All Solutions</button>
    <div style="margin-bottom:20px;">
      <div style="color:var(--lc-t1); font-size:20px; font-weight:600; margin-bottom:8px;">${esc(sol.title)}</div>
      <div style="display:flex; align-items:center; gap:8px; margin-bottom:12px;">
        <div style="width:32px; height:32px; border-radius:50%; background:var(--lc-border); display:flex; align-items:center; justify-content:center; font-size:14px; font-weight:bold;">${esc(sol.author_name.charAt(0).toUpperCase())}</div>
        <div style="font-size:14px; color:var(--lc-t2);">${esc(sol.author_name)} <br> <span style="font-size:12px; opacity:0.6;">${date}</span></div>
      </div>
      <div style="display:flex; gap:6px; margin-bottom:16px; flex-wrap:wrap;">
        ${tagsHtml}
      </div>
      <div style="display:flex; gap:16px; font-size:14px; color:var(--lc-t2); align-items:center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--lc-border);">
        <div style="display:flex; align-items:center; gap:6px; cursor:pointer; ${upStyle}" onclick="voteSolutionDetail('${sol._id}', 'up', ${idx})"><i class="fas fa-arrow-up"></i> <span>${sol.upvote_count || 0}</span></div>
        <div style="display:flex; align-items:center; gap:6px; cursor:pointer; ${downStyle}" onclick="voteSolutionDetail('${sol._id}', 'down', ${idx})"><i class="fas fa-arrow-down"></i> <span>${sol.downvote_count || 0}</span></div>
        <div style="display:flex; align-items:center; gap:6px;"><i class="far fa-eye"></i> ${sol.views + 1}</div>
      </div>
      ${sol.description ? `<div style="color:var(--lc-t1); font-size:14px; margin-bottom:24px; line-height:1.6; white-space:pre-wrap;">${esc(sol.description)}</div>` : ''}
      <div style="font-weight:600; color:var(--lc-t2); font-size:13px; margin-bottom:8px;">Code:</div>
      <div id="sol-readonly-editor-${idx}" style="background:#1e1e1e; border-radius:var(--lc-r2); font-family:var(--mono); font-size:13px; color:var(--lc-t1); padding:16px; border:1px solid var(--lc-border); overflow-x:auto;"></div>
    </div>
  `;

  document.getElementById('solutions-list-container').style.display = 'none';
  const detailContainer = document.getElementById('solution-detail-container');
  detailContainer.innerHTML = detailHtml;
  detailContainer.style.display = 'block';

  const codeContainer = document.getElementById(`sol-readonly-editor-${idx}`);
  if (window.monaco) {
    monaco.editor.colorize(sol.code, 'python', { theme: 'vs-dark' }).then(colored => {
      codeContainer.innerHTML = colored;
    });
  } else {
    codeContainer.innerHTML = `<pre style="margin:0;"><code>${esc(sol.code)}</code></pre>`;
  }
}

window.hideSolutionDetail = function() {
  document.getElementById('solution-detail-container').style.display = 'none';
  document.getElementById('solutions-list-container').style.display = 'flex';
  loadSolutions(); // Reload to refresh view count and votes
}

window.voteSolutionDetail = async function(solId, action, idx) {
  try {
    const res = await fetch(`/practice/api/solutions/${solId}/vote`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.CSRF_TOKEN ?? '' },
      body: JSON.stringify({ action })
    });
    const data = await res.json();
    if (data.success) {
      // update loaded data
      window.loadedSolutions[idx].upvote_count = data.upvotes;
      window.loadedSolutions[idx].downvote_count = data.downvotes;
      window.loadedSolutions[idx].user_vote = data.user_vote;
      
      // refresh detail view
      showSolutionDetail(idx);
    }
  } catch(e) {}
}

window.shareAsSolution = function() {
  window.pendingSolutionCode = getCode();
  switchDescTab('solutions');
  document.getElementById('post-solution-form').style.display = 'block';
  document.getElementById('solution-title').focus();
};

window.shareSubmissionAsSolution = function(idx) {
  const sub = window.loadedSubmissions[idx];
  if (!sub) return;
  window.pendingSolutionCode = sub.code;
  switchDescTab('solutions');
  document.getElementById('post-solution-form').style.display = 'block';
  document.getElementById('solution-title').focus();
};

// solution form UI
document.getElementById('post-solution-btn')?.addEventListener('click', () => {
  window.pendingSolutionCode = null; // Explicitly use current editor code
  document.getElementById('post-solution-form').style.display = 'block';
  document.getElementById('solution-title').focus();
});
document.getElementById('cancel-solution-btn')?.addEventListener('click', () => {
  document.getElementById('post-solution-form').style.display = 'none';
  document.getElementById('solution-title').value = '';
  document.getElementById('solution-tags').value = '';
  document.getElementById('solution-desc').value = '';
  window.pendingSolutionCode = null;
});
document.getElementById('submit-solution-btn')?.addEventListener('click', async () => {
  if (!currentQuestion) return;
  const title = document.getElementById('solution-title').value.trim();
  const desc = document.getElementById('solution-desc').value.trim();
  const tagsStr = document.getElementById('solution-tags').value.trim();
  const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(Boolean) : [];
  const code = window.pendingSolutionCode || getCode();
  
  if (!title) return alert("Please enter a title");
  if (!code) return alert("Code cannot be empty");
  
  const btn = document.getElementById('submit-solution-btn');
  btn.disabled = true;
  btn.textContent = 'Posting...';
  
  try {
    const res = await fetch('/practice/api/solutions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': window.CSRF_TOKEN ?? ''
      },
      body: JSON.stringify({
        q_id: currentQuestion.q_id,
        title: title,
        description: desc,
        tags: tags,
        code: code
      })
    });
    const data = await res.json();
    if (data.success) {
      document.getElementById('post-solution-form').style.display = 'none';
      document.getElementById('solution-title').value = '';
      document.getElementById('solution-tags').value = '';
      document.getElementById('solution-desc').value = '';
      window.pendingSolutionCode = null;
      loadSolutions();
    } else {
      alert("Error: " + data.error);
    }
  } catch (err) {
    alert("Network error");
  } finally {
    btn.disabled = false;
    btn.textContent = 'Submit';
  }
});

function esc(s) {
  return String(s ?? '')
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}

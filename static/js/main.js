// ── State ─────────────────────────────────────────────────────────────
const state = {
  qResult:   null,
  imgResult: null,
  combined:  null,
  lang:      'en',
  t:         {},
  history:   JSON.parse(localStorage.getItem('dermascan_history') || '[]'),
  susScores: JSON.parse(localStorage.getItem('dermascan_sus') || '[]'),
};

const COLORS = { Dry:'#4f9cf9', Normal:'#5fa882', Oily:'#f59e0b', Combination:'#a78bfa' };
const EMOJI  = { Dry:'💧', Normal:'✨', Oily:'💫', Combination:'⚡' };

// ── Translations ───────────────────────────────────────────────────────
async function loadTranslations(lang) {
  try {
    const res = await fetch(`/api/translations/${lang}`);
    state.t = await res.json();
    applyTranslations();
  } catch(e) { console.error('Translation load failed', e); }
}

function applyTranslations() {
  const t = state.t;
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    if (!t[key]) return;

    // For button elements preserve inner HTML structure
    if (el.tagName === 'BUTTON' && el.querySelector('strong')) return;

    // Update text
    el.textContent = t[key];

    // For radio option spans — also update the parent label's input value
    // so questionnaire mapping still works
    const label = el.closest('label.option');
    if (label) {
      const input = label.querySelector('input[type=radio]');
      if (input) {
        // Map Thai key back to English value for scoring
        const engMap = {
          'q1a1':'Very tight and uncomfortable','q1a2':'Slightly tight',
          'q1a3':'Comfortable and balanced','q1a4':'Fine, no particular feeling',
          'q2a1':'Very shiny all over','q2a2':'Shiny only on T-zone',
          'q2a3':'Same as morning','q2a4':'Feels drier and tighter',
          'q3a1':'Frequently, all over face','q3a2':'Occasionally, mainly T-zone',
          'q3a3':'Rarely','q3a4':'Almost never, but skin is flaky',
          'q4a1':'Very dry, flaky or itchy','q4a2':'Slightly dry in some areas',
          'q4a3':'Normal, no issues','q4a4':'Gets oily quickly',
          'q5a1':'Large and visible especially on nose','q5a2':'Visible only on T-zone',
          'q5a3':'Small and barely visible','q5a4':'Very small, skin looks tight',
          'q6a1':'Often irritated or red','q6a2':'Sometimes breaks out',
          'q6a3':'Rarely reacts','q6a4':'Absorbs quickly, needs more',
          'q7a1':'Rough, flaky or tight','q7a2':'Smooth some areas, oily others',
          'q7a3':'Smooth and balanced overall','q7a4':'Consistently shiny and greasy',
          'q8a1':'Lots of oil all over','q8a2':'Oil mainly from T-zone',
          'q8a3':'Very little oil','q8a4':'Almost nothing, skin is dry',
        };
        // Keep English value so MAPPINGS scoring always works
        if (engMap[key]) input.value = engMap[key];
      }
    }
  });
  document.documentElement.lang = state.lang;
}

function initLang() {
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      state.lang = btn.dataset.lang;
      document.querySelectorAll('.lang-btn').forEach(b => b.classList.toggle('active', b.dataset.lang === state.lang));
      await loadTranslations(state.lang);
    });
  });
  loadTranslations('en');
}

// ── Scroll ─────────────────────────────────────────────────────────────
function scrollToTabs() {
  document.getElementById('tabs-section').scrollIntoView({ behavior:'smooth' });
}

// ── Tab switching ──────────────────────────────────────────────────────
function initTabs() {
  const tabs     = document.querySelectorAll('.tab');
  const navLinks = document.querySelectorAll('.nav-link');

  function switchTab(name) {
    tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === name));
    navLinks.forEach(l => l.classList.toggle('active', l.dataset.tab === name));
    document.querySelectorAll('.tab-content').forEach(c => {
      c.classList.toggle('active', c.id === `tab-${name}`);
    });
    if (name === 'compare') renderCompare();
    if (name === 'history') renderHistory();
  }

  tabs.forEach(t => t.addEventListener('click', () => switchTab(t.dataset.tab)));
  navLinks.forEach(l => l.addEventListener('click', e => {
    e.preventDefault();
    switchTab(l.dataset.tab);
    document.getElementById('tabs-section').scrollIntoView({ behavior:'smooth' });
  }));
}

// ── Questionnaire ──────────────────────────────────────────────────────
function initQuestionnaire() {
  const form      = document.getElementById('quiz-form');
  const submitBtn = document.getElementById('quiz-submit');
  const note      = document.getElementById('submit-note');
  const bar       = document.getElementById('progress-bar');
  const label     = document.getElementById('progress-label');
  const total     = 8;

  form.addEventListener('change', () => {
    let answered = 0;
    for (let i = 0; i < total; i++) {
      if (form.querySelector(`input[name="q${i}"]:checked`)) {
        answered++;
        form.querySelector(`[data-q="${i}"]`).classList.add('answered');
      }
    }
    bar.style.width   = Math.round(answered / total * 100) + '%';
    label.textContent = `${answered} / ${total} answered`;
    submitBtn.disabled = answered < total;
    note.textContent = answered === total
      ? 'Ready! Click to see your result.'
      : `${total - answered} question(s) remaining`;
  });

  form.addEventListener('submit', async e => {
    e.preventDefault();
    const answers = [];
    for (let i = 0; i < total; i++) {
      const checked = form.querySelector(`input[name="q${i}"]:checked`);
      answers.push(checked ? checked.value : '');
    }
    submitBtn.disabled  = true;
    submitBtn.textContent = 'Analyzing…';
    try {
      const res  = await fetch('/api/questionnaire', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ answers })
      });
      const data = await res.json();
      state.qResult = data;
      renderResult('quiz-result', data, state.t.result_method_quiz || 'Questionnaire Method');
      document.getElementById('step-q').querySelector('.step-status').textContent = '✓ Done';
      document.getElementById('step-q').querySelector('.step-status').classList.add('done');
      // Auto-compute combined if image result exists
      if (state.imgResult) computeCombined();
    } catch(err) { alert('Analysis failed. Please try again.'); }
    finally {
      submitBtn.disabled = false;
      submitBtn.textContent = state.t.btn_analyze || 'Analyze My Skin Type →';
    }
  });
}

// ── Image Upload ───────────────────────────────────────────────────────
function initImageUpload() {
  const area       = document.getElementById('upload-area');
  const input      = document.getElementById('img-input');
  const preview    = document.getElementById('img-preview');
  const previewImg = document.getElementById('preview-img');
  const changeBtn  = document.getElementById('change-img');
  const submitBtn  = document.getElementById('img-submit');
  let selectedFile = null;

  area.addEventListener('click',  () => input.click());
  changeBtn.addEventListener('click', () => input.click());
  area.addEventListener('dragover',  e => { e.preventDefault(); area.classList.add('drag-over'); });
  area.addEventListener('dragleave', () => area.classList.remove('drag-over'));
  area.addEventListener('drop', e => {
    e.preventDefault(); area.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  });
  input.addEventListener('change', () => { if (input.files[0]) handleFile(input.files[0]); });

  function handleFile(file) {
    if (!file.type.startsWith('image/')) { alert('Please upload an image file.'); return; }
    selectedFile = file;
    previewImg.src = URL.createObjectURL(file);
    area.classList.add('hidden');
    preview.classList.remove('hidden');
    submitBtn.disabled = false;
  }

  submitBtn.addEventListener('click', async () => {
    if (!selectedFile) return;
    const resultDiv = document.getElementById('img-result');
    resultDiv.innerHTML = `<div class="spinner-wrap"><div class="spinner"></div><p style="color:var(--text-soft)">Analyzing your skin…</p></div>`;
    resultDiv.classList.remove('hidden');
    submitBtn.disabled   = true;
    submitBtn.textContent = 'Analyzing…';

    const formData = new FormData();
    formData.append('image', selectedFile);

    try {
      const [typeRes, condRes] = await Promise.all([
        fetch('/api/analyze-image', { method:'POST', body: formData }),
        (async () => { const fd = new FormData(); fd.append('image', selectedFile); return fetch('/api/check-conditions', { method:'POST', body:fd }); })()
      ]);
      const data     = await typeRes.json();
      const condData = await condRes.json();

      if (data.error) {
        resultDiv.innerHTML = `<div style="text-align:center;padding:2rem"><p style="color:#c47a5a">⚠️ ${data.error}</p></div>`;
        return;
      }
      state.imgResult = data;
      renderResult('img-result', data, state.t.result_method_image || 'Image Analysis Method', data.features, condData);
      document.getElementById('step-i').querySelector('.step-status').textContent = '✓ Done';
      document.getElementById('step-i').querySelector('.step-status').classList.add('done');
      // Auto-compute combined if questionnaire done
      if (state.qResult) computeCombined();
    } catch(err) {
      resultDiv.innerHTML = `<div style="text-align:center;padding:2rem"><p style="color:#c47a5a">⚠️ Connection error. Please try again.</p></div>`;
    } finally {
      submitBtn.disabled   = false;
      submitBtn.textContent = state.t.btn_analyze_img || 'Analyze Image →';
    }
  });
}

// ── Combined Result ────────────────────────────────────────────────────
async function computeCombined() {
  if (!state.qResult || !state.imgResult) return;
  try {
    const res  = await fetch('/api/combined-result', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ q_result: state.qResult, img_result: state.imgResult })
    });
    state.combined = await res.json();
  } catch(e) { console.error('Combined result error', e); }
}

// ── Condition Box ──────────────────────────────────────────────────────
function renderConditions(condData) {
  if (!condData || !condData.conditions) return '';
  const t = state.t;
  const condMap = {
    normal:     { label: t.condition_normal || 'No major concerns detected',   icon:'✅' },
    acne:       { label: t.condition_acne   || 'Possible acne detected',        icon:'⚠️' },
    redness:    { label: t.condition_redness|| 'Redness / irritation detected', icon:'🔴' },
    dark_spots: { label: t.condition_dark   || 'Dark spots detected',           icon:'🟤' },
  };
  const items = condData.conditions.map(cond => {
    const info     = condMap[cond] || { label: cond, icon:'◈' };
    const severity = condData.severity?.[cond] || (cond === 'normal' ? 'clear' : 'mild');
    return `<div class="condition-item ${cond==='normal'?'clear':'detected'}">
      <span class="condition-name">${info.icon} ${info.label}</span>
      <span class="condition-badge ${severity}">${severity.charAt(0).toUpperCase()+severity.slice(1)}</span>
    </div>`;
  }).join('');
  return `<div class="condition-box">
    <div class="condition-title">🔬 ${t.condition_title||'Skin Condition Analysis'}</div>
    <div class="condition-items">${items}</div>
  </div>`;
}

// ── Skincare Section ───────────────────────────────────────────────────
function renderSkincareSection(info, skinType, color) {
  const t = state.t;
  const productCategories = Object.entries(info.products || {});

  const morningSteps = (info.morning_routine||[]).map(s=>`
    <div class="routine-step">
      <div class="step-num" style="color:${color}">${s.step}</div>
      <div class="step-body"><div class="step-name">${s.name}</div><div class="step-desc">${s.desc}</div></div>
    </div>`).join('');

  const eveningSteps = (info.evening_routine||[]).map(s=>`
    <div class="routine-step">
      <div class="step-num" style="color:${color}">${s.step}</div>
      <div class="step-body"><div class="step-name">${s.name}</div><div class="step-desc">${s.desc}</div></div>
    </div>`).join('');

  const productsHtml = productCategories.map(([cat,data])=>`
    <div class="product-card">
      <div class="product-cat" style="color:${color}">${cat}</div>
      <p class="product-advice">${data.advice}</p>
      <div class="ingredients-row">
        <div class="ing-label">✓ Key Ingredients</div>
        <div class="ing-tags">${(data.key_ingredients||[]).map(i=>`<span class="tag tag-good">${i}</span>`).join('')}</div>
      </div>
      <div class="brand-list">
        ${(data.brands||[]).map(b=>`<div class="brand-item"><div class="brand-name">◈ ${b.name}</div><div class="brand-why">${b.why}</div></div>`).join('')}
      </div>
    </div>`).join('');

  const loveTags  = (info.ingredients_love ||[]).map(i=>`<span class="tag tag-good">${i}</span>`).join('');
  const avoidTags = (info.ingredients_avoid||[]).map(i=>`<span class="tag tag-bad">${i}</span>`).join('');

  return `<div class="skincare-section">
    <h3 class="skincare-title">🌅 ${t.morning_routine||'Morning Routine'}</h3>
    <div class="routine-steps">${morningSteps}</div>
    <h3 class="skincare-title">🌙 ${t.evening_routine||'Evening Routine'}</h3>
    <div class="routine-steps">${eveningSteps}</div>
    <h3 class="skincare-title">🛍️ ${t.products||'Product Recommendations'}</h3>
    <div class="products-grid">${productsHtml}</div>
    <h3 class="skincare-title">🔬 ${t.ingredients||'Ingredient Guide'}</h3>
    <div class="ingredient-guide">
      <div class="ing-section"><div class="ing-section-title">✅ ${t.look_for||'Look For'}</div><div class="ing-tags">${loveTags}</div></div>
      <div class="ing-section"><div class="ing-section-title">❌ ${t.avoid_label||'Avoid'}</div><div class="ing-tags">${avoidTags}</div></div>
    </div>
  </div>`;
}

// ── Render Result ──────────────────────────────────────────────────────
function renderResult(containerId, data, method, features=null, condData=null) {
  const container = document.getElementById(containerId);
  const { skin_type, percentages, confidence, info } = data;
  const color = COLORS[skin_type] || '#5fa882';
  const emoji = EMOJI[skin_type]  || '◈';
  const t     = state.t;

  const scoresHtml = Object.entries(percentages)
    .sort((a,b) => b[1]-a[1])
    .map(([type,pct]) => `
      <div class="score-item">
        <div class="score-label">${type}</div>
        <div class="score-val">${pct}%</div>
        <div class="score-bar-wrap"><div class="score-fill" style="width:${pct}%;background:${COLORS[type]||'#5fa882'}"></div></div>
      </div>`).join('');

  const charsHtml   = (info.characteristics||[]).map(c=>`<li>${c}</li>`).join('');
  const morningHtml = (info.morning_routine ||[]).map(s=>`<li><strong>${s.name}</strong> — ${s.desc}</li>`).join('');

  let featuresHtml = '';
  if (features) {
    const faceIcon = features.face_detected
      ? '<span class="face-badge detected">✓ Face Detected</span>'
      : '<span class="face-badge not-detected">⚠ No Face Detected</span>';
    featuresHtml = `<div style="margin-bottom:1.5rem">
      <h4 style="font-size:0.78rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--accent2);margin-bottom:0.8rem">Image Features</h4>
      ${faceIcon}
      <div class="features-grid" style="margin-top:0.8rem">
        <div class="feature-item"><span class="feature-label">Brightness</span><span class="feature-val">${features.brightness}/255</span></div>
        <div class="feature-item"><span class="feature-label">Saturation</span><span class="feature-val">${features.saturation}/255</span></div>
        <div class="feature-item"><span class="feature-label">Texture Score</span><span class="feature-val">${features.texture}</span></div>
        <div class="feature-item"><span class="feature-label">Zone Difference</span><span class="feature-val">${features.zone_diff}</span></div>
      </div>
    </div>`;
  }

  const conditionsHtml = condData ? renderConditions(condData) : '';
  const skincareHtml   = renderSkincareSection(info, skin_type, color);

  container.innerHTML = `
    <div class="result-hero" style="--result-color:${color}">
      <div class="result-emoji">${emoji}</div>
      <div class="result-type"><span style="color:${color}">${skin_type}</span> Skin</div>
      <div class="result-conf">${method} · ${confidence}% ${t.confidence||'confidence'}</div>
      <div class="result-desc">${info.description||''}</div>
    </div>
    <div class="scores-grid">${scoresHtml}</div>
    ${featuresHtml}${conditionsHtml}
    <div class="info-grid">
      <div class="info-card"><h4>Characteristics</h4><ul class="info-list">${charsHtml}</ul></div>
      <div class="info-card"><h4>Morning Routine (Quick View)</h4><ul class="info-list">${morningHtml}</ul></div>
      <div class="avoid-card"><strong>⚠ Avoid:</strong> ${info.avoid||''}</div>
    </div>
    ${skincareHtml}
    <div style="text-align:center;margin-top:2rem;display:flex;justify-content:center;gap:1rem;flex-wrap:wrap">
      <button class="export-btn" onclick="exportPDF('${skin_type}','${method}',${confidence})">
        📄 ${t.btn_export||'Download PDF Report'}
      </button>
      <button class="save-btn" id="save-btn-${containerId}" onclick="saveResult('${containerId}','${skin_type}',${confidence},'${method}')">
        💾 ${t.save_result||'Save This Result'}
      </button>
    </div>`;
  container.classList.remove('hidden');
  container.scrollIntoView({ behavior:'smooth', block:'start' });
}

// ── PDF Export ─────────────────────────────────────────────────────────
async function exportPDF(skinType, method, confidence) {
  const data = skinType === state.qResult?.skin_type ? state.qResult : state.imgResult;
  if (!data) return;
  try {
    const res  = await fetch('/api/export-pdf', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ skin_type:skinType, method, confidence, percentages:data.percentages, lang:state.lang })
    });
    const html = await res.text();
    const win  = window.open('', '_blank');
    win.document.write(html);
    win.document.close();
    setTimeout(() => win.print(), 800);
  } catch(e) { alert('PDF export failed. Please try again.'); }
}

// ── Save Result ────────────────────────────────────────────────────────
function saveResult(containerId, skinType, confidence, method) {
  const entry = {
    id: Date.now(), skin_type:skinType, confidence,
    method, date: new Date().toLocaleDateString(),
    time: new Date().toLocaleTimeString()
  };
  state.history.unshift(entry);
  if (state.history.length > 20) state.history.pop();
  localStorage.setItem('dermascan_history', JSON.stringify(state.history));

  const btn = document.getElementById(`save-btn-${containerId}`);
  if (btn) {
    btn.textContent = `✅ ${state.t.saved||'Result saved!'}`;
    btn.classList.add('saved');
    setTimeout(() => {
      btn.textContent = `💾 ${state.t.save_result||'Save This Result'}`;
      btn.classList.remove('saved');
    }, 2000);
  }
}

// ── History ────────────────────────────────────────────────────────────
function renderHistory() {
  const empty = document.getElementById('history-empty');
  const list  = document.getElementById('history-list');
  const t     = state.t;
  if (!state.history.length) { empty.style.display='block'; list.innerHTML=''; return; }
  empty.style.display = 'none';
  const counts = { Dry:0, Normal:0, Oily:0, Combination:0 };
  state.history.forEach(h => { if (counts[h.skin_type]!==undefined) counts[h.skin_type]++; });
  const maxCount = Math.max(...Object.values(counts), 1);
  const chartBars = Object.entries(counts).map(([type,count]) =>
    `<div class="chart-bar-wrap">
      <div class="chart-bar" style="height:${Math.round(count/maxCount*80)+4}px;background:${COLORS[type]}"></div>
      <div class="chart-label">${EMOJI[type]} ${type}<br/>${count}x</div>
    </div>`).join('');
  const items = state.history.map(h =>
    `<div class="history-item">
      <div class="history-emoji">${EMOJI[h.skin_type]||'◈'}</div>
      <div class="history-info">
        <div class="history-type">${h.skin_type} Skin</div>
        <div class="history-meta">${h.date} · ${h.time} · ${h.method}</div>
        <div class="history-conf">${h.confidence}% ${t.confidence||'confidence'}</div>
      </div>
      <button class="history-delete" onclick="deleteHistory(${h.id})">✕</button>
    </div>`).join('');
  list.innerHTML = `
    <div class="history-chart"><h4>📊 Skin Type Distribution</h4><div class="chart-bars">${chartBars}</div></div>
    <div class="history-list" style="margin-top:1.5rem">${items}</div>`;
}

function deleteHistory(id) {
  state.history = state.history.filter(h => h.id !== id);
  localStorage.setItem('dermascan_history', JSON.stringify(state.history));
  renderHistory();
}

// ── Compare with Combined Result ───────────────────────────────────────
function renderCompare() {
  const container = document.getElementById('compare-content');
  if (!state.qResult || !state.imgResult) return;

  const q   = state.qResult;
  const img = state.imgResult;
  const t   = state.t;

  const mkScores = (pcts) => Object.entries(pcts).sort((a,b)=>b[1]-a[1])
    .map(([type,pct]) =>
      `<div style="display:flex;justify-content:space-between;font-size:0.82rem;padding:0.3rem 0;border-bottom:1px solid var(--border)">
        <span style="color:var(--text-soft)">${type}</span>
        <span style="color:${COLORS[type]};font-weight:500">${pct}%</span>
      </div>`).join('');

  // Combined result card
  let combinedHtml = '';
  if (state.combined) {
    const c     = state.combined;
    const color = COLORS[c.skin_type] || '#5fa882';
    const agree = c.agree;
    combinedHtml = `
      <div class="combined-result-box" style="background:${color}">
        <div style="font-size:0.75rem;text-transform:uppercase;letter-spacing:0.1em;color:rgba(255,255,255,0.7);margin-bottom:0.4rem">
          Combined Result (Q×60% + IMG×40%)
        </div>
        <div class="combined-type">${EMOJI[c.skin_type]||''} ${c.skin_type} Skin</div>
        <div class="combined-conf">Combined confidence: ${c.confidence}%</div>
        <span class="agree-badge ${agree?'agree':'differ'}">
          ${agree ? '✅ Both methods agree' : '⚠ Methods differ — questionnaire is primary'}
        </span>
        <div class="formula-line">Score = 0.60 × Questionnaire + 0.40 × Image Analysis</div>
      </div>`;
  } else {
    combinedHtml = `
      <div style="text-align:center;padding:1.5rem;background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);margin-bottom:1.5rem">
        <div class="spinner" style="margin:0 auto 0.8rem"></div>
        <p style="color:var(--text-soft);font-size:0.88rem">Computing combined result…</p>
      </div>`;
    computeCombined().then(() => { if(state.combined) renderCompare(); });
  }

  // Agree/differ banner
  const agree = state.combined?.agree ?? (q.skin_type === img.skin_type);
  const agreeBanner = agree
    ? `<div class="agree-banner agree">✅ Both methods agree: <strong>${q.skin_type} Skin</strong></div>`
    : `<div class="agree-banner differ">⚠ Methods differ — Questionnaire: <strong>${q.skin_type}</strong> · Image: <strong>${img.skin_type}</strong><br/><small>Questionnaire weighted higher (60%) — more reliable primary result.</small></div>`;

  const final = state.combined?.skin_type || q.skin_type;
  const info  = (state.combined?.info) || q.info || {};
  const charsHtml   = (info.characteristics||[]).map(c=>`<li>${c}</li>`).join('');
  const routineHtml = (info.morning_routine||[]).map(s=>`<li><strong>${s.name}</strong> — ${s.desc}</li>`).join('');

  container.innerHTML = `
    ${combinedHtml}
    ${agreeBanner}

    <div class="compare-grid">
      <div class="compare-card" style="--card-color:${COLORS[q.skin_type]}">
        <div class="c-method">📝 ${t.result_method_quiz||'Questionnaire'} <span style="color:var(--accent2);font-size:0.72rem">(60% weight)</span></div>
        <div class="c-emoji">${EMOJI[q.skin_type]}</div>
        <div class="c-type">${q.skin_type} Skin</div>
        <div class="c-conf">${t.confidence||'Confidence'}: ${q.confidence}%</div>
        <div>${mkScores(q.percentages)}</div>
      </div>
      <div class="compare-card" style="--card-color:${COLORS[img.skin_type]}">
        <div class="c-method">📸 ${t.result_method_image||'Image Analysis'} <span style="color:var(--accent2);font-size:0.72rem">(40% weight)</span></div>
        <div class="c-emoji">${EMOJI[img.skin_type]}</div>
        <div class="c-type">${img.skin_type} Skin</div>
        <div class="c-conf">${t.confidence||'Confidence'}: ${img.confidence}%</div>
        <div>${mkScores(img.percentages)}</div>
      </div>
    </div>

    <div class="final-section">
      <h3>🎯 Final Recommendation — ${final} Skin</h3>
      <div class="info-grid">
        <div class="info-card"><h4>Your Skin Characteristics</h4><ul class="info-list">${charsHtml}</ul></div>
        <div class="info-card"><h4>Morning Routine</h4><ul class="info-list">${routineHtml}</ul></div>
        <div class="avoid-card"><strong>⚠ Avoid:</strong> ${info.avoid||''}</div>
      </div>
    </div>
    <p style="text-align:center;font-size:0.76rem;color:var(--text-soft);margin-top:2rem">
      ⚕️ For medical skin concerns, consult a licensed dermatologist.
    </p>`;
}

// ── SUS Survey ─────────────────────────────────────────────────────────
function initSUS() {
  const form      = document.getElementById('sus-form');
  const submitBtn = document.getElementById('sus-submit');
  const note      = document.getElementById('sus-note');
  const total     = 10;

  form.addEventListener('change', () => {
    let answered = 0;
    for (let i = 0; i < total; i++) {
      if (form.querySelector(`input[name="sq${i}"]:checked`)) {
        answered++;
        form.querySelector(`[data-q="${i}"]`).classList.add('answered');
      }
    }
    submitBtn.disabled = answered < total;
    note.textContent = answered === total
      ? 'Ready! Click to calculate your SUS score.'
      : `${total - answered} question(s) remaining`;
  });

  form.addEventListener('submit', async e => {
    e.preventDefault();
    const answers = [];
    for (let i = 0; i < total; i++) {
      const checked = form.querySelector(`input[name="sq${i}"]:checked`);
      answers.push(checked ? parseInt(checked.value) : 3);
    }
    submitBtn.disabled   = true;
    submitBtn.textContent = 'Calculating…';

    try {
      const res  = await fetch('/api/sus-score', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ answers })
      });
      const data = await res.json();
      renderSUSResult(data, answers);

      // Save to localStorage for research data collection
      const entry = {
        id: Date.now(),
        sus_score: data.sus_score,
        grade: data.grade,
        date: new Date().toLocaleDateString(),
        answers
      };
      state.susScores.push(entry);
      localStorage.setItem('dermascan_sus', JSON.stringify(state.susScores));

    } catch(err) {
      alert('Failed to calculate score. Please try again.');
    } finally {
      submitBtn.disabled   = false;
      submitBtn.textContent = 'Calculate My SUS Score →';
    }
  });
}

function renderSUSResult(data, answers) {
  const resultDiv = document.getElementById('sus-result');
  const { sus_score, grade, grade_color } = data;

  // Grade scale display
  const grades = [
    { label:'Poor',            range:'0–51',   col:'#f87171' },
    { label:'Marginal',        range:'52–67',  col:'#fb923c' },
    { label:'Good',            range:'68–80',  col:'#f59e0b' },
    { label:'Excellent',       range:'81–90',  col:'#5fa882' },
    { label:'Best Imaginable', range:'91–100', col:'#3b82f6' },
  ];
  const scaleHtml = grades.map(g =>
    `<div class="sus-scale-item ${g.label===grade?'active':''}"
      style="color:${g.col};background:${g.label===grade?g.col+'22':'transparent'};border-color:${g.label===grade?g.col:'transparent'}">
      <strong>${g.label}</strong><br/><span style="font-size:0.7rem">${g.range}</span>
    </div>`).join('');

  // Individual answer breakdown
  const susLabels = [
    'Use frequently','Unnecessarily complex','Easy to use',
    'Need technical support','Functions well integrated','Too much inconsistency',
    'Most people learn quickly','Very cumbersome','Felt confident','Needed to learn a lot'
  ];
  const answersHtml = answers.map((a, i) => {
    const isPositive = i % 2 === 0;
    const contribution = isPositive ? (a - 1) * 2.5 : (5 - a) * 2.5;
    return `<div style="display:flex;align-items:center;gap:0.8rem;padding:0.5rem 0;border-bottom:1px solid var(--border)">
      <span style="font-size:0.75rem;color:var(--accent2);font-weight:600;min-width:28px">Q${i+1}</span>
      <span style="flex:1;font-size:0.82rem;color:var(--text-muted)">${susLabels[i]}</span>
      <span style="font-size:0.82rem;font-weight:600;color:var(--text);min-width:20px;text-align:center">${a}</span>
      <span style="font-size:0.75rem;color:${isPositive?'#5fa882':'#fb923c'};min-width:38px;text-align:right">+${contribution.toFixed(1)}</span>
    </div>`;
  }).join('');

  resultDiv.innerHTML = `
    <div class="sus-result-box">
      <p style="font-size:0.8rem;color:var(--text-soft);margin-bottom:0.5rem">Your SUS Score</p>
      <div class="sus-score-big" style="color:${grade_color}">${sus_score}</div>
      <div style="font-size:1rem;color:var(--text-soft);margin-bottom:0.8rem">out of 100</div>
      <span class="sus-grade" style="background:${grade_color}22;color:${grade_color};border:1px solid ${grade_color}44">
        ${grade}
      </span>
      <div class="sus-scale">${scaleHtml}</div>
      <p style="font-size:0.78rem;color:var(--text-soft);margin-top:0.5rem">
        Reference: Brooke, J. (1996). SUS: A quick and dirty usability scale.
      </p>
    </div>

    <div style="background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);padding:1.5rem;margin-bottom:1.5rem">
      <h4 style="font-size:0.85rem;color:var(--accent2);margin-bottom:0.8rem;text-transform:uppercase;letter-spacing:0.06em">Score Breakdown</h4>
      ${answersHtml}
      <div style="display:flex;justify-content:flex-end;padding-top:0.5rem;font-size:0.88rem;font-weight:600;color:var(--text)">
        Total: ${sus_score} / 100
      </div>
    </div>

    <div style="background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);padding:1.2rem;text-align:center">
      <p style="font-size:0.88rem;color:var(--text-muted);margin-bottom:0.5rem">
        Thank you for your feedback! Your response has been saved for research purposes.
      </p>
      <button class="btn-outline" onclick="document.getElementById('sus-form').reset(); document.getElementById('sus-result').classList.add('hidden'); document.querySelectorAll('.sus-card').forEach(c=>c.classList.remove('answered')); document.getElementById('sus-submit').disabled=true; document.getElementById('sus-note').textContent='Answer all 10 questions to calculate your score';">
        Submit Another Response
      </button>
    </div>`;

  resultDiv.classList.remove('hidden');
  resultDiv.scrollIntoView({ behavior:'smooth', block:'start' });
}

// Init handled by checkAuth callback below

// ── Auth ───────────────────────────────────────────────────────────────
async function checkAuth() {
  const res  = await fetch('/api/auth/me');
  const data = await res.json();
  if (!data.logged_in) {
    window.location.href = '/login';
    return null;
  }
  // Show user bar
  document.getElementById('user-bar').style.display = 'flex';
  document.getElementById('user-greeting').innerHTML =
    `Hello, <strong>${data.username}</strong>`;
  return data;
}

async function doLogout() {
  await fetch('/api/auth/logout', { method:'POST' });
  window.location.href = '/login';
}

// ── Verify Result Box ──────────────────────────────────────────────────
function renderVerifyBox(resultId, detectedType, containerId) {
  const skinTypes = ['Dry','Normal','Oily','Combination'];
  const optionsHtml = skinTypes.map(t =>
    `<option value="${t}" ${t===detectedType?'selected':''}>${t}</option>`
  ).join('');

  const box = document.createElement('div');
  box.className = 'verify-box';
  box.id = `verify-${resultId}`;
  box.innerHTML = `
    <p>Is this result correct for your skin type?</p>
    <div class="verify-opts">
      <button class="verify-yes-btn" onclick="submitVerify(${resultId},'${detectedType}',true,'${containerId}')">
        ✅ Yes, this is correct!
      </button>
      <div class="verify-type-wrap">
        <select class="verify-select" id="vsel-${resultId}">
          ${skinTypes.map(t=>`<option value="${t}">${t}</option>`).join('')}
        </select>
        <button class="verify-no-btn" onclick="submitVerifyNo(${resultId},'${containerId}')">
          No, my actual type is →
        </button>
      </div>
    </div>
    <p style="font-size:0.75rem;color:var(--text-soft);margin-top:0.8rem">
      Your feedback helps calculate the real accuracy of DermaScan.
    </p>`;

  const container = document.getElementById(containerId);
  // Remove old verify box if exists
  const old = container.querySelector('.verify-box');
  if (old) old.remove();
  container.appendChild(box);
}

async function submitVerify(resultId, verifiedType, isCorrect, containerId) {
  await fetch('/api/verify-result', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ result_id:resultId, verified_type:verifiedType, is_correct:isCorrect })
  });
  const box = document.getElementById(`verify-${resultId}`);
  box.innerHTML = `<div class="verify-done">✅ Thank you! Your feedback has been recorded for research.</div>`;
}

async function submitVerifyNo(resultId, containerId) {
  const sel         = document.getElementById(`vsel-${resultId}`);
  const actualType  = sel.value;
  await fetch('/api/verify-result', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ result_id:resultId, verified_type:actualType, is_correct:false })
  });
  const box = document.getElementById(`verify-${resultId}`);
  box.innerHTML = `<div class="verify-done">✅ Thank you! We recorded that your actual skin type is <strong>${actualType}</strong>.</div>`;
}

// Override renderResult to add verify box + check auth
const _origRenderResult = renderResult;
// Patch renderResult to append verify box after rendering
function renderResultWithVerify(containerId, data, method, features=null, condData=null) {
  renderResult(containerId, data, method, features, condData);
  if (data.result_id) {
    renderVerifyBox(data.result_id, data.skin_type, containerId);
  }
}

// Override questionnaire submit to use new function
document.addEventListener('DOMContentLoaded', () => {
  checkAuth().then(user => {
    if (!user) return;
    initLang();
    initTabs();
    initQuestionnairePatch();
    initImageUploadPatch();
    initSUS();
  });
});

function initQuestionnairePatch() {
  const form      = document.getElementById('quiz-form');
  const submitBtn = document.getElementById('quiz-submit');
  const note      = document.getElementById('submit-note');
  const bar       = document.getElementById('progress-bar');
  const label     = document.getElementById('progress-label');
  const total     = 8;

  form.addEventListener('change', () => {
    let answered = 0;
    for (let i=0; i<total; i++) {
      if (form.querySelector(`input[name="q${i}"]:checked`)) {
        answered++;
        form.querySelector(`[data-q="${i}"]`).classList.add('answered');
      }
    }
    bar.style.width   = Math.round(answered/total*100)+'%';
    label.textContent = `${answered} / ${total} answered`;
    submitBtn.disabled = answered < total;
    note.textContent   = answered===total ? 'Ready! Click to see your result.' : `${total-answered} question(s) remaining`;
  });

  form.addEventListener('submit', async e => {
    e.preventDefault();
    const answers = [];
    for (let i=0; i<total; i++) {
      const c = form.querySelector(`input[name="q${i}"]:checked`);
      answers.push(c ? c.value : '');
    }
    submitBtn.disabled   = true;
    submitBtn.textContent = 'Analyzing…';
    try {
      const res  = await fetch('/api/questionnaire', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({answers})
      });
      const data = await res.json();
      if (data.error === 'Login required') { window.location.href='/login'; return; }
      state.qResult = data;
      renderResultWithVerify('quiz-result', data, state.t.result_method_quiz||'Questionnaire Method');
      document.getElementById('step-q').querySelector('.step-status').textContent = '✓ Done';
      document.getElementById('step-q').querySelector('.step-status').classList.add('done');
      if (state.imgResult) computeCombined();
    } catch(err) { alert('Analysis failed. Please try again.'); }
    finally {
      submitBtn.disabled   = false;
      submitBtn.textContent = state.t.btn_analyze||'Analyze My Skin Type →';
    }
  });
}

function initImageUploadPatch() {
  const area       = document.getElementById('upload-area');
  const input      = document.getElementById('img-input');
  const preview    = document.getElementById('img-preview');
  const previewImg = document.getElementById('preview-img');
  const changeBtn  = document.getElementById('change-img');
  const submitBtn  = document.getElementById('img-submit');
  let selectedFile = null;

  area.addEventListener('click',  () => input.click());
  changeBtn.addEventListener('click', () => input.click());
  area.addEventListener('dragover',  e => { e.preventDefault(); area.classList.add('drag-over'); });
  area.addEventListener('dragleave', () => area.classList.remove('drag-over'));
  area.addEventListener('drop', e => {
    e.preventDefault(); area.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  });
  input.addEventListener('change', () => { if (input.files[0]) handleFile(input.files[0]); });

  function handleFile(file) {
    if (!file.type.startsWith('image/')) { alert('Please upload an image file.'); return; }
    selectedFile   = file;
    previewImg.src = URL.createObjectURL(file);
    area.classList.add('hidden');
    preview.classList.remove('hidden');
    submitBtn.disabled = false;
  }

  submitBtn.addEventListener('click', async () => {
    if (!selectedFile) return;
    const resultDiv = document.getElementById('img-result');
    resultDiv.innerHTML = `<div class="spinner-wrap"><div class="spinner"></div><p style="color:var(--text-soft)">Analyzing your skin…</p></div>`;
    resultDiv.classList.remove('hidden');
    submitBtn.disabled   = true;
    submitBtn.textContent = 'Analyzing…';
    const fd = new FormData();
    fd.append('image', selectedFile);
    try {
      const [typeRes, condRes] = await Promise.all([
        fetch('/api/analyze-image', {method:'POST', body:fd}),
        (async()=>{ const f2=new FormData(); f2.append('image',selectedFile); return fetch('/api/check-conditions',{method:'POST',body:f2}); })()
      ]);
      const data    = await typeRes.json();
      const condData= await condRes.json();
      if (data.error==='Login required') { window.location.href='/login'; return; }
      if (data.error) { resultDiv.innerHTML=`<div style="text-align:center;padding:2rem"><p style="color:#c47a5a">⚠️ ${data.error}</p></div>`; return; }
      state.imgResult = data;
      renderResultWithVerify('img-result', data, state.t.result_method_image||'Image Analysis Method', data.features, condData);
      document.getElementById('step-i').querySelector('.step-status').textContent = '✓ Done';
      document.getElementById('step-i').querySelector('.step-status').classList.add('done');
      if (state.qResult) computeCombined();
    } catch(err) {
      resultDiv.innerHTML=`<div style="text-align:center;padding:2rem"><p style="color:#c47a5a">⚠️ Connection error. Please try again.</p></div>`;
    } finally {
      submitBtn.disabled   = false;
      submitBtn.textContent = state.t.btn_analyze_img||'Analyze Image →';
    }
  });
}

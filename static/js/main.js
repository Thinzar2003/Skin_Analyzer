// ── State ─────────────────────────────────────────────────────────────
const state = {
  qResult:   null,
  imgResult: null,
  lang:      'en',
  t:         {},
  history:   JSON.parse(localStorage.getItem('dermascan_history') || '[]')
};

const COLORS = { Dry:'#4f9cf9', Normal:'#5fa882', Oily:'#f5a623', Combination:'#a78bfa' };
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
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    if (state.t[key]) el.textContent = state.t[key];
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
  document.getElementById('tabs-section').scrollIntoView({ behavior: 'smooth' });
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
    document.getElementById('tabs-section').scrollIntoView({ behavior: 'smooth' });
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
      const checked = form.querySelector(`input[name="q${i}"]:checked`);
      if (checked) {
        answered++;
        form.querySelector(`[data-q="${i}"]`).classList.add('answered');
      }
    }
    const pct = Math.round(answered / total * 100);
    bar.style.width   = pct + '%';
    label.textContent = `${answered} / ${total} answered`;
    submitBtn.disabled = answered < total;
    note.textContent = answered === total ? 'Ready! Click to see your result.' : `${total - answered} question(s) remaining`;
  });

  form.addEventListener('submit', async e => {
    e.preventDefault();
    const answers = [];
    for (let i = 0; i < total; i++) {
      const checked = form.querySelector(`input[name="q${i}"]:checked`);
      answers.push(checked ? checked.value : '');
    }
    submitBtn.disabled = true;
    submitBtn.textContent = 'Analyzing…';
    try {
      const res  = await fetch('/api/questionnaire', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers })
      });
      const data = await res.json();
      state.qResult = data;
      renderResult('quiz-result', data, state.t.result_method_quiz || 'Questionnaire Method');
      document.getElementById('step-q').querySelector('.step-status').textContent = '✓ Done';
      document.getElementById('step-q').querySelector('.step-status').classList.add('done');
    } catch (err) {
      alert('Analysis failed. Please try again.');
    } finally {
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

  area.addEventListener('click', () => input.click());
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
    submitBtn.disabled = true;
    submitBtn.textContent = 'Analyzing…';

    const formData = new FormData();
    formData.append('image', selectedFile);

    try {
      // Run skin type analysis + condition check in parallel
      const [typeRes, condRes] = await Promise.all([
        fetch('/api/analyze-image', { method: 'POST', body: formData }),
        (async () => { const fd = new FormData(); fd.append('image', selectedFile); return fetch('/api/check-conditions', { method:'POST', body: fd }); })()
      ]);

      const data      = await typeRes.json();
      const condData  = await condRes.json();

      if (data.error) {
        resultDiv.innerHTML = `<div style="text-align:center;padding:2rem"><p style="color:#c47a5a">⚠️ ${data.error}</p></div>`;
        return;
      }

      state.imgResult = data;
      renderResult('img-result', data, state.t.result_method_image || 'Image Analysis Method', data.features, condData);
      document.getElementById('step-i').querySelector('.step-status').textContent = '✓ Done';
      document.getElementById('step-i').querySelector('.step-status').classList.add('done');
    } catch (err) {
      resultDiv.innerHTML = `<div style="text-align:center;padding:2rem"><p style="color:#c47a5a">⚠️ Connection error. Please try again.</p></div>`;
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = state.t.btn_analyze_img || 'Analyze Image →';
    }
  });
}

// ── Skin Condition Box ─────────────────────────────────────────────────
function renderConditions(condData) {
  if (!condData || !condData.conditions) return '';
  const t = state.t;
  const condMap = {
    normal:     { label: t.condition_normal || 'No major concerns detected',    icon: '✅' },
    acne:       { label: t.condition_acne   || 'Possible acne detected',         icon: '⚠️' },
    redness:    { label: t.condition_redness|| 'Redness / irritation detected',  icon: '🔴' },
    dark_spots: { label: t.condition_dark   || 'Dark spots detected',            icon: '🟤' },
  };

  const items = condData.conditions.map(cond => {
    const info     = condMap[cond] || { label: cond, icon: '◈' };
    const severity = condData.severity?.[cond] || (cond === 'normal' ? 'clear' : 'mild');
    return `
      <div class="condition-item ${cond === 'normal' ? 'clear' : 'detected'}">
        <span class="condition-name">${info.icon} ${info.label}</span>
        <span class="condition-badge ${severity}">${severity.charAt(0).toUpperCase() + severity.slice(1)}</span>
      </div>`;
  }).join('');

  return `
    <div class="condition-box">
      <div class="condition-title">🔬 ${t.condition_title || 'Skin Condition Analysis'}</div>
      <div class="condition-items">${items}</div>
    </div>`;
}

// ── Skincare Section ───────────────────────────────────────────────────
function renderSkincareSection(info, skinType, color) {
  const t = state.t;
  const productCategories = Object.entries(info.products || {});

  const morningSteps = (info.morning_routine || []).map(s => `
    <div class="routine-step">
      <div class="step-num" style="color:${color}">${s.step}</div>
      <div class="step-body">
        <div class="step-name">${s.name}</div>
        <div class="step-desc">${s.desc}</div>
      </div>
    </div>`).join('');

  const eveningSteps = (info.evening_routine || []).map(s => `
    <div class="routine-step">
      <div class="step-num" style="color:${color}">${s.step}</div>
      <div class="step-body">
        <div class="step-name">${s.name}</div>
        <div class="step-desc">${s.desc}</div>
      </div>
    </div>`).join('');

  const productsHtml = productCategories.map(([cat, data]) => `
    <div class="product-card">
      <div class="product-cat" style="color:${color}">${cat}</div>
      <p class="product-advice">${data.advice}</p>
      <div class="ingredients-row">
        <div class="ing-label">✓ Key Ingredients</div>
        <div class="ing-tags">${(data.key_ingredients||[]).map(i=>`<span class="tag tag-good">${i}</span>`).join('')}</div>
      </div>
      <div class="brand-list">
        ${(data.brands||[]).map(b=>`
          <div class="brand-item">
            <div class="brand-name">◈ ${b.name}</div>
            <div class="brand-why">${b.why}</div>
          </div>`).join('')}
      </div>
    </div>`).join('');

  const loveTags  = (info.ingredients_love  ||[]).map(i=>`<span class="tag tag-good">${i}</span>`).join('');
  const avoidTags = (info.ingredients_avoid ||[]).map(i=>`<span class="tag tag-bad">${i}</span>`).join('');

  return `
    <div class="skincare-section">
      <h3 class="skincare-title">🌅 ${t.morning_routine || 'Morning Routine'}</h3>
      <div class="routine-steps">${morningSteps}</div>

      <h3 class="skincare-title">🌙 ${t.evening_routine || 'Evening Routine'}</h3>
      <div class="routine-steps">${eveningSteps}</div>

      <h3 class="skincare-title">🛍️ ${t.products || 'Product Recommendations'}</h3>
      <div class="products-grid">${productsHtml}</div>

      <h3 class="skincare-title">🔬 ${t.ingredients || 'Ingredient Guide'}</h3>
      <div class="ingredient-guide">
        <div class="ing-section">
          <div class="ing-section-title">✅ ${t.look_for || 'Ingredients to Look For'}</div>
          <div class="ing-tags">${loveTags}</div>
        </div>
        <div class="ing-section">
          <div class="ing-section-title">❌ ${t.avoid_label || 'Ingredients to Avoid'}</div>
          <div class="ing-tags">${avoidTags}</div>
        </div>
      </div>
    </div>`;
}

// ── Render Result ──────────────────────────────────────────────────────
function renderResult(containerId, data, method, features = null, condData = null) {
  const container = document.getElementById(containerId);
  const { skin_type, percentages, confidence, info } = data;
  const color = COLORS[skin_type] || '#5fa882';
  const emoji = EMOJI[skin_type]  || '◈';
  const t     = state.t;

  const scoresHtml = Object.entries(percentages)
    .sort((a, b) => b[1] - a[1])
    .map(([type, pct]) => `
      <div class="score-item">
        <div class="score-label">${type}</div>
        <div class="score-val">${pct}%</div>
        <div class="score-bar-wrap">
          <div class="score-fill" style="width:${pct}%;background:${COLORS[type] || '#5fa882'}"></div>
        </div>
      </div>`).join('');

  const charsHtml   = (info.characteristics||[]).map(c => `<li>${c}</li>`).join('');
  const morningHtml = (info.morning_routine||[]).map(s => `<li><strong>${s.name}</strong> — ${s.desc}</li>`).join('');

  let featuresHtml = '';
  if (features) {
    const faceIcon = features.face_detected
      ? '<span class="face-badge detected">✓ Face Detected</span>'
      : '<span class="face-badge not-detected">⚠ No Face Detected</span>';
    featuresHtml = `
      <div style="margin-bottom:1.5rem">
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
      <div class="result-conf">${method} · ${confidence}% ${t.confidence || 'confidence'}</div>
      <div class="result-desc">${info.description || ''}</div>
    </div>

    <div class="scores-grid">${scoresHtml}</div>

    ${featuresHtml}
    ${conditionsHtml}

    <div class="info-grid">
      <div class="info-card">
        <h4>Characteristics</h4>
        <ul class="info-list">${charsHtml}</ul>
      </div>
      <div class="info-card">
        <h4>Morning Routine (Quick View)</h4>
        <ul class="info-list">${morningHtml}</ul>
      </div>
      <div class="avoid-card">
        <strong>⚠ Avoid:</strong> ${info.avoid || ''}
      </div>
    </div>

    ${skincareHtml}

    <div style="text-align:center;margin-top:2rem;display:flex;justify-content:center;gap:1rem;flex-wrap:wrap">
      <button class="export-btn" onclick="exportPDF('${skin_type}','${method}',${confidence})">
        📄 ${t.btn_export || 'Download PDF Report'}
      </button>
      <button class="save-btn" id="save-btn-${containerId}" onclick="saveResult('${containerId}','${skin_type}',${confidence},'${method}')">
        💾 ${t.save_result || 'Save This Result'}
      </button>
    </div>
  `;
  container.classList.remove('hidden');
  container.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── PDF Export ─────────────────────────────────────────────────────────
async function exportPDF(skinType, method, confidence) {
  const data  = skinType === (state.qResult?.skin_type) ? state.qResult : state.imgResult;
  if (!data) return;

  try {
    const res = await fetch('/api/export-pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        skin_type:   skinType,
        method:      method,
        confidence:  confidence,
        percentages: data.percentages,
        lang:        state.lang
      })
    });
    const html = await res.text();
    const win  = window.open('', '_blank');
    win.document.write(html);
    win.document.close();
    setTimeout(() => win.print(), 800);
  } catch(e) {
    alert('PDF export failed. Please try again.');
  }
}

// ── Save Result to History ─────────────────────────────────────────────
function saveResult(containerId, skinType, confidence, method) {
  const entry = {
    id:         Date.now(),
    skin_type:  skinType,
    confidence: confidence,
    method:     method,
    date:       new Date().toLocaleDateString(),
    time:       new Date().toLocaleTimeString()
  };
  state.history.unshift(entry);
  if (state.history.length > 20) state.history.pop();
  localStorage.setItem('dermascan_history', JSON.stringify(state.history));

  const btn = document.getElementById(`save-btn-${containerId}`);
  if (btn) {
    btn.textContent = `✅ ${state.t.saved || 'Result saved!'}`;
    btn.classList.add('saved');
    setTimeout(() => {
      btn.textContent = `💾 ${state.t.save_result || 'Save This Result'}`;
      btn.classList.remove('saved');
    }, 2000);
  }
}

// ── Render History ─────────────────────────────────────────────────────
function renderHistory() {
  const empty   = document.getElementById('history-empty');
  const list    = document.getElementById('history-list');
  const t       = state.t;

  if (!state.history.length) {
    empty.style.display = 'block';
    list.innerHTML = '';
    return;
  }
  empty.style.display = 'none';

  // Count skin types for chart
  const counts = { Dry:0, Normal:0, Oily:0, Combination:0 };
  state.history.forEach(h => { if (counts[h.skin_type] !== undefined) counts[h.skin_type]++; });
  const maxCount = Math.max(...Object.values(counts), 1);

  const chartBars = Object.entries(counts).map(([type, count]) => `
    <div class="chart-bar-wrap">
      <div class="chart-bar" style="height:${Math.round(count/maxCount*80)+4}px;background:${COLORS[type]}"></div>
      <div class="chart-label">${EMOJI[type]} ${type}<br/>${count}x</div>
    </div>`).join('');

  const items = state.history.map(h => `
    <div class="history-item">
      <div class="history-emoji">${EMOJI[h.skin_type] || '◈'}</div>
      <div class="history-info">
        <div class="history-type">${h.skin_type} Skin</div>
        <div class="history-meta">${h.date} · ${h.time} · ${h.method}</div>
        <div class="history-conf">${h.confidence}% ${t.confidence || 'confidence'}</div>
      </div>
      <button class="history-delete" onclick="deleteHistory(${h.id})">✕</button>
    </div>`).join('');

  list.innerHTML = `
    <div class="history-chart">
      <h4>📊 Skin Type Distribution</h4>
      <div class="chart-bars">${chartBars}</div>
    </div>
    <div class="history-list" style="margin-top:1.5rem">${items}</div>`;
}

function deleteHistory(id) {
  state.history = state.history.filter(h => h.id !== id);
  localStorage.setItem('dermascan_history', JSON.stringify(state.history));
  renderHistory();
}

// ── Compare ────────────────────────────────────────────────────────────
function renderCompare() {
  const container = document.getElementById('compare-content');
  if (!state.qResult || !state.imgResult) return;

  const q     = state.qResult;
  const img   = state.imgResult;
  const agree = q.skin_type === img.skin_type;
  const t     = state.t;

  const agreeBanner = agree
    ? `<div class="agree-banner agree">✅ Both methods agree: <strong>${q.skin_type} Skin</strong> — High confidence result!</div>`
    : `<div class="agree-banner differ">⚠ Methods disagree — Questionnaire: <strong>${q.skin_type}</strong> · Image: <strong>${img.skin_type}</strong><br/><small>The questionnaire is generally more reliable as your primary result.</small></div>`;

  const mkScores = (pcts) => Object.entries(pcts).sort((a,b)=>b[1]-a[1])
    .map(([type,pct]) => `<div style="display:flex;justify-content:space-between;font-size:0.82rem;padding:0.3rem 0;border-bottom:1px solid var(--border)"><span style="color:var(--text-soft)">${type}</span><span style="color:${COLORS[type]};font-weight:500">${pct}%</span></div>`).join('');

  const final = q.skin_type;
  const info  = q.info;
  const charsHtml   = (info.characteristics||[]).map(c=>`<li>${c}</li>`).join('');
  const routineHtml = (info.morning_routine||[]).map(s=>`<li><strong>${s.name}</strong> — ${s.desc}</li>`).join('');

  container.innerHTML = `
    ${agreeBanner}
    <div class="compare-grid">
      <div class="compare-card" style="--card-color:${COLORS[q.skin_type]}">
        <div class="c-method">📝 ${t.result_method_quiz || 'Questionnaire'}</div>
        <div class="c-emoji">${EMOJI[q.skin_type]}</div>
        <div class="c-type">${q.skin_type} Skin</div>
        <div class="c-conf">${t.confidence || 'Confidence'}: ${q.confidence}%</div>
        <div>${mkScores(q.percentages)}</div>
      </div>
      <div class="compare-card" style="--card-color:${COLORS[img.skin_type]}">
        <div class="c-method">📸 ${t.result_method_image || 'Image Analysis'}</div>
        <div class="c-emoji">${EMOJI[img.skin_type]}</div>
        <div class="c-type">${img.skin_type} Skin</div>
        <div class="c-conf">${t.confidence || 'Confidence'}: ${img.confidence}%</div>
        <div>${mkScores(img.percentages)}</div>
      </div>
    </div>
    <div class="final-section">
      <h3>🎯 Final Recommendation — ${final} Skin</h3>
      <div class="info-grid">
        <div class="info-card">
          <h4>Your Skin Characteristics</h4>
          <ul class="info-list">${charsHtml}</ul>
        </div>
        <div class="info-card">
          <h4>Morning Routine</h4>
          <ul class="info-list">${routineHtml}</ul>
        </div>
        <div class="avoid-card">
          <strong>⚠ Avoid:</strong> ${info.avoid || ''}
        </div>
      </div>
    </div>
    <p style="text-align:center;font-size:0.76rem;color:var(--text-soft);margin-top:2rem">
      ⚕️ For medical skin concerns, consult a licensed dermatologist.
    </p>`;
}

// ── Init ───────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initLang();
  initTabs();
  initQuestionnaire();
  initImageUpload();
});

// ── State ─────────────────────────────────────────────────────────────
const state = { qResult: null, imgResult: null };

const COLORS = {
  Dry: '#4f9cf9', Normal: '#34c985', Oily: '#f5a623', Combination: '#a78bfa'
};
const EMOJI = {
  Dry: '💧', Normal: '✨', Oily: '💫', Combination: '⚡'
};

// ── Scroll to tabs ───────────────────────────────────────────────────
function scrollToTabs() {
  document.getElementById('tabs-section').scrollIntoView({ behavior: 'smooth' });
}

// ── Tab switching ────────────────────────────────────────────────────
function initTabs() {
  const tabs    = document.querySelectorAll('.tab');
  const navLinks= document.querySelectorAll('.nav-link');

  function switchTab(name) {
    tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === name));
    navLinks.forEach(l => l.classList.toggle('active', l.dataset.tab === name));
    document.querySelectorAll('.tab-content').forEach(c => {
      c.classList.toggle('active', c.id === `tab-${name}`);
    });
    if (name === 'compare') renderCompare();
  }

  tabs.forEach(t => t.addEventListener('click', () => switchTab(t.dataset.tab)));
  navLinks.forEach(l => l.addEventListener('click', e => {
    e.preventDefault();
    switchTab(l.dataset.tab);
    document.getElementById('tabs-section').scrollIntoView({ behavior: 'smooth' });
  }));
}

// ── Questionnaire ────────────────────────────────────────────────────
function initQuestionnaire() {
  const form     = document.getElementById('quiz-form');
  const submitBtn= document.getElementById('quiz-submit');
  const note     = document.getElementById('submit-note');
  const bar      = document.getElementById('progress-bar');
  const label    = document.getElementById('progress-label');
  const total    = 8;

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
    if (answered === total) note.textContent = 'Ready! Click to see your result.';
    else note.textContent = `${total - answered} question${total - answered > 1 ? 's' : ''} remaining`;
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
      renderResult('quiz-result', data, 'Questionnaire Method');
      document.getElementById('step-q').querySelector('.step-status').textContent = '✓ Done';
      document.getElementById('step-q').querySelector('.step-status').classList.add('done');
      updateComparePlaceholder();
    } catch (err) {
      alert('Analysis failed. Please try again.');
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Analyze My Skin Type →';
    }
  });
}

// ── Image Upload ─────────────────────────────────────────────────────
function initImageUpload() {
  const area     = document.getElementById('upload-area');
  const input    = document.getElementById('img-input');
  const preview  = document.getElementById('img-preview');
  const previewImg= document.getElementById('preview-img');
  const changeBtn= document.getElementById('change-img');
  const submitBtn= document.getElementById('img-submit');
  let   selectedFile = null;

  area.addEventListener('click', () => input.click());
  changeBtn.addEventListener('click', () => { input.click(); });

  area.addEventListener('dragover', e => { e.preventDefault(); area.classList.add('drag-over'); });
  area.addEventListener('dragleave', () => area.classList.remove('drag-over'));
  area.addEventListener('drop', e => {
    e.preventDefault();
    area.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  });

  input.addEventListener('change', () => {
    if (input.files[0]) handleFile(input.files[0]);
  });

  function handleFile(file) {
    if (!file.type.startsWith('image/')) { alert('Please upload an image file.'); return; }
    selectedFile = file;
    const url = URL.createObjectURL(file);
    previewImg.src = url;
    area.classList.add('hidden');
    preview.classList.remove('hidden');
    submitBtn.disabled = false;
  }

  submitBtn.addEventListener('click', async () => {
    if (!selectedFile) return;
    const resultDiv = document.getElementById('img-result');
    resultDiv.innerHTML = `<div class="spinner-wrap"><div class="spinner"></div><p style="color:var(--text-muted)">Analyzing your skin…</p></div>`;
    resultDiv.classList.remove('hidden');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Analyzing…';

    const formData = new FormData();
    formData.append('image', selectedFile);

    try {
      const res  = await fetch('/api/analyze-image', { method: 'POST', body: formData });
      const data = await res.json();
      if (data.error) {
        resultDiv.innerHTML = `<div style="text-align:center;padding:2rem">
          <p style="color:#f5a623;font-size:1rem;margin-bottom:0.5rem">⚠️ ${data.error}</p>
          <p style="color:var(--text-muted);font-size:0.85rem">Please try a different image (JPG/PNG, clear face photo)</p>
        </div>`;
        return;
      }
      state.imgResult = data;
      renderResult('img-result', data, 'Image Analysis Method', data.features);
      document.getElementById('step-i').querySelector('.step-status').textContent = '✓ Done';
      document.getElementById('step-i').querySelector('.step-status').classList.add('done');
      updateComparePlaceholder();
    } catch (err) {
      resultDiv.innerHTML = `<div style="text-align:center;padding:2rem">
        <p style="color:#f5a623;font-size:1rem;margin-bottom:0.5rem">⚠️ Connection error</p>
        <p style="color:var(--text-muted);font-size:0.85rem">Error: ${err.message}. Please try again.</p>
      </div>`;
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Analyze Image →';
    }
  });
}

// ── Render Result ────────────────────────────────────────────────────
function renderResult(containerId, data, method, features = null) {
  const container   = document.getElementById(containerId);
  const { skin_type, percentages, confidence, info } = data;
  const color = COLORS[skin_type];
  const emoji = EMOJI[skin_type];

  const scoresHtml = Object.entries(percentages)
    .sort((a, b) => b[1] - a[1])
    .map(([type, pct]) => `
      <div class="score-item">
        <div class="score-label">${type}</div>
        <div class="score-val">${pct}%</div>
        <div class="score-bar-wrap">
          <div class="score-fill" style="width:${pct}%;background:${COLORS[type]}"></div>
        </div>
      </div>
    `).join('');

  const charsHtml = info.characteristics.map(c => `<li>${c}</li>`).join('');
  const routineHtml = (info.morning_routine || []).map(s => `<li><strong>${s.name}</strong> — ${s.desc}</li>`).join('');

  let featuresHtml = '';
  if (features) {
    const faceStatus = features.face_detected
      ? '<span class="face-badge detected">✓ Face Detected</span>'
      : '<span class="face-badge not-detected">⚠ No Face Detected</span>';
    featuresHtml = `
      <div style="margin-bottom:1.5rem">
        <h4 style="font-size:0.8rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--accent);margin-bottom:0.8rem">Image Features</h4>
        ${faceStatus}
        <div class="features-grid" style="margin-top:0.8rem">
          <div class="feature-item"><span class="feature-label">Brightness</span><span class="feature-val">${features.brightness}/255</span></div>
          <div class="feature-item"><span class="feature-label">Saturation</span><span class="feature-val">${features.saturation}/255</span></div>
          <div class="feature-item"><span class="feature-label">Texture Score</span><span class="feature-val">${features.texture}</span></div>
          <div class="feature-item"><span class="feature-label">Zone Difference</span><span class="feature-val">${features.zone_diff}</span></div>
        </div>
      </div>
    `;
  }

  const skincareHtml = renderSkincareSection(info, skin_type, color);

  container.innerHTML = `
    <div class="result-hero" style="--result-color:${color}">
      <div class="result-emoji">${emoji}</div>
      <div class="result-type"><span>${skin_type}</span> Skin</div>
      <div class="result-conf">${method} · ${confidence}% confidence</div>
      <div class="result-desc">${info.description}</div>
    </div>

    <div class="scores-grid">${scoresHtml}</div>

    ${featuresHtml}

    <div class="info-grid">
      <div class="info-card">
        <h4>Characteristics</h4>
        <ul class="info-list">${charsHtml}</ul>
      </div>
      <div class="info-card">
        <h4>Recommended Routine</h4>
        <ul class="info-list">${routineHtml}</ul>
      </div>
      <div class="avoid-card">
        <strong>⚠ Avoid:</strong> ${info.avoid}
      </div>
    </div>

    ${skincareHtml}
  `;
  container.classList.remove('hidden');
  container.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── Compare ──────────────────────────────────────────────────────────
function updateComparePlaceholder() {
  if (state.qResult && state.imgResult) {
    document.querySelectorAll('.step-status').forEach(s => { s.textContent = '✓ Done'; s.classList.add('done'); });
  }
}

function renderCompare() {
  const container = document.getElementById('compare-content');
  if (!state.qResult || !state.imgResult) return;

  const q = state.qResult;
  const i = state.imgResult;
  const agree = q.skin_type === i.skin_type;

  const agreeBanner = agree
    ? `<div class="agree-banner agree">✅ Both methods agree: <strong>${q.skin_type} Skin</strong> — High confidence result!</div>`
    : `<div class="agree-banner differ">⚠ Methods disagree — Questionnaire: <strong>${q.skin_type}</strong> · Image: <strong>${i.skin_type}</strong><br/><small>The questionnaire is generally more reliable as your primary result.</small></div>`;

  const qScores = Object.entries(q.percentages).sort((a,b)=>b[1]-a[1]).map(([t,p]) => `<div style="display:flex;justify-content:space-between;font-size:0.85rem;padding:0.3rem 0;border-bottom:1px solid var(--border)"><span style="color:var(--text-muted)">${t}</span><span style="color:${COLORS[t]};font-weight:500">${p}%</span></div>`).join('');
  const iScores = Object.entries(i.percentages).sort((a,b)=>b[1]-a[1]).map(([t,p]) => `<div style="display:flex;justify-content:space-between;font-size:0.85rem;padding:0.3rem 0;border-bottom:1px solid var(--border)"><span style="color:var(--text-muted)">${t}</span><span style="color:${COLORS[t]};font-weight:500">${p}%</span></div>`).join('');

  const final = q.skin_type;
  const info  = q.info;
  const charsHtml   = info.characteristics.map(c => `<li>${c}</li>`).join('');
  const routineHtml = (info.morning_routine || []).map(s => `<li><strong>${s.name}</strong> — ${s.desc}</li>`).join('');

  container.innerHTML = `
    ${agreeBanner}

    <div class="compare-grid">
      <div class="compare-card" style="--card-color:${COLORS[q.skin_type]}">
        <div class="c-method">📝 Questionnaire Method</div>
        <div class="c-emoji">${EMOJI[q.skin_type]}</div>
        <div class="c-type">${q.skin_type} Skin</div>
        <div class="c-conf">Confidence: ${q.confidence}%</div>
        <div>${qScores}</div>
      </div>
      <div class="compare-card" style="--card-color:${COLORS[i.skin_type]}">
        <div class="c-method">📸 Image Analysis</div>
        <div class="c-emoji">${EMOJI[i.skin_type]}</div>
        <div class="c-type">${i.skin_type} Skin</div>
        <div class="c-conf">Confidence: ${i.confidence}%</div>
        <div>${iScores}</div>
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
          <h4>Your Skincare Routine</h4>
          <ul class="info-list">${routineHtml}</ul>
        </div>
        <div class="avoid-card">
          <strong>⚠ Avoid:</strong> ${info.avoid}
        </div>
      </div>
    </div>

    <p style="text-align:center;font-size:0.78rem;color:var(--text-muted);margin-top:2rem">
      ⚕️ For medical skin concerns, consult a licensed dermatologist.
    </p>
  `;
}

// ── Init ─────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initQuestionnaire();
  initImageUpload();
});

// ── Skincare Routine & Products Renderer ─────────────────────────────
function renderSkincareSection(info, skinType, color) {
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
        <div class="ing-group ing-love">
          <div class="ing-label">✓ Key Ingredients</div>
          <div class="ing-tags">${(data.key_ingredients||[]).map(i=>`<span class="tag tag-good">${i}</span>`).join('')}</div>
        </div>
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
      <h3 class="skincare-title" style="color:${color}">🌅 Morning Routine</h3>
      <div class="routine-steps">${morningSteps}</div>

      <h3 class="skincare-title" style="color:${color}">🌙 Evening Routine</h3>
      <div class="routine-steps">${eveningSteps}</div>

      <h3 class="skincare-title" style="color:${color}">🛍️ Product Recommendations</h3>
      <div class="products-grid">${productsHtml}</div>

      <h3 class="skincare-title" style="color:${color}">🔬 Ingredient Guide</h3>
      <div class="ingredient-guide">
        <div class="ing-section">
          <div class="ing-section-title">✅ Ingredients to Look For</div>
          <div class="ing-tags">${loveTags}</div>
        </div>
        <div class="ing-section">
          <div class="ing-section-title">❌ Ingredients to Avoid</div>
          <div class="ing-tags">${avoidTags}</div>
        </div>
      </div>
    </div>`;
}

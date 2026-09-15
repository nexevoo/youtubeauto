/* ════════════════════════════════════════════
   AI Video Studio — Live Monitor Logic
   ════════════════════════════════════════════ */

// ── DOM Refs ────────────────────────────────────────────────────────────────
const terminalBody   = document.getElementById('terminal-body');
const resultPreview  = document.getElementById('result-preview');
const statusLabel    = document.getElementById('status-label');
const statusDot      = document.querySelector('.status-dot');
const resultVideo    = document.getElementById('result-video');
const resultTitle    = document.getElementById('result-title');
const resultDesc     = document.getElementById('result-desc');
const resultTags     = document.getElementById('result-tags');
const galleryGrid    = document.getElementById('gallery-grid');
const galleryEmpty   = document.getElementById('gallery-empty');

// ── Tab Navigation ──────────────────────────────────────────────────────────
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`tab-${tab}`).classList.add('active');
    if (tab === 'gallery') loadGallery();
    if (tab === 'settings') loadCredentialsList();
  });
});

// ── Terminal Helper ─────────────────────────────────────────────────────────
function appendLog(message, cls = '') {
  const p = document.createElement('p');
  p.className = `terminal-line ${cls}`;
  // Timestamp prefix
  const ts = new Date().toLocaleTimeString('en-US', { hour12: false });
  p.innerHTML = `<span style="color:var(--text-dim)">[${ts}]</span> ${message}`;
  terminalBody.appendChild(p);
  terminalBody.scrollTop = terminalBody.scrollHeight;
}

function clearTerminal() {
  terminalBody.innerHTML = '';
}

// ── Pipeline UI ─────────────────────────────────────────────────────────────
function setStepState(stepNum, state) {
  const el = document.getElementById(`step-${stepNum}`);
  if (!el) return;
  el.classList.remove('running', 'done', 'error');
  if (state) el.classList.add(state);
  const statusEl = el.querySelector('.ps-status-icon') || el.querySelector('.step-status');
  if (statusEl) {
    if (state === 'running') statusEl.textContent = '⏳';
    else if (state === 'done') statusEl.textContent = '✅';
    else if (state === 'error') statusEl.textContent = '❌';
    else statusEl.textContent = '';
  }
}

function resetPipeline() {
  [1, 2, 3, 4, 5, 6].forEach(i => setStepState(i, null));
  clearTerminal();
  document.getElementById('script-box').style.display = 'none';
  resultPreview.style.display = 'none';
}

// ── Status Bar ──────────────────────────────────────────────────────────────
function setStatus(label, state = 'ready') {
  statusLabel.textContent = label;
  statusDot.className = 'status-dot';
  
  const btnAuto = document.getElementById('btn-auto-gen');
  const btnManual = document.getElementById('btn-manual-gen');

  if (state === 'busy') {
    statusDot.classList.add('busy');
    if (btnAuto) {
        btnAuto.disabled = true;
        btnAuto.style.opacity = '0.5';
        btnAuto.style.cursor = 'not-allowed';
    }
    if (btnManual) {
        btnManual.disabled = true;
        btnManual.style.opacity = '0.5';
        btnManual.style.cursor = 'not-allowed';
    }
  }
  
  if (state === 'ready' || state === 'error') {
    if (state === 'error') statusDot.classList.add('error');
    if (btnAuto) {
        btnAuto.disabled = false;
        btnAuto.style.opacity = '1';
        btnAuto.style.cursor = 'pointer';
    }
    if (btnManual) {
        btnManual.disabled = false;
        btnManual.style.opacity = '1';
        btnManual.style.cursor = 'pointer';
    }
  }
}

// ── SSE Live Stream ─────────────────────────────────────────────────────────
function connectLiveStream() {
  setStatus('Connecting...', 'busy');
  const evtSource = new EventSource('/api/stream');

  evtSource.addEventListener('init_state', (e) => {
    const state = JSON.parse(e.data);
    setStatus(state.status === 'idle' ? 'Sleeping' : 'Generating Live', state.status === 'running' ? 'busy' : 'ready');
    
    if (state.message) {
      appendLog(state.message, 'dim');
    }
    
    // Process history
    if (state.logs && state.logs.length > 0) {
      clearTerminal();
      state.logs.forEach(log => {
        handleProgressEvent(log.data, true);
      });
    }
  });

  function handleProgressEvent(data, isHistory = false) {
    const { step, status, message, script } = data;

    if (!isHistory) {
        setStatus(status === 'idle' ? 'Sleeping' : 'Generating Live', status === 'idle' ? 'ready' : 'busy');
    }

    if (step === 1 && status === 'running' && !isHistory) {
       // Reset for a new run
       resetPipeline();
    }

    // Update step indicators
    if (status === 'running') {
      // Mark previous steps done
      for (let i = 1; i < step; i++) setStepState(i, 'done');
      setStepState(step, 'running');
    } else if (status === 'done') {
      setStepState(step, 'done');
      
      // If script is done (Step 2), display it in the script box
      if (step === 2 && script) {
        document.getElementById('script-title-display').textContent = script.title;
        document.getElementById('script-desc-display').textContent = script.description;
        const scenesHtml = script.scenes.map((scene, idx) => `
          <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border)">
            <strong style="color:var(--accent); font-size: 0.8rem">Scene ${idx + 1} (${scene.visual_keywords})</strong>
            <p style="font-size: 0.85rem; margin-top: 4px; color: var(--text)">"${scene.narration}"</p>
          </div>
        `).join('');
        document.getElementById('script-scenes-display').innerHTML = scenesHtml;
        document.getElementById('script-box').style.display = 'block';
      }
    } else if (status === 'error') {
      setStepState(step, 'error');
    } else if (status === 'idle') {
      [1, 2, 3, 4, 5, 6, 7].forEach(i => setStepState(i, null));
    }

    // Log
    const cls = status === 'done' ? 'success' : '';
    if (!isHistory || status === 'running' || status === 'done' || status === 'idle') {
      appendLog(message, cls);
    }
  }

  evtSource.addEventListener('progress', (e) => {
    const data = JSON.parse(e.data);
    handleProgressEvent(data);
  });

  evtSource.addEventListener('complete', (e) => {
    const data = JSON.parse(e.data);
    [1, 2, 3, 4, 5, 6, 7].forEach(i => setStepState(i, 'done'));
    
    // Update Step 7's description dynamically based on upload success/failure
    const step7Desc = document.querySelector('#step-7 .ps-desc');
    if (step7Desc) step7Desc.textContent = data.message;
    
    appendLog(data.message, 'success');
    appendLog(`📁 Saved Video: ${data.video.filename}`, 'accent');
    if (data.video.thumbnail_url) {
      appendLog(`🖼️ Custom Thumbnail Attached: ${data.video.thumbnail_url}`, 'accent');
    }
    setStatus('Ready', 'ready');

    // Show result preview
    resultVideo.src = data.video.url;
    if (data.video.thumbnail_url) {
      resultVideo.poster = data.video.thumbnail_url;
      const thumbImg = document.getElementById('result-thumbnail');
      if (thumbImg) {
        thumbImg.src = data.video.thumbnail_url;
        thumbImg.style.display = 'block';
      }
    }
    
    const ytLinkRow = document.getElementById('yt-link-row');
    const ytLink = document.getElementById('result-yt-link');
    const statusTag = document.getElementById('result-upload-status-tag');
    
    if (data.video.youtube_url) {
      if (ytLinkRow) ytLinkRow.style.display = 'flex';
      if (ytLink) {
        ytLink.href = data.video.youtube_url;
        ytLink.textContent = `Open Private Draft on YouTube (${data.video.youtube_id || 'View'}) ↗`;
      }
      if (statusTag) {
        statusTag.textContent = '✅ Uploaded to YouTube (Private Draft)';
        statusTag.style.background = 'rgba(16, 185, 129, 0.2)';
        statusTag.style.color = '#34d399';
      }
    } else {
      if (ytLinkRow) ytLinkRow.style.display = 'none';
      if (statusTag) {
        statusTag.textContent = 'Saved Locally';
        statusTag.style.background = 'rgba(239, 68, 68, 0.2)';
        statusTag.style.color = '#f87171';
      }
    }
    
    resultTitle.textContent = data.video.title;
    resultDesc.textContent = data.video.description;
    resultTags.innerHTML = data.video.tags.map(t => `<span class="tag-chip">${t}</span>`).join('');
    resultPreview.style.display = 'block';
    
    // Automatically load gallery to reflect new video
    if (document.getElementById('tab-gallery').classList.contains('active')) {
      loadGallery();
    }
  });

  evtSource.addEventListener('error', (e) => {
    appendLog('❌ Connection to Live Stream lost. Reconnecting...', 'error');
    setStatus('Disconnected', 'error');
  });
}

// ── Gallery ─────────────────────────────────────────────────────────────────
async function loadGallery() {
  try {
    const res = await fetch('/api/gallery');
    const data = await res.json();
    galleryGrid.innerHTML = '';

    if (data.videos.length === 0) {
      galleryGrid.style.display = 'none';
      galleryEmpty.style.display = 'flex';
      return;
    }
    
    galleryGrid.style.display = 'grid';
    galleryEmpty.style.display = 'none';

    data.videos.forEach(video => {
      const card = document.createElement('div');
      card.className = 'gallery-item';
      const posterAttr = video.thumbnail_url ? `poster="${video.thumbnail_url}"` : '';
      const thumbLink = video.thumbnail_url ? `<a href="${video.thumbnail_url}" target="_blank" style="color:var(--accent-blue); font-size:0.75rem; text-decoration:underline;">🖼️ View Thumbnail</a>` : '';
      card.innerHTML = `
        <div class="gallery-video-wrap">
          <video class="gallery-video" src="${video.url}" ${posterAttr} controls muted loop preload="metadata"></video>
        </div>
        <div class="gallery-info">
          <div class="gallery-title" title="${video.filename}">${video.filename}</div>
          <div class="gallery-date" style="display:flex; justify-content:space-between; align-items:center;">
            <span>${video.created_at} &bull; ${video.size_mb} MB</span>
            ${thumbLink}
          </div>
        </div>
      `;
      galleryGrid.appendChild(card);
    });
  } catch (e) {
    console.error('Failed to load gallery:', e);
  }
}

// ── Helpers ─────────────────────────────────────────────────────────────────
function showStatus(elementId, message, type = 'error') {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.textContent = message;
    el.className = 'status-msg ' + type;
    
    // Auto-hide success messages after 5 seconds
    if (type === 'success') {
        setTimeout(() => {
            if (el.textContent === message) el.className = 'status-msg';
        }, 5000);
    }
}

// ── Pre-Flight YouTube Check & Unified Trigger ─────────────────────────────
async function triggerGeneration(endpoint, payload, statusMsgId, btnElement) {
  // Visual state
  if (btnElement) {
    btnElement.disabled = true;
    btnElement.style.opacity = '0.7';
  }
  showStatus(statusMsgId, '🔍 Pre-Flight Check: Verifying YouTube channel connection...', 'warning');

  try {
    // 1. Check YouTube connectivity with backend
    const ytRes = await fetch('/api/settings/youtube/status');
    const ytData = await ytRes.json();

    if (!ytData.connected) {
      const failMsg = `⛔ YouTube Check Failed: ${ytData.message || 'Not connected'}.\n\nAll generated videos are set to automatically upload to YouTube as Private Drafts.\n\nVideo generation is blocked until YouTube credentials are authenticated in Settings.`;
      showStatus(statusMsgId, failMsg, 'error');
      alert(failMsg);
      checkYouTubeStatus(); // Refresh banner
      return;
    }

    // 2. YouTube is connected!
    showStatus(statusMsgId, '✅ YouTube Verified! Video WILL upload to YouTube (Private Draft). Starting...', 'success');
    appendLog('🔍 Pre-flight check: YouTube connection verified successfully.', 'accent');
    appendLog('🎯 Destination: YouTube Channel (Private Draft)', 'success');

    // 3. Initiate generation
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (data.status === 'error') {
      showStatus(statusMsgId, data.message, 'error');
      alert(data.message);
    } else {
      showStatus(statusMsgId, data.message || 'Pipeline started! Destination: YouTube (Private Draft)', 'success');
    }
  } catch (err) {
    console.error('Trigger generation error:', err);
    showStatus(statusMsgId, 'Failed to trigger generation: ' + err.message, 'error');
  } finally {
    if (btnElement) {
      btnElement.disabled = false;
      btnElement.style.opacity = '1';
    }
  }
}

// ── Music Library ───────────────────────────────────────────────────────────
function getSelectedMusicPreference() {
  const sel = document.getElementById('music-preference-select');
  return sel ? sel.value : 'all';
}

async function loadMusicLibrary() {
  const optGroup = document.getElementById('music-individual-options');
  const chipsContainer = document.getElementById('music-track-chips');
  const badgeCount = document.getElementById('music-badge-count');
  const select = document.getElementById('music-preference-select');
  const modeText = document.getElementById('music-mode-text');
  const toggleBtn = document.getElementById('btn-toggle-chips');

  if (toggleBtn && chipsContainer) {
    toggleBtn.addEventListener('click', () => {
      const isHidden = chipsContainer.style.display === 'none';
      chipsContainer.style.display = isHidden ? 'flex' : 'none';
      toggleBtn.textContent = isHidden ? 'Hide Tracks ▴' : 'View 22 Tracks ▾';
    });
  }

  if (select && modeText) {
    select.addEventListener('change', () => {
      const val = select.value;
      if (val === 'all') {
        modeText.textContent = '🔀 Auto-Rotate & Blend Across All 22 Tracks';
      } else if (val === 'mood') {
        modeText.textContent = '🎭 Smart Mood-Matched (Crime / Romance / History / Geography / Fun)';
      } else {
        const text = select.options[select.selectedIndex]?.textContent || val;
        modeText.textContent = `🎯 Selected Track: ${text}`;
      }
      document.querySelectorAll('.music-chip').forEach(c => {
        c.classList.toggle('active', c.getAttribute('data-filename') === val);
      });
    });
  }

  try {
    const res = await fetch('/api/music');
    if (!res.ok) return;
    const data = await res.json();

    if (badgeCount) {
      badgeCount.textContent = `${data.total} Tracks in Library`;
    }

    if (optGroup) {
      optGroup.innerHTML = '';
      data.tracks.forEach(track => {
        const opt = document.createElement('option');
        opt.value = track.filename;
        opt.textContent = `🎵 [${track.mood}] ${track.title}`;
        optGroup.appendChild(opt);
      });
    }

    if (chipsContainer) {
      chipsContainer.innerHTML = '';
      data.tracks.forEach(track => {
        const chip = document.createElement('div');
        const moodKey = track.mood.toLowerCase().replace(/[^a-z]/g, '');
        chip.className = 'music-chip';
        chip.setAttribute('data-filename', track.filename);
        chip.innerHTML = `
          <span class="chip-mood-dot chip-mood-${moodKey}"></span>
          <span>${track.title}</span>
          <span style="opacity: 0.6; font-size: 0.7rem;">(${track.mood})</span>
        `;
        chip.addEventListener('click', () => {
          if (select) {
            select.value = track.filename;
            select.dispatchEvent(new Event('change'));
          }
        });
        chipsContainer.appendChild(chip);
      });
    }
  } catch (err) {
    console.error('Failed to load music library:', err);
  }
}

// ── Generator Triggers ─────────────────────────────────────────────────────
document.getElementById('btn-auto-gen')?.addEventListener('click', (e) => {
  triggerGeneration('/api/generate/auto', { upload_youtube: true, music_preference: getSelectedMusicPreference() }, 'status-auto-gen', e.currentTarget);
});

document.getElementById('btn-manual-gen')?.addEventListener('click', (e) => {
  const story = document.getElementById('input-manual-story')?.value.trim();
  if (!story) return showStatus('status-manual-gen', 'Please enter a story or topic first.', 'error');
  triggerGeneration('/api/generate/manual', { story, upload_youtube: true, music_preference: getSelectedMusicPreference() }, 'status-manual-gen', e.currentTarget);
});

const wikiBtnMap = {
  'btn-wiki-truecrime': 'status-wiki-truecrime',
  'btn-wiki-history': 'status-wiki-history',
  'btn-wiki-geography': 'status-wiki-geography',
  'btn-wiki-love': 'status-wiki-love'
};

Object.entries(wikiBtnMap).forEach(([btnId, statusId]) => {
  document.getElementById(btnId)?.addEventListener('click', (e) => {
    const topic = e.currentTarget.getAttribute('data-topic');
    triggerGeneration('/api/generate/wiki', { upload_youtube: true, topic, music_preference: getSelectedMusicPreference() }, statusId, e.currentTarget);
  });
});

// ── Settings Triggers ───────────────────────────────────────────────────────
document.getElementById('btn-save-groq')?.addEventListener('click', async () => {
  const key = document.getElementById('input-groq-key')?.value.trim();
  if (!key) return showStatus('status-groq', 'Please enter a Groq API key.', 'error');
  
  const btn = document.getElementById('btn-save-groq');
  btn.disabled = true;
  btn.textContent = 'Saving...';
  
  try {
      const res = await fetch('/api/settings/groq', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key })
      });
      const data = await res.json();
      showStatus('status-groq', data.message, data.status);
      if (data.status === 'success') {
          document.getElementById('input-groq-key').value = '';
      }
  } catch (e) {
      console.error(e);
      showStatus('status-groq', 'Failed to save Groq API key.', 'error');
  } finally {
      btn.disabled = false;
      btn.textContent = 'Save Groq Key';
  }
});

// ── YouTube Credentials List & Switcher ────────────────────────────────────
function renderCredentials(creds) {
  const container = document.getElementById('cred-list');
  const badge = document.getElementById('cred-count-badge');
  if (!container) return;

  if (badge) {
    badge.textContent = `${creds.length} Channel${creds.length === 1 ? '' : 's'} Available`;
  }

  if (!creds || creds.length === 0) {
    container.innerHTML = '<div class="cred-empty">No channels configured yet. Upload a client_secret.json above to create your first channel profile.</div>';
    return;
  }

  // Check if active channel needs Google SSO authorization
  const activeChannel = creds.find(c => c.is_active);
  const authBanner = document.getElementById('auth-action-banner');
  if (authBanner) {
    if (activeChannel && !activeChannel.has_token) {
      authBanner.style.display = 'flex';
      const desc = authBanner.querySelector('.auth-banner-desc');
      if (desc) {
        desc.innerHTML = `Active channel <strong>${activeChannel.project_id}</strong> is selected but not authorized. Click <strong>"Sign In with Google (SSO)"</strong> below or on the channel card to link your account.`;
      }
    } else {
      authBanner.style.display = 'none';
    }
  }

  container.innerHTML = '';
  creds.forEach(item => {
    const el = document.createElement('div');
    el.className = `cred-item ${item.is_active ? 'active' : ''}`;
    
    let statusBadge = '';
    if (item.is_active && item.has_token) {
      statusBadge = `<span class="cred-badge cred-badge--active">✅ Active & Connected</span>`;
    } else if (item.is_active && !item.has_token) {
      statusBadge = `<span class="cred-badge cred-badge--warning">⚠️ Active (Sign-In Needed)</span>`;
    } else if (item.has_token) {
      statusBadge = `<span class="cred-badge" style="background:rgba(16,185,129,0.15);color:#34d399;border:1px solid rgba(16,185,129,0.3);">🟢 Authorized (Standby)</span>`;
    } else {
      statusBadge = `<span class="cred-badge cred-badge--standby">⚪ Standby (Needs Sign-In)</span>`;
    }

    const tokenPill = item.has_token
      ? `<span class="channel-pill channel-pill--ready">🔑 Token Paired</span>`
      : `<span class="channel-pill channel-pill--warn">⚠️ No Token</span>`;

    let actionBtnHtml = '';
    if (item.is_active) {
      if (!item.has_token) {
        actionBtnHtml = `<button class="btn-cred-sso-action" data-channel="${item.project_id}"><span>🔑</span> Sign In with Google (SSO)</button>`;
      } else {
        actionBtnHtml = `<button class="btn-cred-activate btn-active-state" disabled>✓ Active Channel</button>`;
      }
    } else {
      actionBtnHtml = `<button class="btn-cred-activate" data-file="${item.filename}">⚡ Switch to this Channel</button>`;
    }

    el.innerHTML = `
      <div class="cred-left">
        <div class="cred-icon">📺</div>
        <div class="cred-name-wrap">
          <div class="cred-name">
            <span>${item.project_id || 'YouTube Project'}</span>
            ${statusBadge}
          </div>
          <div class="cred-sub">
            <span class="channel-pill">🆔 ${item.client_id_short}</span>
            ${tokenPill}
            <span>• Updated: ${item.modified_at}</span>
          </div>
        </div>
      </div>
      <div class="cred-actions">
        ${actionBtnHtml}
        <button class="btn-cred-delete" data-file="${item.filename}" title="Remove this channel profile">
          🗑️
        </button>
      </div>
    `;

    // Google SSO Button handler on the card
    const btnSsoCard = el.querySelector('.btn-cred-sso-action');
    if (btnSsoCard) {
      btnSsoCard.addEventListener('click', async () => {
        btnSsoCard.disabled = true;
        btnSsoCard.innerHTML = '<span>⏳</span> Authorizing Google SSO...';
        showStatus('status-youtube', 'Opening Google Sign-In in your browser. Please approve access to link your YouTube channel...', 'info');
        try {
          const res = await fetch('/api/settings/youtube/authenticate', { method: 'POST' });
          const data = await res.json();
          if (data.status === 'success' || data.connected) {
            showStatus('status-youtube', '🎉 ' + (data.message || 'YouTube authenticated successfully!'), 'success');
            if (data.credentials) {
              renderCredentials(data.credentials);
            } else {
              await loadCredentialsList();
            }
            await checkYouTubeStatus();
          } else {
            showStatus('status-youtube', '❌ ' + (data.message || 'Authentication failed or was cancelled.'), 'error');
            btnSsoCard.disabled = false;
            btnSsoCard.innerHTML = '<span>🔑</span> Sign In with Google (SSO)';
            await checkYouTubeStatus();
          }
        } catch (err) {
          console.error(err);
          showStatus('status-youtube', 'Failed to communicate with authentication service.', 'error');
          btnSsoCard.disabled = false;
          btnSsoCard.innerHTML = '<span>🔑</span> Sign In with Google (SSO)';
        }
      });
    }

    // Activate / Switch button handler
    const btnActivate = el.querySelector('.btn-cred-activate:not(.btn-active-state)');
    if (btnActivate) {
      btnActivate.addEventListener('click', async () => {
        btnActivate.disabled = true;
        btnActivate.innerHTML = '<span>⏳</span> Switching...';
        try {
          const resp = await fetch('/api/settings/youtube/select', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: item.filename })
          });
          const selData = await resp.json();
          showStatus('status-youtube', selData.message, selData.status);
          if (selData.credentials) {
            renderCredentials(selData.credentials);
          } else {
            await loadCredentialsList();
          }
          await checkYouTubeStatus();
        } catch (err) {
          console.error(err);
          showStatus('status-youtube', 'Failed to switch channel: ' + err.message, 'error');
          btnActivate.disabled = false;
          btnActivate.innerHTML = '<span>⚡</span> Switch to this Channel';
        }
      });
    }

    // Delete button handler
    const btnDelete = el.querySelector('.btn-cred-delete');
    if (btnDelete) {
      btnDelete.addEventListener('click', async () => {
        if (!confirm(`Are you sure you want to delete Channel Profile '${item.project_id}' and all associated tokens?`)) return;
        btnDelete.disabled = true;
        try {
          const resp = await fetch(`/api/settings/youtube/credentials/${encodeURIComponent(item.filename)}`, {
            method: 'DELETE'
          });
          const delData = await resp.json();
          showStatus('status-youtube', delData.message, delData.status);
          
          if (delData.status === 'success') {
            el.style.transition = 'all 0.2s ease';
            el.style.opacity = '0';
            el.style.transform = 'scale(0.95)';
            setTimeout(() => {
              el.remove();
              if (delData.credentials) {
                renderCredentials(delData.credentials);
              } else {
                loadCredentialsList();
              }
            }, 200);
          } else {
            btnDelete.disabled = false;
          }
          await checkYouTubeStatus();
        } catch (err) {
          console.error(err);
          showStatus('status-youtube', 'Failed to delete channel profile: ' + err.message, 'error');
          btnDelete.disabled = false;
        }
      });
    }

    container.appendChild(el);
  });
}

async function loadCredentialsList() {
  const container = document.getElementById('cred-list');
  if (!container) return;

  try {
    const res = await fetch('/api/settings/youtube/credentials');
    if (!res.ok) return;
    const data = await res.json();
    renderCredentials(data.credentials || []);
  } catch (err) {
    console.error('Failed to load credentials:', err);
    if (container) container.innerHTML = '<div class="cred-empty">Failed to load credentials list.</div>';
  }
}

document.getElementById('btn-save-youtube')?.addEventListener('click', async () => {
  const fileInput = document.getElementById('input-youtube-json');
  if (!fileInput || !fileInput.files.length) {
    document.getElementById('file-label-text').textContent = 'Choose OAuth client_secret.json or token.json...';
    return showStatus('status-youtube', 'Please select a credentials JSON file first.', 'error');
  }
  
  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append('file', file);
  
  const btn = document.getElementById('btn-save-youtube');
  btn.disabled = true;
  btn.textContent = 'Uploading & Saving...';
  
  try {
    const res = await fetch('/api/settings/youtube', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    showStatus('status-youtube', data.message, data.status);
    if (data.status === 'success') {
      fileInput.value = '';
      document.getElementById('file-label-text').textContent = 'Choose OAuth client_secret.json or token.json...';
      await loadCredentialsList();
      checkYouTubeStatus();
    }
  } catch (e) {
    console.error(e);
    showStatus('status-youtube', 'Failed to upload YouTube credentials.', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '📺 Add Channel File';
  }
});

// ── YouTube Connection Checker ───────────────────────────────────────────────
async function checkYouTubeStatus() {
  const dot = document.getElementById('yt-status-dot');
  const title = document.getElementById('yt-status-title');
  const desc = document.getElementById('yt-status-sub');
  const badge = document.getElementById('yt-destination-badge');
  const cardTags = document.querySelectorAll('.card-dest-tag');
  const authBanner = document.getElementById('auth-action-banner');
  
  if (title) title.textContent = 'Verifying YouTube Connection...';
  if (dot) dot.className = 'yt-status-dot';
  
  try {
    const res = await fetch('/api/settings/youtube/status');
    const data = await res.json();
    
    if (data.connected) {
      if (authBanner) authBanner.style.display = 'none';
      if (dot) dot.className = 'yt-status-dot connected';
      if (title) title.textContent = 'YouTube Verified & Connected';
      if (desc) desc.textContent = 'Channel authenticated. All generated videos WILL automatically upload to YouTube as Private Drafts.';
      if (badge) {
        badge.className = 'yt-dest-pill verified';
        badge.textContent = '✅ Destination: YouTube (Private Draft)';
      }
      cardTags.forEach(tag => {
        tag.className = 'card-dest-tag connected';
        tag.innerHTML = '<span class="card-dest-tag-dot"></span> Upload Target: <strong>YouTube (Private Draft)</strong>';
      });
    } else {
      if (dot) dot.className = 'yt-status-dot disconnected';
      if (data.has_client_secret) {
        if (authBanner) authBanner.style.display = 'flex';
        if (title) title.textContent = 'Action Required: Sign In with Google';
        if (desc) desc.textContent = 'Client credentials loaded! Click "Sign In with Google" below to grant channel permissions and create token.json.';
      } else {
        if (authBanner) authBanner.style.display = 'none';
        if (title) title.textContent = 'YouTube Not Connected';
        if (desc) desc.textContent = (data.message || 'Please upload credentials and authenticate in Settings.') + ' Video generation locked.';
      }
      if (badge) {
        badge.className = 'yt-dest-pill disconnected';
        badge.textContent = '❌ Upload Blocked (Not Connected)';
      }
      cardTags.forEach(tag => {
        tag.className = 'card-dest-tag';
        tag.innerHTML = '<span class="card-dest-tag-dot"></span> <strong>YouTube Disconnected</strong> (Upload Blocked)';
      });
    }
  } catch (e) {
    console.error('Failed to check YouTube status:', e);
    if (dot) dot.className = 'yt-status-dot disconnected';
    if (title) title.textContent = 'YouTube Check Failed';
    if (desc) desc.textContent = 'Could not communicate with local server to verify YouTube connection.';
    if (badge) {
      badge.className = 'yt-dest-pill disconnected';
      badge.textContent = '⚠️ Check Failed';
    }
  }
}

document.getElementById('btn-authenticate-google')?.addEventListener('click', async () => {
  const btn = document.getElementById('btn-authenticate-google');
  if (!btn) return;
  btn.disabled = true;
  btn.classList.add('loading');
  const originalHtml = btn.innerHTML;
  btn.innerHTML = '<span>⏳</span> Opening Google Sign-in...';
  
  showStatus('status-youtube', 'Opening Google Sign-In in your browser. Please select your Google account and click "Continue / Allow" to authorize your YouTube channel...', 'info');
  
  try {
    const res = await fetch('/api/settings/youtube/authenticate', { method: 'POST' });
    const data = await res.json();
    
    if (data.status === 'success' || data.connected) {
      showStatus('status-youtube', '🎉 ' + (data.message || 'YouTube authenticated successfully!'), 'success');
      await loadCredentialsList();
      await checkYouTubeStatus();
    } else {
      showStatus('status-youtube', '❌ ' + (data.message || 'Authentication failed or was cancelled.'), 'error');
      await checkYouTubeStatus();
    }
  } catch (err) {
    console.error(err);
    showStatus('status-youtube', 'Failed to communicate with authentication service.', 'error');
  } finally {
    btn.disabled = false;
    btn.classList.remove('loading');
    btn.innerHTML = originalHtml;
  }
});

document.getElementById('btn-recheck-yt')?.addEventListener('click', async (e) => {
  const btn = e.currentTarget;
  if (!btn) return;
  btn.disabled = true;
  const originalText = btn.textContent;
  btn.textContent = '⏳ Checking...';
  try {
    await checkYouTubeStatus();
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
  }
});

// ── Init ─────────────────────────────────────────────────────────────────────
try { clearTerminal(); } catch (e) { console.error(e); }
try { connectLiveStream(); } catch (e) { console.error(e); }
try { checkYouTubeStatus(); } catch (e) { console.error(e); }
try { loadMusicLibrary(); } catch (e) { console.error(e); }
try { loadCredentialsList(); } catch (e) { console.error(e); }

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    checkYouTubeStatus();
    loadMusicLibrary();
    loadCredentialsList();
  });
}
window.addEventListener('load', () => {
  checkYouTubeStatus();
  loadMusicLibrary();
  loadCredentialsList();
});



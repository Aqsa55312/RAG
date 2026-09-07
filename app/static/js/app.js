/**
 * Enterprise Knowledge AI - Frontend Application Logic
 * Manages JWT Auth, RBAC Role Switching, RAG Chat, Ingestion, and Health Analytics.
 */

// Application State
const state = {
  activeRole: 'admin',
  token: '',
  allowedSpaces: ['*'],
  canSync: true,
  isGenerating: false,
  health: null
};

// DOM Elements
const elements = {
  roleBtns: document.querySelectorAll('.role-btn'),
  roleBadgeDisplay: document.getElementById('active-role-badge'),
  allowedSpacesDisplay: document.getElementById('allowed-spaces-badge'),
  tabLinks: document.querySelectorAll('.tab-link'),
  tabContents: document.querySelectorAll('.tab-content'),
  
  // Health Indicators
  dbStatusDot: document.getElementById('db-status-dot'),
  dbStatusText: document.getElementById('db-status-text'),
  ollamaStatusDot: document.getElementById('ollama-status-dot'),
  ollamaStatusText: document.getElementById('ollama-status-text'),
  vectorCountPill: document.getElementById('vector-count-pill'),

  // Chat Elements
  chatMessages: document.getElementById('chat-messages'),
  chatInput: document.getElementById('chat-input'),
  sendBtn: document.getElementById('send-btn'),
  filterSpaceSelect: document.getElementById('filter-space-select'),
  topKSlider: document.getElementById('top-k-slider'),
  topKValue: document.getElementById('top-k-val'),
  clearChatBtn: document.getElementById('clear-chat-btn'),
  promptChips: document.querySelectorAll('.chip'),

  // Ingestion Elements
  ingestForm: document.getElementById('manual-ingest-form'),
  ingestTitle: document.getElementById('doc-title'),
  ingestSpace: document.getElementById('doc-space'),
  ingestContent: document.getElementById('doc-content'),
  ingestBtn: document.getElementById('ingest-submit-btn'),
  rbacIngestWarning: document.getElementById('rbac-ingest-warning'),
  syncConfluenceBtn: document.getElementById('sync-confluence-btn'),
  syncNotionBtn: document.getElementById('sync-notion-btn'),

  // Explorer & Analytics
  statTotalVectors: document.getElementById('stat-total-vectors'),
  statCollection: document.getElementById('stat-collection'),
  statOllamaModel: document.getElementById('stat-ollama-model'),
  tokenInspector: document.getElementById('token-inspector'),
  copyTokenBtn: document.getElementById('copy-token-btn'),

  // Toast Container
  toastContainer: document.getElementById('toast-container')
};

// ==============================================================================
// 1. Initialization & Role Switching
// ==============================================================================

async function init() {
  setupEventListeners();
  await switchRole('admin');
  await fetchSystemHealth();
  setInterval(fetchSystemHealth, 15000); // Polling health every 15s
}

function setupEventListeners() {
  // Role Switcher Buttons
  elements.roleBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const role = btn.dataset.role;
      switchRole(role);
    });
  });

  // Tab Navigation
  elements.tabLinks.forEach(link => {
    link.addEventListener('click', () => {
      const targetTab = link.dataset.tab;
      elements.tabLinks.forEach(l => l.classList.remove('active'));
      elements.tabContents.forEach(c => c.classList.remove('active'));

      link.classList.add('active');
      document.getElementById(targetTab).classList.add('active');
    });
  });

  // Chat Events
  elements.sendBtn.addEventListener('click', handleSendMessage);
  elements.chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  });

  // Auto-resize chat textarea
  elements.chatInput.addEventListener('input', () => {
    elements.chatInput.style.height = 'auto';
    elements.chatInput.style.height = Math.min(elements.chatInput.scrollHeight, 140) + 'px';
  });

  // Slider Top-K
  elements.topKSlider.addEventListener('input', (e) => {
    elements.topKValue.textContent = e.target.value;
  });

  // Clear Chat
  elements.clearChatBtn.addEventListener('click', resetChat);

  // Prompt Suggestion Chips
  elements.promptChips.forEach(chip => {
    chip.addEventListener('click', () => {
      elements.chatInput.value = chip.dataset.prompt;
      handleSendMessage();
    });
  });

  // Manual Ingestion Form
  elements.ingestForm.addEventListener('submit', handleManualIngest);

  // Sync Connectors
  elements.syncConfluenceBtn.addEventListener('click', handleConfluenceSync);
  elements.syncNotionBtn.addEventListener('click', handleNotionSync);

  // Copy Token
  elements.copyTokenBtn.addEventListener('click', () => {
    if (state.token) {
      navigator.clipboard.writeText(state.token);
      showToast('JWT Token berhasil disalin!', 'success');
    }
  });
}

// ==============================================================================
// 2. Authentication & Token Management
// ==============================================================================

async function switchRole(role) {
  state.activeRole = role;

  // Update UI buttons
  elements.roleBtns.forEach(btn => {
    btn.classList.toggle('active', btn.dataset.role === role);
  });

  try {
    const res = await fetch('/api/v1/auth/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: `user_${role}`,
        email: `${role}@company.com`,
        role: role
      })
    });

    if (!res.ok) throw new Error('Gagal mendapatkan token auth.');

    const data = await res.json();
    state.token = data.access_token;
    state.allowedSpaces = data.allowed_spaces;
    state.canSync = data.can_sync;

    // Update Display Badges
    elements.roleBadgeDisplay.textContent = role.toUpperCase();
    elements.allowedSpacesDisplay.textContent = state.allowedSpaces.join(', ');

    // Update Ingest Permission Banner
    if (state.canSync) {
      elements.rbacIngestWarning.style.display = 'none';
      elements.ingestBtn.disabled = false;
      elements.syncConfluenceBtn.disabled = false;
      elements.syncNotionBtn.disabled = false;
    } else {
      elements.rbacIngestWarning.style.display = 'block';
      elements.rbacIngestWarning.innerHTML = `⚠️ Role <strong>${role.toUpperCase()}</strong> tidak memiliki izin sinkronisasi (Hanya Admin yang dapat mengindeks dokumen).`;
      elements.ingestBtn.disabled = true;
      elements.syncConfluenceBtn.disabled = true;
      elements.syncNotionBtn.disabled = true;
    }

    // Update Token Inspector in Analytics Tab
    elements.tokenInspector.textContent = state.token;

    showToast(`Beralih ke Role: ${role.toUpperCase()}`, 'success');
  } catch (err) {
    showToast(`Error Auth: ${err.message}`, 'error');
  }
}

// ==============================================================================
// 3. System Health & Diagnostics
// ==============================================================================

async function fetchSystemHealth() {
  try {
    const res = await fetch('/api/v1/health');
    if (!res.ok) throw new Error('Health check error');
    const data = await res.json();
    state.health = data;

    // ChromaDB Status
    const dbOk = data.vector_db_status === 'connected';
    elements.dbStatusDot.className = `dot ${dbOk ? 'online' : 'offline'}`;
    elements.dbStatusText.textContent = dbOk ? 'ChromaDB' : 'Chroma Disconnected';

    // Ollama Status
    const ollamaOk = data.ollama_status === 'connected';
    elements.ollamaStatusDot.className = `dot ${ollamaOk ? 'online' : 'warning'}`;
    elements.ollamaStatusText.textContent = ollamaOk ? 'Ollama Ready' : 'Ollama Degraded';

    // Vector Count
    elements.vectorCountPill.textContent = `${data.total_vectors} Vektor`;
    if (elements.statTotalVectors) elements.statTotalVectors.textContent = data.total_vectors;
    if (elements.statCollection) elements.statCollection.textContent = data.active_collection;

  } catch (err) {
    elements.dbStatusDot.className = 'dot offline';
    elements.ollamaStatusDot.className = 'dot offline';
  }
}

// ==============================================================================
// 4. RAG Chat & Assistant
// ==============================================================================

async function handleSendMessage() {
  const query = elements.chatInput.value.trim();
  if (!query || state.isGenerating) return;

  // Remove empty placeholder state if present
  const emptyState = document.getElementById('empty-chat-state');
  if (emptyState) emptyState.remove();

  // Add User Message Bubble
  appendMessage('user', query);
  elements.chatInput.value = '';
  elements.chatInput.style.height = 'auto';

  // Add Loading / Typing Indicator Bubble
  const aiMessageId = appendTypingIndicator();
  state.isGenerating = true;
  elements.sendBtn.disabled = true;

  try {
    const spaceFilter = elements.filterSpaceSelect.value;
    const topK = parseInt(elements.topKSlider.value, 10);

    const payload = {
      query: query,
      top_k: topK
    };
    if (spaceFilter) {
      payload.filter_space = spaceFilter;
    }

    const res = await fetch('/api/v1/rag/query', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${state.token}`
      },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || 'Gagal memproses pertanyaan.');
    }

    const data = await res.json();

    // Replace typing indicator with actual AI answer
    updateAIMessage(aiMessageId, data.answer, data.sources, data.applied_spaces);

  } catch (err) {
    updateAIMessage(aiMessageId, `❌ Error: ${err.message}`, []);
    showToast(err.message, 'error');
  } finally {
    state.isGenerating = false;
    elements.sendBtn.disabled = false;
  }
}

function appendMessage(sender, text) {
  const msgDiv = document.createElement('div');
  msgDiv.className = `message ${sender}`;

  const avatar = sender === 'user' ? '👤' : '✨';
  msgDiv.innerHTML = `
    <div class="message-avatar">${avatar}</div>
    <div class="message-body">
      <div class="message-bubble">${escapeHtml(text)}</div>
    </div>
  `;

  elements.chatMessages.appendChild(msgDiv);
  scrollToBottom();
  return msgDiv;
}

function appendTypingIndicator() {
  const msgDiv = document.createElement('div');
  const id = `ai-msg-${Date.now()}`;
  msgDiv.id = id;
  msgDiv.className = 'message ai';

  msgDiv.innerHTML = `
    <div class="message-avatar">✨</div>
    <div class="message-body">
      <div class="message-bubble">
        <div class="typing-dots">
          <span></span><span></span><span></span>
        </div>
      </div>
    </div>
  `;

  elements.chatMessages.appendChild(msgDiv);
  scrollToBottom();
  return id;
}

function updateAIMessage(id, answer, sources = [], appliedSpaces = []) {
  const msgDiv = document.getElementById(id);
  if (!msgDiv) return;

  const formattedAnswer = formatMarkdown(answer);

  let sourcesHtml = '';
  if (sources && sources.length > 0) {
    const sourceCards = sources.map((s, idx) => {
      const spaceBadge = getSpaceBadge(s.space || s.metadata?.space || 'GENERAL');
      const score = s.score !== null && s.score !== undefined ? `<span style="color:var(--primary); font-size:0.75rem;">Score: ${s.score.toFixed(3)}</span>` : '';
      return `
        <div class="source-card">
          <div class="source-header">
            <span>[#${idx + 1}] ${escapeHtml(s.title || 'Untitled')}</span>
            <div>${spaceBadge} ${score}</div>
          </div>
          <div class="source-preview">${escapeHtml(s.content)}</div>
        </div>
      `;
    }).join('');

    sourcesHtml = `
      <div class="sources-container">
        <div class="sources-title">📚 Referensi Dokumen (${sources.length} Chunks Relevan)</div>
        <div class="sources-list">${sourceCards}</div>
      </div>
    `;
  }

  msgDiv.querySelector('.message-body').innerHTML = `
    <div class="message-bubble">
      ${formattedAnswer}
      ${sourcesHtml}
    </div>
  `;

  scrollToBottom();
}

function resetChat() {
  elements.chatMessages.innerHTML = `
    <div id="empty-chat-state" class="empty-chat">
      <div class="empty-icon">🤖</div>
      <h3>Enterprise Knowledge Assistant</h3>
      <p>Ajukan pertanyaan seputar dokumen perusahaan, arsitektur sistem, SOP internal, atau kebijakan HR.</p>
      <div class="prompt-chips">
        <button class="chip" data-prompt="Bagaimana arsitektur Kubernetes & CI/CD?">🚀 Arsitektur Kubernetes</button>
        <button class="chip" data-prompt="Berapa jatah cuti tahunan karyawan?">🌴 Kebijakan Cuti HR</button>
        <button class="chip" data-prompt="Apa SOP monitoring server & respons alert?">⚡ SOP Monitoring OPS</button>
      </div>
    </div>
  `;
  // Re-attach listeners to new chips
  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      elements.chatInput.value = chip.dataset.prompt;
      handleSendMessage();
    });
  });
}

function scrollToBottom() {
  elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

// ==============================================================================
// 5. Knowledge Ingestion
// ==============================================================================

async function handleManualIngest(e) {
  e.preventDefault();
  if (!state.canSync) {
    showToast('Akses Ditolak: Hanya role Admin yang dapat melakukan ingestion.', 'error');
    return;
  }

  const title = elements.ingestTitle.value.trim();
  const space = elements.ingestSpace.value;
  const content = elements.ingestContent.value.trim();

  if (!title || !content) {
    showToast('Judul dan isi dokumen wajib diisi.', 'warning');
    return;
  }

  elements.ingestBtn.disabled = true;
  elements.ingestBtn.innerHTML = '⏳ Mengindeks Dokumen...';

  try {
    const res = await fetch('/api/v1/ingest/text', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${state.token}`
      },
      body: JSON.stringify({
        title: title,
        space: space,
        content: content,
        source: 'manual'
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Gagal mengindeks dokumen.');
    }

    const data = await res.json();
    showToast(`Sukses! ${data.chunks_created} potongan dokumen berhasil disimpan ke Space '${space}'.`, 'success');

    // Reset Form
    elements.ingestTitle.value = '';
    elements.ingestContent.value = '';
    fetchSystemHealth();

  } catch (err) {
    showToast(`Error Ingest: ${err.message}`, 'error');
  } finally {
    elements.ingestBtn.disabled = false;
    elements.ingestBtn.innerHTML = '📥 Indeks Dokumen ke Vector DB';
  }
}

async function handleConfluenceSync() {
  if (!state.canSync) return;
  elements.syncConfluenceBtn.disabled = true;
  elements.syncConfluenceBtn.textContent = 'Syncing...';

  try {
    const res = await fetch('/api/v1/ingest/confluence', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${state.token}`
      },
      body: JSON.stringify({})
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Gagal sinkronisasi Confluence.');

    showToast(data.message, data.status === 'success' ? 'success' : 'warning');
    fetchSystemHealth();
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    elements.syncConfluenceBtn.disabled = false;
    elements.syncConfluenceBtn.textContent = 'Sync Sekarang';
  }
}

async function handleNotionSync() {
  if (!state.canSync) return;
  elements.syncNotionBtn.disabled = true;
  elements.syncNotionBtn.textContent = 'Syncing...';

  try {
    const res = await fetch('/api/v1/ingest/notion', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${state.token}`
      },
      body: JSON.stringify({})
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Gagal sinkronisasi Notion.');

    showToast(data.message, data.status === 'success' ? 'success' : 'warning');
    fetchSystemHealth();
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    elements.syncNotionBtn.disabled = false;
    elements.syncNotionBtn.textContent = 'Sync Sekarang';
  }
}

// ==============================================================================
// 6. Utility Functions
// ==============================================================================

function getSpaceBadge(space) {
  const s = (space || 'GENERAL').toUpperCase();
  if (s === 'ENG') return `<span class="badge badge-eng">ENG</span>`;
  if (s === 'HR') return `<span class="badge badge-hr">HR</span>`;
  if (s === 'OPS') return `<span class="badge badge-ops">OPS</span>`;
  return `<span class="badge badge-general">${s}</span>`;
}

function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  const icon = type === 'success' ? '✅' : (type === 'error' ? '❌' : 'ℹ️');
  toast.innerHTML = `<span>${icon}</span><span>${escapeHtml(message)}</span>`;

  elements.toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(50px)';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function escapeHtml(text) {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatMarkdown(text) {
  if (!text) return '';
  let formatted = escapeHtml(text);

  // Bold **text**
  formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Italic *text*
  formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');
  // Inline code `code`
  formatted = formatted.replace(/`([^`]+)`/g, '<code style="background:rgba(0,0,0,0.4); padding:2px 6px; border-radius:4px; font-family:monospace; color:var(--primary);">$1</code>');
  // Line breaks
  formatted = formatted.replace(/\n/g, '<br>');

  return formatted;
}

// Start application on DOM Ready
document.addEventListener('DOMContentLoaded', init);

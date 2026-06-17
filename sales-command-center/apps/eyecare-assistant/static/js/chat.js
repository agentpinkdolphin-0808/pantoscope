'use strict';

const threadEl = document.getElementById('thread');
const formEl = document.getElementById('input-form');
const inputEl = document.getElementById('message-input');

function formatTime(isoString) {
  try {
    return new Date(isoString).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  } catch (e) {
    return '';
  }
}

function appendMessage(role, content, timestamp) {
  const row = document.createElement('div');
  row.className = `msg-row ${role}`;

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.textContent = content;

  const ts = document.createElement('div');
  ts.className = 'msg-timestamp';
  ts.textContent = formatTime(timestamp);

  row.appendChild(bubble);
  row.appendChild(ts);
  threadEl.appendChild(row);
  threadEl.scrollTop = threadEl.scrollHeight;
  return row;
}

function showEmptyState() {
  const empty = document.createElement('div');
  empty.className = 'empty-thread';
  empty.textContent = 'Ask about eye-care products, alternatives, or current pricing.';
  threadEl.appendChild(empty);
}

async function loadHistory() {
  try {
    const res = await fetch('api/history');
    const history = await res.json();
    threadEl.innerHTML = '';
    if (!history.length) {
      showEmptyState();
      return;
    }
    history.forEach(m => appendMessage(m.role, m.content, m.timestamp));
  } catch (e) {
    showEmptyState();
  }
}

async function sendMessage(message) {
  const emptyState = threadEl.querySelector('.empty-thread');
  if (emptyState) emptyState.remove();

  appendMessage('user', message, new Date().toISOString());

  const pending = document.createElement('div');
  pending.className = 'msg-row assistant';
  pending.innerHTML = '<div class="msg-bubble">…</div>';
  threadEl.appendChild(pending);
  threadEl.scrollTop = threadEl.scrollHeight;

  try {
    const res = await fetch('api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    const data = await res.json();
    pending.remove();
    if (data.error) {
      appendMessage('assistant', `Error: ${data.error}`, new Date().toISOString());
    } else {
      appendMessage('assistant', data.assistant.content, data.assistant.timestamp);
    }
  } catch (e) {
    pending.remove();
    appendMessage('assistant', 'Network error — please try again.', new Date().toISOString());
  }
}

formEl.addEventListener('submit', e => {
  e.preventDefault();
  const message = inputEl.value.trim();
  if (!message) return;
  inputEl.value = '';
  sendMessage(message);
});

loadHistory();

import React, { useEffect, useMemo, useState } from 'react';
import {
  Bot,
  Database,
  RefreshCw,
  SendHorizontal,
  ShieldCheck,
} from 'lucide-react';

function appHeaders(appId) {
  return {
    'content-type': 'application/json',
    'x-app-id': appId,
  };
}

async function readJson(response) {
  const text = await response.text();
  if (!text.trim()) {
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}.`);
    }
    return {};
  }
  const payload = JSON.parse(text);
  if (!response.ok) {
    if (typeof payload?.error === 'string') {
      throw new Error(payload.error);
    }
    throw new Error(`Request failed with status ${response.status}.`);
  }
  return payload;
}

async function readNdjson(response) {
  const text = await response.text();
  if (!response.ok) {
    let payload;
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
    if (typeof payload?.error === 'string') {
      throw new Error(payload.error);
    }
    throw new Error(`Request failed with status ${response.status}.`);
  }
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

function buildAssistantEntry(result) {
  return {
    role: 'assistant',
    text: result.message,
    metadata: {
      responseState: result.response_state || result.channel_response?.state?.status || 'ok',
      capability: result.primary_capability_id || result.selected_capability_id || null,
      route: result.orchestration_mode || result.route || null,
      blocks: result.channel_response?.blocks ?? [],
    },
  };
}

function buildResultFromEvents(events) {
  const result = [...events].reverse().find((item) => item.type === 'result');
  if (result) {
    return result;
  }

  const errorEvent = [...events].reverse().find(
    (item) => item.type === 'error' && typeof item.message === 'string' && item.message.trim(),
  );
  if (errorEvent) {
    throw new Error(errorEvent.message);
  }

  const tokenText = events
    .filter((item) => item.type === 'token' && typeof item.content === 'string')
    .map((item) => item.content)
    .join('')
    .trim();
  if (tokenText) {
    const blocks = events
      .filter((item) => item.type === 'block' && item.payload)
      .map((item) => item.payload);
    const stateEvent = [...events].reverse().find((item) => item.type === 'state' && item.payload);
    return {
      type: 'result',
      message: tokenText,
      channel_response: {
        blocks,
        state: stateEvent?.payload || { status: 'ok' },
      },
    };
  }

  throw new Error('Chat response did not include a final result.');
}

function MessageBubble({ message }) {
  const blocks = message.metadata?.blocks ?? [];
  return (
    <article className={`chat-bubble chat-bubble--${message.role}`}>
      <div className="chat-bubble__role">{message.role === 'user' ? 'You' : 'FastMCP'}</div>
      <p>{message.text}</p>
      {blocks.length > 0 ? (
        <div className="chat-bubble__blocks">
          {blocks.map((block) => (
            <div
              key={block.block_id || `${block.kind}-${block.title || block.body}`}
              className="chat-bubble__block"
            >
              <strong>{block.title || block.kind}</strong>
              {block.body ? <span>{block.body}</span> : null}
            </div>
          ))}
        </div>
      ) : null}
      {message.metadata?.capability || message.metadata?.route ? (
        <div className="chat-bubble__meta">
          {message.metadata.route ? <span>{message.metadata.route}</span> : null}
          {message.metadata.capability ? <span>{message.metadata.capability}</span> : null}
        </div>
      ) : null}
    </article>
  );
}

export default function App() {
  const [apps, setApps] = useState([]);
  const [selectedAppId, setSelectedAppId] = useState('');
  const [sessionsByApp, setSessionsByApp] = useState({});
  const [messagesByApp, setMessagesByApp] = useState({});
  const [draft, setDraft] = useState('Show overdue tasks');
  const [loadingApps, setLoadingApps] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function loadApps() {
      try {
        const payload = await readJson(await fetch('/apps'));
        if (cancelled) {
          return;
        }
        setApps(payload.apps || []);
        setSelectedAppId(payload.default_app_id || payload.apps?.[0]?.app_id || '');
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load configured applications.');
        }
      } finally {
        if (!cancelled) {
          setLoadingApps(false);
        }
      }
    }

    loadApps();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedApp = useMemo(
    () => apps.find((item) => item.app_id === selectedAppId) || null,
    [apps, selectedAppId],
  );

  const visibleMessages = messagesByApp[selectedAppId] || [];

  async function ensureSession(appId) {
    if (sessionsByApp[appId]) {
      return sessionsByApp[appId];
    }
    const payload = await readJson(
      await fetch('/session/start', {
        method: 'POST',
        headers: { 'x-app-id': appId },
      }),
    );
    setSessionsByApp((current) => ({ ...current, [appId]: payload.session_id }));
    return payload.session_id;
  }

  async function handleRefreshApps() {
    setLoadingApps(true);
    setError('');
    try {
      const payload = await readJson(await fetch('/apps'));
      setApps(payload.apps || []);
      setSelectedAppId((current) => current || payload.default_app_id || payload.apps?.[0]?.app_id || '');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to refresh applications.');
    } finally {
      setLoadingApps(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const message = draft.trim();
    if (!selectedAppId || !message || sending) {
      return;
    }

    setError('');
    setSending(true);
    setDraft('');
    setMessagesByApp((current) => ({
      ...current,
      [selectedAppId]: [...(current[selectedAppId] || []), { role: 'user', text: message }],
    }));

    try {
      const sessionId = await ensureSession(selectedAppId);
      const events = await readNdjson(
        await fetch('/chat?rich=true', {
          method: 'POST',
          headers: appHeaders(selectedAppId),
          body: JSON.stringify({
            app_id: selectedAppId,
            session_id: sessionId,
            message,
          }),
        }),
      );
      const result = buildResultFromEvents(events);
      setMessagesByApp((current) => ({
        ...current,
        [selectedAppId]: [...(current[selectedAppId] || []), buildAssistantEntry(result)],
      }));
    } catch (err) {
      const messageText = err instanceof Error ? err.message : 'Chat request failed.';
      setError(messageText);
      setMessagesByApp((current) => ({
        ...current,
        [selectedAppId]: [
          ...(current[selectedAppId] || []),
          {
            role: 'assistant',
            text: messageText,
            metadata: { responseState: 'error' },
          },
        ],
      }));
    } finally {
      setSending(false);
    }
  }

  return (
    <main className="workspace-shell">
      <div className="workspace-shell__backdrop workspace-shell__backdrop--left" />
      <div className="workspace-shell__backdrop workspace-shell__backdrop--right" />

      <section className="chat-hero">
        <div className="chat-hero__copy">
          <div className="chat-hero__eyebrow">Multi-DB Chat</div>
          <h1>One chatbot, many application databases.</h1>
          <p>
            Pick an application, keep the conversation scoped to that app, and let FastMCP route every
            query through the same SQL guardrails.
          </p>
        </div>
        <div className="chat-hero__facts">
          <div className="chat-fact">
            <Database size={18} />
            <span>{apps.length || 0} configured apps</span>
          </div>
          <div className="chat-fact">
            <ShieldCheck size={18} />
            <span>App-scoped routing and policy enforcement</span>
          </div>
        </div>
      </section>

      <section className="chat-layout">
        <aside className="chat-sidebar">
          <div className="chat-panel-header">
            <div>
              <div className="panel__eyebrow">Scope</div>
              <h2>Application</h2>
            </div>
            <button
              type="button"
              className="ghost-button"
              onClick={handleRefreshApps}
              disabled={loadingApps}
            >
              <RefreshCw size={15} className={loadingApps ? 'is-spinning' : ''} />
              Refresh
            </button>
          </div>

          <label className="chat-field">
            <span>App ID</span>
            <select
              value={selectedAppId}
              onChange={(event) => setSelectedAppId(event.target.value)}
              disabled={loadingApps || apps.length === 0}
            >
              {apps.length === 0 ? <option value="">No applications found</option> : null}
              {apps.map((app) => (
                <option key={app.app_id} value={app.app_id}>
                  {app.display_name} ({app.app_id})
                </option>
              ))}
            </select>
          </label>

          {selectedApp ? (
            <div className="chat-app-card">
              <div className="chat-app-card__header">
                <Bot size={18} />
                <div>
                  <strong>{selectedApp.display_name}</strong>
                  <span>{selectedApp.app_id}</span>
                </div>
              </div>
              <p>{selectedApp.description || 'Configured application scope.'}</p>
              <dl className="chat-app-card__details">
                <div>
                  <dt>Domain</dt>
                  <dd>{selectedApp.domain_name || 'n/a'}</dd>
                </div>
                <div>
                  <dt>Allowed tables</dt>
                  <dd>{selectedApp.allowed_tables?.length || 0}</dd>
                </div>
                <div>
                  <dt>Session</dt>
                  <dd>{sessionsByApp[selectedAppId] || 'Starts on first message'}</dd>
                </div>
              </dl>
            </div>
          ) : (
            <div className="chat-placeholder">Load an application list to begin.</div>
          )}

          <div className="chat-guardrail-card">
            <h3>Guardrails</h3>
            <p>
              The selected app controls which tables are visible and whether writes are permitted. The UI
              only changes scope by switching the selected app.
            </p>
          </div>
        </aside>

        <section className="chat-main">
          <div className="chat-panel-header">
            <div>
              <div className="panel__eyebrow">Conversation</div>
              <h2>{selectedApp ? `${selectedApp.display_name} Chat` : 'App Chat'}</h2>
            </div>
            <div className="chat-status-pill">
              {sending ? 'Thinking' : selectedAppId ? `Bound to ${selectedAppId}` : 'Select an app'}
            </div>
          </div>

          <div className="chat-thread">
            {visibleMessages.length === 0 ? (
              <div className="chat-empty-state">
                <strong>Start with a real question.</strong>
                <p>
                  Try asking for a report, a status lookup, or a guarded update in the currently selected
                  application.
                </p>
                <div className="chat-suggestions">
                  <button type="button" onClick={() => setDraft('Show overdue tasks')}>
                    Show overdue tasks
                  </button>
                  <button type="button" onClick={() => setDraft('List pending work orders for Plant Alpha')}>
                    List pending work orders
                  </button>
                  <button type="button" onClick={() => setDraft('Create a new maintenance task')}>
                    Create a new maintenance task
                  </button>
                </div>
              </div>
            ) : (
              visibleMessages.map((message, index) => (
                <MessageBubble
                  key={`${selectedAppId}-${message.role}-${index}-${message.text}`}
                  message={message}
                />
              ))
            )}
          </div>

          <form className="chat-composer" onSubmit={handleSubmit}>
            <textarea
              rows={3}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={
                selectedApp
                  ? `Ask ${selectedApp.display_name} about its database...`
                  : 'Select an application first.'
              }
              disabled={!selectedAppId || sending}
            />
            <div className="chat-composer__footer">
              {error ? <div className="chat-error">{error}</div> : <div className="chat-hint">Rich results stream through the same widget chat API.</div>}
              <button type="submit" className="send-button" disabled={!selectedAppId || sending || !draft.trim()}>
                <SendHorizontal size={16} />
                Send
              </button>
            </div>
          </form>
        </section>
      </section>
    </main>
  );
}

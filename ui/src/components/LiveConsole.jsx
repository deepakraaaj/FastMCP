import React, { useMemo, useState } from 'react';
import {
  Bot,
  CheckCircle2,
  MessageSquareText,
  Play,
  RefreshCw,
  SendHorizontal,
  ShieldCheck,
  Workflow,
} from 'lucide-react';

const DEFAULT_WIDGET_FORM = {
  appId: 'fits',
  userId: 'u-demo-01',
  userName: 'Deepak',
  companyId: 'northfield',
  companyName: 'Northfield Energy',
  message: 'Show overdue tasks',
};

const DEFAULT_ADMIN_FORM = {
  actorId: 'platform-admin',
  role: 'platform_admin',
  tenantId: 'northfield',
  allowedAppIds: 'fits',
  authScopes: 'apps:*',
  adminToken: '',
  appId: '',
  channelId: 'web_chat',
  message: 'Show overdue maintenance tasks for Plant Alpha and summarize the backlog.',
};

const DEFAULT_FILTERS = {
  approvalsStatus: 'pending',
  approvalsAppId: '',
  proposalStatus: '',
  registrationState: '',
};

function splitCsv(value) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function encodeContext(value) {
  const bytes = new TextEncoder().encode(JSON.stringify(value));
  let binary = '';
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary);
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
  const events = text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line));
  const errorEvent = events.find((event) => event.type === 'error');
  if (errorEvent?.message) {
    throw new Error(errorEvent.message);
  }
  return events;
}

function lastResult(events) {
  return [...events].reverse().find((event) => event.type === 'result') ?? null;
}

function stateLabel(value) {
  return value.replace(/_/g, ' ');
}

function transcriptEntry(role, text, metadata = null) {
  return { role, text, metadata };
}

function ResultSummary({ title, result }) {
  if (!result) {
    return (
      <div className="live-summary live-summary--empty">
        <span>No response yet.</span>
      </div>
    );
  }

  const blocks = result.channel_response?.blocks ?? [];
  const diagnostics = result.channel_response?.diagnostics ?? {};
  const diagnosticsKeys = Object.keys(diagnostics);

  return (
    <div className="live-summary">
      <div className="live-summary__header">
        <strong>{title}</strong>
        <span className={`status-pill status-${result.response_state || result.channel_response?.state?.status || 'ok'}`}>
          {stateLabel(result.response_state || result.channel_response?.state?.status || 'ok')}
        </span>
      </div>
      <dl className="live-kv">
        <div>
          <dt>Session</dt>
          <dd>{result.session_id || 'n/a'}</dd>
        </div>
        <div>
          <dt>Mode</dt>
          <dd>{result.execution_mode || 'n/a'}</dd>
        </div>
        <div>
          <dt>Agent</dt>
          <dd>{result.agent_kind || 'n/a'}</dd>
        </div>
        <div>
          <dt>Route</dt>
          <dd>{result.orchestration_mode || result.route || 'n/a'}</dd>
        </div>
        <div>
          <dt>Capability</dt>
          <dd>{result.primary_capability_id || result.selected_capability_id || 'n/a'}</dd>
        </div>
        <div>
          <dt>Approval</dt>
          <dd>{result.approval_id || 'none'}</dd>
        </div>
        <div>
          <dt>Proposal</dt>
          <dd>{result.proposal_id || 'none'}</dd>
        </div>
      </dl>

      {blocks.length > 0 ? (
        <div className="live-block-list">
          {blocks.map((block) => (
            <div key={block.block_id || `${block.kind}-${block.title || block.body}`} className="live-block">
              <div className="live-block__title">
                <span>{block.title || stateLabel(block.kind)}</span>
                <small>{block.kind}</small>
              </div>
              {block.body ? <p>{block.body}</p> : null}
              {block.data && Object.keys(block.data).length > 0 ? (
                <pre>{JSON.stringify(block.data, null, 2)}</pre>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      {diagnosticsKeys.length > 0 ? (
        <details className="live-diagnostics">
          <summary>Diagnostics</summary>
          <pre>{JSON.stringify(diagnostics, null, 2)}</pre>
        </details>
      ) : null}
    </div>
  );
}

function TranscriptView({ title, transcript }) {
  return (
    <div className="live-transcript">
      <div className="live-transcript__header">
        <strong>{title}</strong>
        <span>{transcript.length / 2 || 0} turns</span>
      </div>
      <div className="live-transcript__stack">
        {transcript.length === 0 ? (
          <div className="live-transcript__empty">No interaction yet.</div>
        ) : (
          transcript.map((entry, index) => (
            <div key={`${entry.role}-${index}-${entry.text}`} className={`live-transcript__bubble role-${entry.role}`}>
              <div className="live-transcript__role">{entry.role === 'user' ? 'User' : 'Assistant'}</div>
              <p>{entry.text}</p>
              {entry.metadata?.response_state ? (
                <div className="live-transcript__meta">
                  state: {stateLabel(entry.metadata.response_state)}
                </div>
              ) : null}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function LifecycleCard({ title, items, emptyText, renderItem }) {
  return (
    <section className="live-card">
      <div className="live-card__header">
        <div>
          <div className="panel__eyebrow">Lifecycle</div>
          <h3>{title}</h3>
        </div>
      </div>
      <div className="lifecycle-list">
        {items.length === 0 ? <div className="lifecycle-list__empty">{emptyText}</div> : items.map(renderItem)}
      </div>
    </section>
  );
}

export default function LiveConsole() {
  const [widgetForm, setWidgetForm] = useState(DEFAULT_WIDGET_FORM);
  const [widgetSessionId, setWidgetSessionId] = useState('');
  const [widgetTranscript, setWidgetTranscript] = useState([]);
  const [widgetEvents, setWidgetEvents] = useState([]);
  const [widgetBusy, setWidgetBusy] = useState(false);
  const [widgetError, setWidgetError] = useState('');

  const [adminForm, setAdminForm] = useState(DEFAULT_ADMIN_FORM);
  const [adminSessionId, setAdminSessionId] = useState('');
  const [adminTranscript, setAdminTranscript] = useState([]);
  const [adminEvents, setAdminEvents] = useState([]);
  const [adminBusy, setAdminBusy] = useState(false);
  const [adminError, setAdminError] = useState('');

  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [approvals, setApprovals] = useState([]);
  const [proposals, setProposals] = useState([]);
  const [registrations, setRegistrations] = useState([]);
  const [lifecycleBusy, setLifecycleBusy] = useState(false);
  const [lifecycleError, setLifecycleError] = useState('');
  const [activityFeed, setActivityFeed] = useState([
    'Ask a widget question to exercise app-scoped chat.',
    'Use admin chat for cross-app analysis or agent proposals.',
    'Work the approval and registration queues from the live lifecycle panels.',
  ]);

  const widgetResult = useMemo(() => lastResult(widgetEvents), [widgetEvents]);
  const adminResult = useMemo(() => lastResult(adminEvents), [adminEvents]);

  const widgetHeaders = useMemo(
    () => ({
      'content-type': 'application/json',
      'x-app-id': widgetForm.appId,
      'x-user-context': encodeContext({
        user_id: widgetForm.userId || null,
        user_name: widgetForm.userName || null,
        company_id: widgetForm.companyId || null,
        company_name: widgetForm.companyName || null,
      }),
    }),
    [widgetForm],
  );

  const adminHeaders = useMemo(
    () => {
      const headers = {
        'content-type': 'application/json',
      };
      const adminToken = adminForm.adminToken.trim();
      if (adminToken) {
        headers.authorization = adminToken.toLowerCase().startsWith('bearer ')
          ? adminToken
          : `Bearer ${adminToken}`;
        return headers;
      }
      headers['x-admin-context'] = encodeContext({
        actor_id: adminForm.actorId,
        tenant_id: adminForm.tenantId || null,
        role: adminForm.role,
        auth_scopes: splitCsv(adminForm.authScopes),
        allowed_app_ids: splitCsv(adminForm.allowedAppIds),
      });
      return headers;
    },
    [adminForm],
  );

  function pushActivity(message) {
    setActivityFeed((current) => [message, ...current].slice(0, 8));
  }

  function updateWidgetForm(key, value) {
    setWidgetForm((current) => ({ ...current, [key]: value }));
  }

  function updateAdminForm(key, value) {
    setAdminForm((current) => ({ ...current, [key]: value }));
  }

  async function ensureWidgetSession() {
    if (widgetSessionId) {
      return widgetSessionId;
    }
    const response = await fetch('/session/start', {
      method: 'POST',
      headers: widgetHeaders,
    });
    const payload = await readJson(response);
    setWidgetSessionId(payload.session_id);
    pushActivity(`Started widget session ${payload.session_id} for ${payload.app_id}.`);
    return payload.session_id;
  }

  async function sendWidgetMessage() {
    setWidgetBusy(true);
    setWidgetError('');
    const message = widgetForm.message.trim();
    if (!message) {
      setWidgetBusy(false);
      setWidgetError('Widget message is required.');
      return;
    }

    try {
      const sessionId = await ensureWidgetSession();
      const response = await fetch('/chat?rich=true', {
        method: 'POST',
        headers: widgetHeaders,
        body: JSON.stringify({
          session_id: sessionId,
          app_id: widgetForm.appId,
          message,
        }),
      });
      const events = await readNdjson(response);
      const result = lastResult(events);
      setWidgetEvents(events);
      setWidgetTranscript((current) => [
        ...current,
        transcriptEntry('user', message),
        transcriptEntry('assistant', result?.message || 'No response returned.', result),
      ]);
      if (result?.session_id) {
        setWidgetSessionId(result.session_id);
      }
      pushActivity(`Widget chat completed in ${result?.orchestration_mode || 'answer'} mode.`);
    } catch (error) {
      setWidgetError(error instanceof Error ? error.message : 'Widget request failed.');
    } finally {
      setWidgetBusy(false);
    }
  }

  async function sendAdminMessage() {
    setAdminBusy(true);
    setAdminError('');
    const message = adminForm.message.trim();
    if (!message) {
      setAdminBusy(false);
      setAdminError('Admin message is required.');
      return;
    }

    try {
      const response = await fetch('/admin/chat?rich=true', {
        method: 'POST',
        headers: adminHeaders,
        body: JSON.stringify({
          session_id: adminSessionId || null,
          app_id: adminForm.appId || null,
          channel_id: adminForm.channelId || null,
          message,
        }),
      });
      const events = await readNdjson(response);
      const result = lastResult(events);
      setAdminEvents(events);
      setAdminTranscript((current) => [
        ...current,
        transcriptEntry('user', message),
        transcriptEntry('assistant', result?.message || 'No response returned.', result),
      ]);
      if (result?.session_id) {
        setAdminSessionId(result.session_id);
      }
      pushActivity(
        `Admin chat produced ${result?.orchestration_mode || 'unknown'} mode${result?.approval_id ? ` with approval ${result.approval_id}` : ''}.`,
      );
      await refreshLifecycle();
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : 'Admin request failed.');
    } finally {
      setAdminBusy(false);
    }
  }

  async function refreshLifecycle() {
    setLifecycleBusy(true);
    setLifecycleError('');
    try {
      const approvalParams = new URLSearchParams();
      if (filters.approvalsStatus) {
        approvalParams.set('status', filters.approvalsStatus);
      }
      if (filters.approvalsAppId) {
        approvalParams.set('app_id', filters.approvalsAppId);
      }
      const proposalParams = new URLSearchParams();
      if (filters.proposalStatus) {
        proposalParams.set('status', filters.proposalStatus);
      }
      const registrationParams = new URLSearchParams();
      if (filters.registrationState) {
        registrationParams.set('registry_state', filters.registrationState);
      }

      const [approvalPayload, proposalPayload, registrationPayload] = await Promise.all([
        fetch(`/admin/approvals?${approvalParams.toString()}`, { headers: adminHeaders }).then(readJson),
        fetch(`/admin/agents/proposals?${proposalParams.toString()}`, { headers: adminHeaders }).then(readJson),
        fetch(`/admin/agents/registrations?${registrationParams.toString()}`, { headers: adminHeaders }).then(readJson),
      ]);

      setApprovals(approvalPayload.lifecycle?.approval_queue || []);
      setProposals(proposalPayload.lifecycle?.proposal_drafts || []);
      setRegistrations(registrationPayload.lifecycle?.registration_records || []);
      pushActivity('Lifecycle queues refreshed from the live admin HTTP surface.');
    } catch (error) {
      setLifecycleError(error instanceof Error ? error.message : 'Failed to load lifecycle data.');
    } finally {
      setLifecycleBusy(false);
    }
  }

  async function decideApproval(approvalId, decision) {
    setLifecycleBusy(true);
    setLifecycleError('');
    try {
      const payload = await fetch(`/admin/approvals/${approvalId}/decision`, {
        method: 'POST',
        headers: adminHeaders,
        body: JSON.stringify({
          app_id: filters.approvalsAppId || adminForm.appId || null,
          session_id: adminSessionId || null,
          decision,
        }),
      }).then(readJson);
      pushActivity(`Approval ${approvalId} marked ${payload.lifecycle?.approval_request?.status || decision}.`);
      await refreshLifecycle();
    } catch (error) {
      setLifecycleError(error instanceof Error ? error.message : 'Approval decision failed.');
      setLifecycleBusy(false);
    }
  }

  async function resumeApproval(approvalId) {
    setLifecycleBusy(true);
    setLifecycleError('');
    try {
      const payload = await fetch(`/admin/approvals/${approvalId}/resume`, {
        method: 'POST',
        headers: adminHeaders,
        body: JSON.stringify({
          app_id: filters.approvalsAppId || adminForm.appId || null,
          session_id: adminSessionId || null,
        }),
      }).then(readJson);
      pushActivity(`Approval ${approvalId} resumed through ${payload.route}.`);
      await refreshLifecycle();
    } catch (error) {
      setLifecycleError(error instanceof Error ? error.message : 'Resume failed.');
      setLifecycleBusy(false);
    }
  }

  async function registerProposal(proposalId) {
    setLifecycleBusy(true);
    setLifecycleError('');
    try {
      const payload = await fetch(`/admin/agents/proposals/${proposalId}/register`, {
        method: 'POST',
        headers: adminHeaders,
        body: JSON.stringify({
          app_id: adminForm.appId || filters.approvalsAppId || null,
        }),
      }).then(readJson);
      pushActivity(
        `Proposal ${proposalId} registered as ${payload.lifecycle?.registration_record?.agent_id || 'a runtime agent'}.`,
      );
      await refreshLifecycle();
    } catch (error) {
      setLifecycleError(error instanceof Error ? error.message : 'Proposal registration failed.');
      setLifecycleBusy(false);
    }
  }

  async function activateRegistration(registrationId) {
    setLifecycleBusy(true);
    setLifecycleError('');
    try {
      const payload = await fetch(`/admin/agents/registrations/${registrationId}/activate`, {
        method: 'POST',
        headers: adminHeaders,
        body: JSON.stringify({
          app_id: adminForm.appId || filters.approvalsAppId || null,
        }),
      }).then(readJson);
      pushActivity(
        `Registration ${registrationId} is now ${payload.lifecycle?.registration_record?.registry_state || 'active'}.`,
      );
      await refreshLifecycle();
    } catch (error) {
      setLifecycleError(error instanceof Error ? error.message : 'Registration activation failed.');
      setLifecycleBusy(false);
    }
  }

  return (
    <section className="panel live-console">
      <div className="panel__header">
        <div>
          <div className="panel__eyebrow">Interactive Surface</div>
          <h2>Live runtime console</h2>
        </div>
        <p>
          This panel talks to the actual widget and admin HTTP surfaces. Use it to drive app chat, admin chat,
          approvals, proposal registration, and activation from one browser view.
        </p>
      </div>

      <div className="live-plan-grid">
        <div className="live-plan-card">
          <ShieldCheck size={18} strokeWidth={2.1} />
          <div>
            <strong>1. App chat</strong>
            <p>Start with the widget panel to verify single-app scope and direct report/workflow routing.</p>
          </div>
        </div>
        <div className="live-plan-card">
          <Bot size={18} strokeWidth={2.1} />
          <div>
            <strong>2. Admin chat</strong>
            <p>Use cross-app or proposal prompts to hit approval-required and draft-first lifecycle paths.</p>
          </div>
        </div>
        <div className="live-plan-card">
          <Workflow size={18} strokeWidth={2.1} />
          <div>
            <strong>3. Lifecycle</strong>
            <p>Refresh the queues, approve or reject, register proposals, then activate registrations.</p>
          </div>
        </div>
      </div>

      <div className="live-console__grid">
        <section className="live-card">
          <div className="live-card__header">
            <div>
              <div className="panel__eyebrow">Widget Chat</div>
              <h3>App-scoped interaction</h3>
            </div>
            <div className="live-card__actions">
              <button type="button" className="action-button" onClick={ensureWidgetSession} disabled={widgetBusy}>
                <Play size={15} />
                Start session
              </button>
              <button type="button" className="action-button action-button--primary" onClick={sendWidgetMessage} disabled={widgetBusy}>
                <SendHorizontal size={15} />
                Send
              </button>
            </div>
          </div>

          <div className="form-grid">
            <label>
              App ID
              <input value={widgetForm.appId} onChange={(event) => updateWidgetForm('appId', event.target.value)} />
            </label>
            <label>
              User ID
              <input value={widgetForm.userId} onChange={(event) => updateWidgetForm('userId', event.target.value)} />
            </label>
            <label>
              User name
              <input value={widgetForm.userName} onChange={(event) => updateWidgetForm('userName', event.target.value)} />
            </label>
            <label>
              Company ID
              <input value={widgetForm.companyId} onChange={(event) => updateWidgetForm('companyId', event.target.value)} />
            </label>
          </div>

          <label className="form-field form-field--full">
            Message
            <textarea
              rows={3}
              value={widgetForm.message}
              onChange={(event) => updateWidgetForm('message', event.target.value)}
            />
          </label>

          <div className="live-meta-strip">
            <span>Session: {widgetSessionId || 'not started'}</span>
            <span>Transport: /session/start + /chat</span>
          </div>

          {widgetError ? <div className="live-error">{widgetError}</div> : null}
          <TranscriptView title="Widget transcript" transcript={widgetTranscript} />
          <ResultSummary title="Widget response" result={widgetResult} />
        </section>

        <section className="live-card">
          <div className="live-card__header">
            <div>
              <div className="panel__eyebrow">Admin Chat</div>
              <h3>Privileged interaction</h3>
            </div>
            <div className="live-card__actions">
              <button type="button" className="action-button action-button--primary" onClick={sendAdminMessage} disabled={adminBusy}>
                <MessageSquareText size={15} />
                Send admin chat
              </button>
            </div>
          </div>

          <div className="form-grid">
            <label>
              Actor ID
              <input value={adminForm.actorId} onChange={(event) => updateAdminForm('actorId', event.target.value)} />
            </label>
            <label>
              Role
              <select value={adminForm.role} onChange={(event) => updateAdminForm('role', event.target.value)}>
                <option value="app_admin">app_admin</option>
                <option value="platform_admin">platform_admin</option>
                <option value="service">service</option>
              </select>
            </label>
            <label>
              Tenant ID
              <input value={adminForm.tenantId} onChange={(event) => updateAdminForm('tenantId', event.target.value)} />
            </label>
            <label>
              Channel ID
              <input value={adminForm.channelId} onChange={(event) => updateAdminForm('channelId', event.target.value)} />
            </label>
            <label className="form-field--full">
              Admin bearer token
              <input
                value={adminForm.adminToken}
                onChange={(event) => updateAdminForm('adminToken', event.target.value)}
                placeholder="Optional. Leave empty to use development x-admin-context."
              />
            </label>
            <label className="form-field--full">
              Allowed app IDs
              <input
                value={adminForm.allowedAppIds}
                onChange={(event) => updateAdminForm('allowedAppIds', event.target.value)}
                placeholder="fits"
              />
            </label>
            <label className="form-field--full">
              Auth scopes
              <input
                value={adminForm.authScopes}
                onChange={(event) => updateAdminForm('authScopes', event.target.value)}
                placeholder="apps:*"
              />
            </label>
            <label>
              Requested app
              <input value={adminForm.appId} onChange={(event) => updateAdminForm('appId', event.target.value)} placeholder="optional" />
            </label>
          </div>

          <label className="form-field form-field--full">
            Message
            <textarea
              rows={4}
              value={adminForm.message}
              onChange={(event) => updateAdminForm('message', event.target.value)}
            />
          </label>

          <div className="live-meta-strip">
            <span>Session: {adminSessionId || 'auto-start on first message'}</span>
            <span>Transport: /admin/chat</span>
          </div>

          {adminError ? <div className="live-error">{adminError}</div> : null}
          <TranscriptView title="Admin transcript" transcript={adminTranscript} />
          <ResultSummary title="Admin response" result={adminResult} />
        </section>
      </div>

      <div className="live-console__toolbar">
        <div className="live-card__actions">
          <button type="button" className="action-button action-button--primary" onClick={refreshLifecycle} disabled={lifecycleBusy}>
            <RefreshCw size={15} />
            Refresh lifecycle queues
          </button>
        </div>
        <div className="toolbar-filters">
          <label>
            Approval status
            <select
              value={filters.approvalsStatus}
              onChange={(event) => setFilters((current) => ({ ...current, approvalsStatus: event.target.value }))}
            >
              <option value="">all</option>
              <option value="pending">pending</option>
              <option value="approved">approved</option>
              <option value="rejected">rejected</option>
              <option value="cancelled">cancelled</option>
            </select>
          </label>
          <label>
            Approval app
            <input
              value={filters.approvalsAppId}
              onChange={(event) => setFilters((current) => ({ ...current, approvalsAppId: event.target.value }))}
              placeholder="optional"
            />
          </label>
          <label>
            Proposal status
            <input
              value={filters.proposalStatus}
              onChange={(event) => setFilters((current) => ({ ...current, proposalStatus: event.target.value }))}
              placeholder="optional"
            />
          </label>
          <label>
            Registration state
            <input
              value={filters.registrationState}
              onChange={(event) => setFilters((current) => ({ ...current, registrationState: event.target.value }))}
              placeholder="optional"
            />
          </label>
        </div>
      </div>

      {lifecycleError ? <div className="live-error">{lifecycleError}</div> : null}

      <div className="live-console__grid live-console__grid--lifecycle">
        <LifecycleCard
          title="Approvals"
          items={approvals}
          emptyText="No approvals loaded for the current filter."
          renderItem={(approval) => (
            <article key={approval.approval_id} className="lifecycle-item">
              <div className="lifecycle-item__header">
                <strong>{approval.approval_id}</strong>
                <span className={`status-pill status-${approval.status}`}>{approval.status}</span>
              </div>
              <p>{approval.request_reason}</p>
              <div className="lifecycle-item__meta">
                <span>scope: {approval.scope_type}</span>
                <span>apps: {(approval.app_ids || []).join(', ') || 'none'}</span>
              </div>
              <div className="lifecycle-item__actions">
                {approval.status === 'pending' ? (
                  <>
                    <button type="button" className="action-button action-button--primary" onClick={() => decideApproval(approval.approval_id, 'approve')}>
                      <CheckCircle2 size={15} />
                      Approve
                    </button>
                    <button type="button" className="action-button" onClick={() => decideApproval(approval.approval_id, 'reject')}>
                      Reject
                    </button>
                  </>
                ) : null}
                {approval.status === 'approved' && approval.scope_type === 'execution' ? (
                  <button type="button" className="action-button" onClick={() => resumeApproval(approval.approval_id)}>
                    <Play size={15} />
                    Resume execution
                  </button>
                ) : null}
              </div>
            </article>
          )}
        />

        <LifecycleCard
          title="Proposal Drafts"
          items={proposals}
          emptyText="No proposal drafts loaded for the current filter."
          renderItem={(proposal) => (
            <article key={proposal.proposal_id} className="lifecycle-item">
              <div className="lifecycle-item__header">
                <strong>{proposal.display_name}</strong>
                <span className={`status-pill status-${proposal.status}`}>{proposal.status}</span>
              </div>
              <p>{proposal.problem_statement}</p>
              <div className="lifecycle-item__meta">
                <span>kind: {proposal.proposed_agent_kind}</span>
                <span>apps: {(proposal.target_app_ids || []).join(', ') || 'none'}</span>
              </div>
              <div className="lifecycle-item__actions">
                {proposal.status === 'approved_for_registration' ? (
                  <button type="button" className="action-button action-button--primary" onClick={() => registerProposal(proposal.proposal_id)}>
                    Register
                  </button>
                ) : null}
              </div>
            </article>
          )}
        />

        <LifecycleCard
          title="Registrations"
          items={registrations}
          emptyText="No registrations loaded for the current filter."
          renderItem={(registration) => (
            <article key={registration.registration_id} className="lifecycle-item">
              <div className="lifecycle-item__header">
                <strong>{registration.agent_id}</strong>
                <span className={`status-pill status-${registration.registry_state}`}>{registration.registry_state}</span>
              </div>
              <p>Registration {registration.registration_id}</p>
              <div className="lifecycle-item__meta">
                <span>version: {registration.version}</span>
                <span>proposal: {registration.proposal_id}</span>
              </div>
              <div className="lifecycle-item__actions">
                {registration.registry_state === 'registered' ? (
                  <button type="button" className="action-button action-button--primary" onClick={() => activateRegistration(registration.registration_id)}>
                    Activate
                  </button>
                ) : null}
              </div>
            </article>
          )}
        />
      </div>

      <section className="live-card live-card--activity">
        <div className="live-card__header">
          <div>
            <div className="panel__eyebrow">Interaction Plan</div>
            <h3>Suggested end-to-end walkthrough</h3>
          </div>
        </div>
        <div className="activity-feed">
          {activityFeed.map((item, index) => (
            <div key={`${item}-${index}`} className="activity-feed__item">
              {item}
            </div>
          ))}
        </div>
      </section>
    </section>
  );
}

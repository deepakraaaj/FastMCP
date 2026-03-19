import React, { startTransition, useState } from 'react';
import ReactFlow, { Background, Controls, MarkerType } from 'reactflow';
import 'reactflow/dist/style.css';
import {
  Activity,
  ArrowRight,
  Bot,
  CheckCircle2,
  CircleAlert,
  Clock3,
  Database,
  FileStack,
  GitBranch,
  Lock,
  MessageSquare,
  Scale,
  ShieldCheck,
  Sparkles,
  Users,
  Workflow,
} from 'lucide-react';

import LiveConsole from './components/LiveConsole';
import SystemNode from './nodes/SystemNode';

const nodeTypes = { system: SystemNode };

const GRAPH_LAYOUT = {
  entry: { x: 20, y: 156 },
  context: { x: 250, y: 40 },
  policy: { x: 250, y: 272 },
  planner: { x: 530, y: 156 },
  router: { x: 810, y: 40 },
  approval: { x: 810, y: 272 },
  execution: { x: 1090, y: 40 },
  heavy: { x: 1090, y: 272 },
  formatter: { x: 1370, y: 40 },
  audit: { x: 1370, y: 272 },
  lifecycle: { x: 1370, y: 504 },
};

const NODE_META = {
  entry: { eyebrow: 'Surface', title: 'User Entry', icon: Activity, source: true, target: false },
  context: { eyebrow: 'Identity', title: 'Request Context', icon: Users },
  policy: { eyebrow: 'Enforcement', title: 'Policy Envelope', icon: ShieldCheck },
  planner: { eyebrow: 'Planning', title: 'Intent Planner', icon: Sparkles },
  router: { eyebrow: 'Dispatch', title: 'Capability Router', icon: GitBranch },
  approval: { eyebrow: 'Control', title: 'Approval Gate', icon: Scale },
  execution: { eyebrow: 'Execution', title: 'Guarded Execution', icon: Database },
  heavy: { eyebrow: 'Escalation', title: 'Heavy Agent', icon: Bot },
  formatter: { eyebrow: 'Presentation', title: 'Formatter Layer', icon: MessageSquare },
  audit: { eyebrow: 'Observability', title: 'Audit and Trace', icon: FileStack },
  lifecycle: { eyebrow: 'Lifecycle', title: 'Agent Lifecycle', icon: Workflow, source: false },
};

const SCENARIOS = {
  app_chat: {
    label: 'App Chat',
    badge: 'Single-app enforcement',
    heading: 'App chat stays inside FITS from the first planning step.',
    summary:
      'The operator asks for overdue maintenance work. The request is bound to FITS before reasoning, so the planner cannot widen scope or reach another application.',
    graph: {
      entry: {
        detail: 'widget session ws_fits_204',
        footnote: 'origin: app_chat',
        state: 'active',
        stateLabel: 'Live request',
      },
      context: {
        detail: 'actor: ops.jules · tenant: northfield',
        footnote: 'app_id comes from trusted channel context',
        state: 'success',
        stateLabel: 'Bound',
      },
      policy: {
        detail: 'apps=[fits] · capabilities=report, workflow, sql.read',
        footnote: 'cross-app and heavy execution disabled',
        state: 'success',
        stateLabel: 'Locked',
      },
      planner: {
        detail: 'intent=report_query · fallback=clarify',
        footnote: 'cannot choose capabilities outside envelope',
        state: 'active',
        stateLabel: 'Planning',
      },
      router: {
        detail: 'selected report.overdue_work_orders',
        footnote: 'registry choice stays inside fits manifest',
        state: 'success',
        stateLabel: 'Resolved',
      },
      approval: {
        detail: 'no approval needed for read-only app request',
        footnote: 'still visible as a control boundary',
        state: 'idle',
        stateLabel: 'Bypassed',
      },
      execution: {
        detail: 'SELECT-only query with plant filter attached',
        footnote: 'policy checks happen before SQL runs',
        state: 'success',
        stateLabel: 'Executed',
      },
      heavy: {
        detail: 'cross-db reasoning unavailable in app mode',
        footnote: 'user must move to admin console for this path',
        state: 'muted',
        stateLabel: 'Blocked',
      },
      formatter: {
        detail: 'widget cards + concise evidence block',
        footnote: 'no raw SQL or trace dump to end user',
        state: 'success',
        stateLabel: 'Rendered',
      },
      audit: {
        detail: 'trace_id, plan, capability, visibility captured',
        footnote: 'audit survives even when user sees simple output',
        state: 'success',
        stateLabel: 'Recorded',
      },
      lifecycle: {
        detail: 'no agent proposal activity in this flow',
        footnote: 'draft lifecycle remains dormant',
        state: 'muted',
        stateLabel: 'Dormant',
      },
    },
    activeEdges: [
      'entry-context',
      'context-policy',
      'policy-planner',
      'planner-router',
      'router-execution',
      'execution-formatter',
      'execution-audit',
      'formatter-audit',
    ],
    envelope: [
      ['Mode', 'app_chat'],
      ['Allowed apps', 'FITS only'],
      ['Role', 'tenant operator'],
      ['Capability set', 'reports, workflows, sql.read'],
      ['Escalation', 'disabled'],
      ['Visibility', 'widget-safe summary only'],
    ],
    agents: [
      { name: 'App Scoped Chat Agent', state: 'active' },
      { name: 'Schema Intelligence Agent', state: 'standby' },
      { name: 'Admin Orchestration Agent', state: 'off' },
    ],
    approvals: [
      {
        title: 'Execution policy',
        status: 'clear',
        body: 'Read-only request stays inside FITS. No manual approval step is needed.',
      },
      {
        title: 'Cross-app access',
        status: 'blocked',
        body: 'Blocked by design in app mode. Prompt text cannot widen the app set.',
      },
    ],
    transcriptTitle: 'FITS Widget Chat',
    transcript: [
      { role: 'user', text: 'Show overdue maintenance tasks for Plant Alpha.' },
      {
        role: 'assistant',
        text: 'I can answer from FITS only. Pulling the overdue work-order report for Plant Alpha now.',
      },
      {
        role: 'assistant',
        text: '12 tasks are overdue. Three are safety-critical and two are waiting on parts.',
        emphasis: true,
      },
    ],
    timeline: [
      { title: 'Request context built', detail: 'tenant, role, app, session, and channel captured', state: 'done' },
      { title: 'Envelope locked', detail: 'single-app scope attached before planning', state: 'done' },
      { title: 'Capability chosen', detail: 'report.overdue_work_orders outranks freeform SQL', state: 'done' },
      { title: 'Formatter applied', detail: 'widget-safe summary with evidence tags', state: 'done' },
    ],
    outputs: [
      { title: 'Answer block', detail: 'Concise maintenance summary with plant-level counts.', icon: CheckCircle2 },
      { title: 'Evidence block', detail: 'Visible source tags, but no raw SQL or planner trace.', icon: Lock },
      { title: 'Guardrail cue', detail: 'The UI states clearly that this conversation is scoped to FITS.', icon: ShieldCheck },
    ],
  },
  admin_cross_app: {
    label: 'Admin Cross-App',
    badge: 'Privileged orchestration',
    heading: 'Admin chat can coordinate across apps, but only through explicit privilege and visible escalation.',
    summary:
      'The admin asks for a cross-system delay analysis. The request enters privileged mode, the envelope allows multiple apps, and the heavy agent becomes a visible staged execution path.',
    graph: {
      entry: {
        detail: 'admin console session adm_18',
        footnote: 'origin: admin_chat',
        state: 'active',
        stateLabel: 'Live request',
      },
      context: {
        detail: 'actor: anika.r · role: platform_admin',
        footnote: 'trusted auth grants admin console access',
        state: 'success',
        stateLabel: 'Verified',
      },
      policy: {
        detail: 'apps=[fits, vts, warehouse] · cross-db=true',
        footnote: 'privilege is explicit and auditable',
        state: 'warning',
        stateLabel: 'Privileged',
      },
      planner: {
        detail: 'intent=correlate_delay_causes across 3 systems',
        footnote: 'planner marks request as structurally heavy',
        state: 'active',
        stateLabel: 'Escalating',
      },
      router: {
        detail: 'splits work into approved per-app capability calls',
        footnote: 'registry remains the dispatch source of truth',
        state: 'warning',
        stateLabel: 'Compiled',
      },
      approval: {
        detail: 'cross-app reasoning requires explicit logged approval',
        footnote: 'manual review can be auto-cleared only by policy rule',
        state: 'warning',
        stateLabel: 'Visible gate',
      },
      execution: {
        detail: 'staged read paths across FITS, VTS, and warehouse',
        footnote: 'each underlying action still uses guarded tools',
        state: 'warning',
        stateLabel: 'Running',
      },
      heavy: {
        detail: 'heavy cross-db agent coordinates reconciliation',
        footnote: 'user sees the escalation instead of silent background branching',
        state: 'active',
        stateLabel: 'Escalated',
      },
      formatter: {
        detail: 'admin dashboard cards + metrics + trace summary',
        footnote: 'higher-visibility output profile than widget chat',
        state: 'success',
        stateLabel: 'Rendered',
      },
      audit: {
        detail: 'stores envelope, approval, heavy-agent, and tool trace',
        footnote: 'privileged mode creates stronger evidence requirements',
        state: 'success',
        stateLabel: 'Recorded',
      },
      lifecycle: {
        detail: 'proposal path available if unmet pattern repeats',
        footnote: 'not active in this request',
        state: 'idle',
        stateLabel: 'Watching',
      },
    },
    activeEdges: [
      'entry-context',
      'context-policy',
      'policy-planner',
      'planner-approval',
      'planner-router',
      'approval-heavy',
      'heavy-execution',
      'router-execution',
      'execution-formatter',
      'execution-audit',
      'formatter-audit',
    ],
    envelope: [
      ['Mode', 'admin_chat'],
      ['Allowed apps', 'FITS, VTS, warehouse'],
      ['Role', 'platform admin'],
      ['Capability set', 'reports, workflows, sql.read, heavy_agent'],
      ['Escalation', 'allowed with trace'],
      ['Visibility', 'admin diagnostics + audit summary'],
    ],
    agents: [
      { name: 'Admin Orchestration Agent', state: 'active' },
      { name: 'Heavy Cross-DB Agent', state: 'active' },
      { name: 'App Scoped Chat Agent', state: 'shadowed' },
    ],
    approvals: [
      {
        title: 'Cross-app execution',
        status: 'pending',
        body: 'Approval request AR-4108 waits for policy-confirmed clearance before the heavy run begins.',
      },
      {
        title: 'Audit visibility',
        status: 'clear',
        body: 'Admin profile may see plan and capability trace, but not raw secrets or connection material.',
      },
    ],
    transcriptTitle: 'Admin Orchestration Console',
    transcript: [
      { role: 'user', text: 'Why are service visits delayed across FITS and VTS this week?' },
      {
        role: 'assistant',
        text: 'This needs privileged cross-app analysis. I am opening a heavy reconciliation path with explicit approval tracking.',
      },
      {
        role: 'assistant',
        text: 'Preliminary signal: inventory shortages explain 43% of the delays, with a separate VTS dispatch bottleneck in the east region.',
        emphasis: true,
      },
    ],
    timeline: [
      { title: 'Admin context verified', detail: 'request moves into privileged admin_chat mode', state: 'done' },
      { title: 'Heavy plan compiled', detail: 'planner selects staged reconciliation instead of direct answer', state: 'done' },
      { title: 'Approval event created', detail: 'AR-4108 is logged before execution expands', state: 'running' },
      { title: 'Cross-app output rendered', detail: 'dashboard cards include evidence and drift notes', state: 'queued' },
    ],
    outputs: [
      { title: 'Escalation banner', detail: 'Visible notice that a heavy cross-db agent is now running.', icon: CircleAlert },
      { title: 'Admin dashboard cards', detail: 'Comparative metrics across apps, plus degraded-source markers if needed.', icon: Database },
      { title: 'Audit detail panel', detail: 'Approval id, trace id, and plan summary are visible to admins.', icon: FileStack },
    ],
  },
  agent_proposal: {
    label: 'Agent Proposal',
    badge: 'Draft-first lifecycle',
    heading: 'Repeated unmet demand becomes a draft proposal, never an automatic agent activation.',
    summary:
      'The admin keeps asking for a recurring reconciliation pattern that the current agent set handles poorly. The planner can propose a new agent, but only as a reviewable draft with registration and activation still pending.',
    graph: {
      entry: {
        detail: 'admin console session adm_32',
        footnote: 'request pattern repeats across weeks',
        state: 'active',
        stateLabel: 'Live request',
      },
      context: {
        detail: 'actor: anika.r · role: platform_admin',
        footnote: 'proposal rights come from trusted role',
        state: 'success',
        stateLabel: 'Verified',
      },
      policy: {
        detail: 'proposal rights=true · activation rights=false',
        footnote: 'envelope allows draft creation only',
        state: 'warning',
        stateLabel: 'Constrained',
      },
      planner: {
        detail: 'intent=propose_new_agent for recurring cross-domain pattern',
        footnote: 'planner chooses proposal instead of unsafe overfitting',
        state: 'active',
        stateLabel: 'Proposing',
      },
      router: {
        detail: 'no new runtime capability is dispatched yet',
        footnote: 'current tools remain unchanged until approval',
        state: 'muted',
        stateLabel: 'Held',
      },
      approval: {
        detail: 'draft review required before registration or activation',
        footnote: 'approval boundary is mandatory, not advisory',
        state: 'active',
        stateLabel: 'In review',
      },
      execution: {
        detail: 'existing safe capabilities can still answer partially',
        footnote: 'proposal path is separate from normal execution',
        state: 'idle',
        stateLabel: 'Optional',
      },
      heavy: {
        detail: 'heavy agent may still be used for current request only',
        footnote: 'that does not imply a new permanent agent exists',
        state: 'idle',
        stateLabel: 'Temporary',
      },
      formatter: {
        detail: 'shows proposal summary, draft schema, and approval state',
        footnote: 'UI must make draft status obvious to the user',
        state: 'success',
        stateLabel: 'Rendered',
      },
      audit: {
        detail: 'proposal id, reviewer, and state transitions recorded',
        footnote: 'every lifecycle step is attributable',
        state: 'success',
        stateLabel: 'Recorded',
      },
      lifecycle: {
        detail: 'draft -> approved -> registered -> activated',
        footnote: 'registration and activation are separate transitions',
        state: 'active',
        stateLabel: 'Drafting',
      },
    },
    activeEdges: [
      'entry-context',
      'context-policy',
      'policy-planner',
      'planner-approval',
      'approval-lifecycle',
      'formatter-audit',
      'approval-audit',
    ],
    envelope: [
      ['Mode', 'admin_chat'],
      ['Allowed apps', 'platform scope for review only'],
      ['Role', 'platform admin'],
      ['Capability set', 'proposal drafting, review, existing safe tools'],
      ['Escalation', 'proposal only, no auto-activation'],
      ['Visibility', 'draft spec + lifecycle state'],
    ],
    agents: [
      { name: 'Agent Proposal Agent', state: 'active' },
      { name: 'Admin Orchestration Agent', state: 'active' },
      { name: 'Heavy Cross-DB Agent', state: 'standby' },
    ],
    approvals: [
      {
        title: 'Draft proposal PR-204',
        status: 'pending',
        body: 'Draft spec generated for a dispatch-reconciliation agent. Registration is blocked until review completes.',
      },
      {
        title: 'Activation policy',
        status: 'blocked',
        body: 'Activation remains disabled even after registration until a second explicit decision is recorded.',
      },
    ],
    transcriptTitle: 'Agent Lifecycle Review',
    transcript: [
      { role: 'user', text: 'We keep doing the same cross-app dispatch reconciliation. Should this become its own agent?' },
      {
        role: 'assistant',
        text: 'Yes, this pattern is recurring. I created a draft proposal with scope, allowed sources, and review requirements.',
      },
      {
        role: 'assistant',
        text: 'Status: Draft only. Nothing has been registered or activated yet.',
        emphasis: true,
      },
    ],
    timeline: [
      { title: 'Pattern detected', detail: 'planner sees repeated unmet cross-domain demand', state: 'done' },
      { title: 'Draft spec created', detail: 'proposal includes scope, tools, risks, and review notes', state: 'done' },
      { title: 'Registration held', detail: 'awaits admin review and audit completion', state: 'running' },
      { title: 'Activation unavailable', detail: 'a second explicit lifecycle step is still required', state: 'queued' },
    ],
    outputs: [
      { title: 'Draft proposal card', detail: 'Shows proposed agent purpose, allowed apps, and operating limits.', icon: Workflow },
      { title: 'Approval queue state', detail: 'Review state stays visible until someone approves or rejects it.', icon: Clock3 },
      { title: 'Lifecycle ladder', detail: 'Registration and activation are rendered as separate steps.', icon: ArrowRight },
    ],
  },
};

const EDGE_SEQUENCE = [
  ['entry-context', 'entry', 'context'],
  ['context-policy', 'context', 'policy'],
  ['policy-planner', 'policy', 'planner'],
  ['planner-router', 'planner', 'router'],
  ['planner-approval', 'planner', 'approval'],
  ['router-execution', 'router', 'execution'],
  ['approval-heavy', 'approval', 'heavy'],
  ['heavy-execution', 'heavy', 'execution'],
  ['execution-formatter', 'execution', 'formatter'],
  ['execution-audit', 'execution', 'audit'],
  ['formatter-audit', 'formatter', 'audit'],
  ['approval-lifecycle', 'approval', 'lifecycle'],
  ['approval-audit', 'approval', 'audit'],
];

function buildNodes(scenario) {
  return Object.entries(NODE_META).map(([id, meta]) => ({
    id,
    type: 'system',
    position: GRAPH_LAYOUT[id],
    draggable: false,
    selectable: false,
    data: {
      ...meta,
      ...scenario.graph[id],
      emphasis: scenario.graph[id].state === 'active' || scenario.graph[id].state === 'warning',
    },
  }));
}

function buildEdges(scenario) {
  return EDGE_SEQUENCE.map(([id, source, target]) => {
    const active = scenario.activeEdges.includes(id);
    return {
      id,
      source,
      target,
      animated: active,
      markerEnd: { type: MarkerType.ArrowClosed },
      className: active ? 'flow-edge is-active' : 'flow-edge',
      style: active ? { strokeWidth: 2.75 } : { strokeWidth: 1.5 },
    };
  });
}

function ScenarioButton({ isActive, label, badge, onClick }) {
  return (
    <button className={`scenario-button ${isActive ? 'is-active' : ''}`} onClick={onClick}>
      <span className="scenario-button__label">{label}</span>
      <span className="scenario-button__badge">{badge}</span>
    </button>
  );
}

function AgentPill({ name, state }) {
  return (
    <div className={`agent-pill state-${state}`}>
      <span className="agent-pill__name">{name}</span>
      <span className="agent-pill__state">{state.replace('_', ' ')}</span>
    </div>
  );
}

function ApprovalCard({ title, status, body }) {
  return (
    <div className={`approval-card status-${status}`}>
      <div className="approval-card__header">
        <strong>{title}</strong>
        <span>{status}</span>
      </div>
      <p>{body}</p>
    </div>
  );
}

function TranscriptBubble({ role, text, emphasis }) {
  return (
    <div className={`transcript-bubble role-${role} ${emphasis ? 'is-emphasis' : ''}`}>
      <div className="transcript-bubble__role">{role === 'user' ? 'User' : 'Assistant'}</div>
      <p>{text}</p>
    </div>
  );
}

function TimelineItem({ title, detail, state }) {
  return (
    <div className={`timeline-item state-${state}`}>
      <div className="timeline-item__bullet" />
      <div>
        <div className="timeline-item__title">{title}</div>
        <div className="timeline-item__detail">{detail}</div>
      </div>
    </div>
  );
}

function OutputCard({ title, detail, icon: Icon }) {
  return (
    <div className="output-card">
      <div className="output-card__icon">
        <Icon size={18} strokeWidth={2.1} />
      </div>
      <div>
        <div className="output-card__title">{title}</div>
        <div className="output-card__detail">{detail}</div>
      </div>
    </div>
  );
}

export default function App() {
  const [scenarioKey, setScenarioKey] = useState('app_chat');
  const scenario = SCENARIOS[scenarioKey];
  const nodes = buildNodes(scenario);
  const edges = buildEdges(scenario);

  return (
    <div className="app-shell">
      <div className="app-shell__backdrop app-shell__backdrop--left" />
      <div className="app-shell__backdrop app-shell__backdrop--right" />

      <header className="hero-card">
        <div className="hero-card__copy">
          <div className="hero-card__eyebrow">Phase 7 Visual Artifacts</div>
          <h1>Policy-first architecture, shown as product surfaces instead of abstract notes.</h1>
          <p>{scenario.heading}</p>
        </div>
        <div className="hero-card__meta">
          <div className="hero-chip">React demo</div>
          <div className="hero-chip">Architecture console</div>
          <div className="hero-chip">Approval-aware UX</div>
        </div>
      </header>

      <section className="scenario-strip">
        {Object.entries(SCENARIOS).map(([key, item]) => (
          <ScenarioButton
            key={key}
            isActive={scenarioKey === key}
            label={item.label}
            badge={item.badge}
            onClick={() => {
              startTransition(() => setScenarioKey(key));
            }}
          />
        ))}
      </section>

      <main className="content-grid">
        <section className="panel panel-topology">
          <div className="panel__header">
            <div>
              <div className="panel__eyebrow">System Topology</div>
              <h2>Target request path</h2>
            </div>
            <p>{scenario.summary}</p>
          </div>
          <div className="topology-canvas">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable={false}
              fitView
              fitViewOptions={{ padding: 0.14 }}
              proOptions={{ hideAttribution: true }}
            >
              <Background gap={20} size={1} color="rgba(16, 42, 67, 0.08)" />
              <Controls showInteractive={false} position="bottom-right" />
            </ReactFlow>
          </div>
        </section>

        <aside className="panel control-rail">
          <div className="rail-card">
            <div className="panel__eyebrow">Envelope Snapshot</div>
            <h3>Scope before reasoning</h3>
            <dl className="envelope-list">
              {scenario.envelope.map(([label, value]) => (
                <div key={label} className="envelope-list__row">
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          </div>

          <div className="rail-card">
            <div className="panel__eyebrow">Active Agents</div>
            <h3>Who is allowed to participate</h3>
            <div className="agent-pill-grid">
              {scenario.agents.map((agent) => (
                <AgentPill key={agent.name} {...agent} />
              ))}
            </div>
          </div>

          <div className="rail-card">
            <div className="panel__eyebrow">Approval Queue</div>
            <h3>Visible control state</h3>
            <div className="approval-card-grid">
              {scenario.approvals.map((item) => (
                <ApprovalCard key={item.title} {...item} />
              ))}
            </div>
          </div>
        </aside>
      </main>

      <section className="surface-grid">
        <article className="panel surface-card">
          <div className="panel__header">
            <div>
              <div className="panel__eyebrow">Surface Mockup</div>
              <h2>{scenario.transcriptTitle}</h2>
            </div>
            <p>What the user sees should reflect mode, scope, and approval state without exposing internal raw mechanics.</p>
          </div>
          <div className="transcript-stack">
            {scenario.transcript.map((message) => (
              <TranscriptBubble key={`${message.role}-${message.text}`} {...message} />
            ))}
          </div>
        </article>

        <article className="panel surface-card">
          <div className="panel__header">
            <div>
              <div className="panel__eyebrow">Execution Timeline</div>
              <h2>Deterministic phase progression</h2>
            </div>
            <p>The demo keeps the planner, approval, and execution states distinct so later implementation work has a stable contract.</p>
          </div>
          <div className="timeline-stack">
            {scenario.timeline.map((item) => (
              <TimelineItem key={item.title} {...item} />
            ))}
          </div>
        </article>

        <article className="panel surface-card">
          <div className="panel__header">
            <div>
              <div className="panel__eyebrow">Output Blocks</div>
              <h2>Formatter-facing artifacts</h2>
            </div>
            <p>These blocks preview what the formatter layer should assemble once the backend contracts exist in code.</p>
          </div>
          <div className="output-grid">
            {scenario.outputs.map((item) => (
              <OutputCard key={item.title} {...item} />
            ))}
          </div>
        </article>
      </section>

      <LiveConsole />
    </div>
  );
}

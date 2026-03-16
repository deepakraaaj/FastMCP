import React, { useState, useCallback, useRef, useMemo } from 'react';
import ReactFlow, {
  addEdge,
  Background,
  Controls,
  MiniMap,
  applyEdgeChanges,
  applyNodeChanges,
} from 'reactflow';
import 'reactflow/dist/style.css';

import WorkflowNode from './nodes/WorkflowNode';
import Sidebar from './components/Sidebar';
import ConfigPanel from './components/ConfigPanel';

/* ── Register custom node types ──────────────── */
const nodeTypes = { workflow: WorkflowNode };

/* ── Default workflow (demo) ─────────────────── */
const defaultNodes = [
  {
    id: '1',
    type: 'workflow',
    position: { x: 40, y: 180 },
    data: {
      kind: 'trigger',
      label: 'User Message',
      description: 'Incoming chat request',
      status: 'success',
      footer: 'app_id: fits',
    },
  },
  {
    id: '2',
    type: 'workflow',
    position: { x: 320, y: 60 },
    data: {
      kind: 'discover',
      label: 'Schema Discovery',
      description: 'Introspect fits_dev_march_9',
      status: 'success',
      footer: '14 tables found',
      appId: 'fits',
    },
  },
  {
    id: '3',
    type: 'workflow',
    position: { x: 320, y: 280 },
    data: {
      kind: 'reason',
      label: 'vLLM Reasoner',
      description: 'Analyze schema + user intent',
      status: 'running',
      footer: 'Model: Llama 3 70B',
      model: 'llama3',
      temperature: 0.7,
      prompt: 'Analyze the user request against the discovered schema...',
    },
  },
  {
    id: '4',
    type: 'workflow',
    position: { x: 640, y: 60 },
    data: {
      kind: 'action',
      label: 'SQL Execution',
      description: 'Run validated query',
      status: 'idle',
      footer: 'Policy: SELECT only',
      sql: "SELECT name, email FROM users WHERE active=1",
    },
  },
  {
    id: '5',
    type: 'workflow',
    position: { x: 640, y: 280 },
    data: {
      kind: 'clarify',
      label: 'User Clarification',
      description: 'Ask user to pick a table',
      status: 'waiting',
      footer: 'Awaiting response',
      clarifyPrompt: 'Which maintenance type would you like to create?',
    },
  },
  {
    id: '6',
    type: 'workflow',
    position: { x: 940, y: 180 },
    data: {
      kind: 'response',
      label: 'Final Response',
      description: 'Send result to user',
      status: 'idle',
    },
  },
];

const defaultEdges = [
  { id: 'e1-2', source: '1', target: '2', animated: true },
  { id: 'e1-3', source: '1', target: '3', animated: true },
  { id: 'e2-4', source: '2', target: '4', animated: true },
  { id: 'e3-5', source: '3', target: '5', animated: true },
  { id: 'e4-6', source: '4', target: '6', animated: true },
  { id: 'e5-6', source: '5', target: '6', animated: true },
];

/* ── Unique ID counter ───────────────────────── */
let nodeIdCounter = 100;
const getNodeId = () => `node_${nodeIdCounter++}`;

/* ── App ─────────────────────────────────────── */
export default function App() {
  const reactFlowWrapper = useRef(null);
  const [nodes, setNodes] = useState(defaultNodes);
  const [edges, setEdges] = useState(defaultEdges);
  const [selectedNode, setSelectedNode] = useState(null);
  const [reactFlowInstance, setReactFlowInstance] = useState(null);

  /* ── Node / Edge changes ── */
  const onNodesChange = useCallback(
    (changes) => setNodes((nds) => applyNodeChanges(changes, nds)),
    [],
  );
  const onEdgesChange = useCallback(
    (changes) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    [],
  );
  const onConnect = useCallback(
    (params) =>
      setEdges((eds) => addEdge({ ...params, animated: true }, eds)),
    [],
  );

  /* ── Node click → open config panel ── */
  const onNodeClick = useCallback((_, node) => {
    setSelectedNode(node);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  /* ── Update node data from config panel ── */
  const onUpdateNodeData = useCallback((nodeId, newData) => {
    setNodes((nds) =>
      nds.map((n) => (n.id === nodeId ? { ...n, data: newData } : n)),
    );
    setSelectedNode((prev) =>
      prev && prev.id === nodeId ? { ...prev, data: newData } : prev,
    );
  }, []);

  /* ── Drag & Drop from sidebar ── */
  const onDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event) => {
      event.preventDefault();
      const kind = event.dataTransfer.getData('application/reactflow-kind');
      const label = event.dataTransfer.getData('application/reactflow-label');

      if (!kind || !reactFlowInstance) return;

      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      const newNode = {
        id: getNodeId(),
        type: 'workflow',
        position,
        data: {
          kind,
          label: label || kind,
          description: '',
          status: 'idle',
        },
      };

      setNodes((nds) => nds.concat(newNode));
    },
    [reactFlowInstance],
  );

  /* ── Minimap color ── */
  const minimapNodeColor = useCallback((n) => {
    const kind = n.data?.kind;
    const map = {
      trigger: '#06b6d4', discover: '#a855f7', reason: '#f59e0b',
      action: '#10b981', clarify: '#f43f5e', response: '#6366f1',
    };
    return map[kind] || '#64748b';
  }, []);

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      {/* Left Sidebar */}
      <Sidebar />

      {/* Top Bar */}
      <div className="topbar" style={{ left: 'calc(260px + 50%)', transform: 'translateX(-50%)' }}>
        <span className="topbar-title">Create Maintenance Task</span>
        <div className="topbar-sep" />
        <span className="topbar-badge">6 nodes</span>
        <div className="topbar-sep" />
        <button className="topbar-btn" onClick={() => alert('Workflow execution coming soon!')}>
          ▶ Run Workflow
        </button>
      </div>

      {/* Canvas */}
      <div
        className={`canvas-wrapper ${selectedNode ? 'panel-open' : ''}`}
        ref={reactFlowWrapper}
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onInit={setReactFlowInstance}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          onDragOver={onDragOver}
          onDrop={onDrop}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          defaultEdgeOptions={{ animated: true }}
        >
          <Background color="#1e293b" gap={20} size={1} />
          <Controls />
          <MiniMap
            nodeColor={minimapNodeColor}
            maskColor="rgba(2, 6, 23, 0.7)"
          />
        </ReactFlow>
      </div>

      {/* Right Config Panel */}
      <ConfigPanel
        node={selectedNode}
        onClose={() => setSelectedNode(null)}
        onUpdate={onUpdateNodeData}
      />
    </div>
  );
}

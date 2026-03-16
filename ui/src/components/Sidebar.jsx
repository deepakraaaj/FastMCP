import React from 'react';

const PALETTE = [
  { kind: 'trigger',  label: 'Trigger',            icon: '⚡', desc: 'User message or HTTP hook' },
  { kind: 'discover', label: 'Schema Discovery',   icon: '🔍', desc: 'Auto-introspect app DB'   },
  { kind: 'reason',   label: 'vLLM Reasoner',      icon: '🧠', desc: 'AI agent reasoning step'   },
  { kind: 'action',   label: 'SQL Execution',       icon: '⚙️', desc: 'Run queries / mutations'   },
  { kind: 'clarify',  label: 'User Clarification', icon: '💬', desc: 'Ask user for more info'    },
  { kind: 'response', label: 'Response',            icon: '📤', desc: 'Send final result'         },
];

function Sidebar() {
  const onDragStart = (event, kind, label) => {
    event.dataTransfer.setData('application/reactflow-kind', kind);
    event.dataTransfer.setData('application/reactflow-label', label);
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="dot" />
        <h1>Aegis Orchestrator</h1>
        <span>v0.1</span>
      </div>

      {/* Node Palette */}
      <div className="sidebar-section">Drag to Canvas</div>
      {PALETTE.map((item) => (
        <div
          key={item.kind}
          className="node-palette-item"
          draggable
          onDragStart={(e) => onDragStart(e, item.kind, item.label)}
        >
          <div
            className="icon"
            style={{
              background: `rgba(${item.kind === 'trigger' ? '6,182,212' : item.kind === 'discover' ? '168,85,247' : item.kind === 'reason' ? '245,158,11' : item.kind === 'action' ? '16,185,129' : item.kind === 'clarify' ? '244,63,94' : '99,102,241'}, 0.15)`,
              fontSize: 16,
            }}
          >
            {item.icon}
          </div>
          <div>
            <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 13 }}>
              {item.label}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              {item.desc}
            </div>
          </div>
        </div>
      ))}

      {/* Connected Apps */}
      <div className="sidebar-section" style={{ marginTop: 16 }}>Connected Apps</div>
      <div className="node-palette-item" style={{ cursor: 'default' }}>
        <div className="icon" style={{ background: 'rgba(16,185,129,0.15)', fontSize: 14 }}>🗄️</div>
        <div>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 13 }}>
            fits_dev_march_9
          </div>
          <div style={{ fontSize: 11, color: 'var(--emerald-500)' }}>● Connected</div>
        </div>
      </div>
    </div>
  );
}

export default Sidebar;

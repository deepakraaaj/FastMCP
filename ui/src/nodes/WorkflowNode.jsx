import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';

/* ── Color map per node type ─────────────────── */
const COLORS = {
  trigger:   { bg: 'rgba(6,182,212,0.10)',  accent: '#06b6d4', border: 'rgba(6,182,212,0.3)'  },
  discover:  { bg: 'rgba(168,85,247,0.10)',  accent: '#a855f7', border: 'rgba(168,85,247,0.3)' },
  reason:    { bg: 'rgba(245,158,11,0.10)',  accent: '#f59e0b', border: 'rgba(245,158,11,0.3)' },
  action:    { bg: 'rgba(16,185,129,0.10)',  accent: '#10b981', border: 'rgba(16,185,129,0.3)' },
  clarify:   { bg: 'rgba(244,63,94,0.10)',   accent: '#f43f5e', border: 'rgba(244,63,94,0.3)'  },
  response:  { bg: 'rgba(99,102,241,0.10)',  accent: '#6366f1', border: 'rgba(99,102,241,0.3)' },
};

const ICONS = {
  trigger:  '⚡',
  discover: '🔍',
  reason:   '🧠',
  action:   '⚙️',
  clarify:  '💬',
  response: '📤',
};

function WorkflowNode({ data, selected }) {
  const kind = data.kind || 'action';
  const color = COLORS[kind] || COLORS.action;
  const icon = ICONS[kind] || '⚙️';
  const status = data.status || 'idle';

  return (
    <div
      className={`custom-node ${selected ? 'selected' : ''}`}
      style={{ borderColor: selected ? color.accent : undefined }}
    >
      {/* ── Header ── */}
      <div
        className="custom-node-header"
        style={{ background: color.bg, color: color.accent }}
      >
        <span style={{ fontSize: 16 }}>{icon}</span>
        <span>{kind.toUpperCase()}</span>
        <span className={`status-badge ${status}`} style={{ marginLeft: 'auto' }}>
          <span className="status-dot" />
          {status}
        </span>
      </div>

      {/* ── Body ── */}
      <div className="custom-node-body">
        <div className="label">{data.label}</div>
        {data.description && (
          <div className="description">{data.description}</div>
        )}
      </div>

      {/* ── Footer ── */}
      {data.footer && (
        <div className="custom-node-footer">
          <span>{data.footer}</span>
        </div>
      )}

      {/* ── Handles ── */}
      {kind !== 'trigger' && (
        <Handle
          type="target"
          position={Position.Left}
          style={{ background: color.accent }}
        />
      )}
      {kind !== 'response' && (
        <Handle
          type="source"
          position={Position.Right}
          style={{ background: color.accent }}
        />
      )}
    </div>
  );
}

export default memo(WorkflowNode);

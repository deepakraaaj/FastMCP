import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';

function SystemNode({ data }) {
  const Icon = data.icon;

  return (
    <div className={`system-node state-${data.state || 'idle'} ${data.emphasis ? 'is-emphasis' : ''}`}>
      <div className="system-node__header">
        <div className="system-node__icon">
          <Icon size={18} strokeWidth={2.1} />
        </div>
        <div className="system-node__eyebrow">{data.eyebrow}</div>
      </div>
      <div className="system-node__title">{data.title}</div>
      <div className="system-node__detail">{data.detail}</div>
      <div className="system-node__footer">
        <span className={`node-state-chip state-${data.state || 'idle'}`}>{data.stateLabel}</span>
        <span className="system-node__footnote">{data.footnote}</span>
      </div>

      {data.target !== false ? (
        <Handle type="target" position={Position.Left} className="system-node__handle" />
      ) : null}
      {data.source !== false ? (
        <Handle type="source" position={Position.Right} className="system-node__handle" />
      ) : null}
    </div>
  );
}

export default memo(SystemNode);

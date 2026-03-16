import React from 'react';

function ConfigPanel({ node, onClose, onUpdate }) {
  if (!node) return null;
  const data = node.data || {};

  const handleChange = (field, value) => {
    onUpdate(node.id, { ...data, [field]: value });
  };

  return (
    <div className={`config-panel ${node ? 'open' : ''}`}>
      {/* Header */}
      <div className="config-panel-header">
        <h2>
          <span style={{ marginRight: 8 }}>{data.kind === 'trigger' ? '⚡' : data.kind === 'discover' ? '🔍' : data.kind === 'reason' ? '🧠' : data.kind === 'action' ? '⚙️' : data.kind === 'clarify' ? '💬' : '📤'}</span>
          {data.label || 'Node Config'}
        </h2>
        <button onClick={onClose} title="Close">✕</button>
      </div>

      {/* Body */}
      <div className="config-panel-body">
        {/* Label */}
        <div className="config-field">
          <label>Node Label</label>
          <input
            value={data.label || ''}
            onChange={(e) => handleChange('label', e.target.value)}
          />
        </div>

        {/* Description */}
        <div className="config-field">
          <label>Description</label>
          <input
            value={data.description || ''}
            onChange={(e) => handleChange('description', e.target.value)}
          />
        </div>

        {/* Kind-specific fields */}
        {data.kind === 'action' && (
          <div className="config-field">
            <label>SQL Query</label>
            <textarea
              value={data.sql || ''}
              onChange={(e) => handleChange('sql', e.target.value)}
              placeholder="SELECT * FROM tasks WHERE status = 'pending'"
            />
          </div>
        )}

        {data.kind === 'reason' && (
          <>
            <div className="config-field">
              <label>Model</label>
              <select
                value={data.model || 'auto'}
                onChange={(e) => handleChange('model', e.target.value)}
              >
                <option value="auto">Auto (vLLM)</option>
                <option value="llama3">Llama 3 70B</option>
                <option value="mistral">Mistral 7B</option>
              </select>
            </div>
            <div className="config-field">
              <label>Agent Prompt</label>
              <textarea
                value={data.prompt || ''}
                onChange={(e) => handleChange('prompt', e.target.value)}
                placeholder="Analyze the schema and determine what the user needs..."
              />
            </div>
            <div className="config-field">
              <label>Temperature</label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={data.temperature || 0.7}
                onChange={(e) => handleChange('temperature', parseFloat(e.target.value))}
                style={{ accentColor: 'var(--cyan-500)' }}
              />
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                {data.temperature || 0.7}
              </div>
            </div>
          </>
        )}

        {data.kind === 'discover' && (
          <div className="config-field">
            <label>App ID</label>
            <input
              value={data.appId || 'fits'}
              onChange={(e) => handleChange('appId', e.target.value)}
            />
          </div>
        )}

        {data.kind === 'clarify' && (
          <div className="config-field">
            <label>Clarification Prompt</label>
            <textarea
              value={data.clarifyPrompt || ''}
              onChange={(e) => handleChange('clarifyPrompt', e.target.value)}
              placeholder="Ask the user which table they want to insert into..."
            />
          </div>
        )}

        {/* Status */}
        <div className="config-field">
          <label>Status</label>
          <select
            value={data.status || 'idle'}
            onChange={(e) => handleChange('status', e.target.value)}
          >
            <option value="idle">Idle</option>
            <option value="running">Running</option>
            <option value="success">Success</option>
            <option value="waiting">Waiting</option>
            <option value="error">Error</option>
          </select>
        </div>

        {/* Node ID */}
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 'auto' }}>
          Node ID: {node.id}
        </div>
      </div>
    </div>
  );
}

export default ConfigPanel;

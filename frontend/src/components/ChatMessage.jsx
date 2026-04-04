import PixelCharacter from './PixelCharacter';

const AGENT_META = {
  ceo:    { name: '대표',         color: '#dc2626', bg: 'rgba(220,38,38,0.08)' },
  cfo:    { name: 'CFO',          color: '#16a34a', bg: 'rgba(22,163,74,0.08)' },
  cto:    { name: 'CTO',          color: '#2563eb', bg: 'rgba(37,99,235,0.08)' },
  cmo:    { name: 'CMO',          color: '#db2777', bg: 'rgba(219,39,119,0.08)' },
  bd:     { name: 'BD팀장',       color: '#7c3aed', bg: 'rgba(124,58,237,0.08)' },
  legal:  { name: '법무팀장',     color: '#b45309', bg: 'rgba(180,83,9,0.08)' },
  ux:     { name: 'UX디자이너',   color: '#0891b2', bg: 'rgba(8,145,178,0.08)' },
  data:   { name: '데이터분석가', color: '#0d9488', bg: 'rgba(13,148,136,0.08)' },
  junior: { name: 'MZ신입',       color: '#d97706', bg: 'rgba(217,119,6,0.08)' },
  chair:  { name: '의장',         color: '#6b7280', bg: 'rgba(107,114,128,0.08)' },
};

export function TypingIndicator({ agentId }) {
  const meta = AGENT_META[agentId];
  if (!meta) return null;
  return (
    <div className="message">
      <div className="message-bubble" style={{ '--agent-color': meta.color, '--agent-bg': meta.bg }}>
        <div className="message-avatar" style={{ background: meta.bg, borderColor: meta.color }}>
          <PixelCharacter agentId={agentId} state="talking" size={3} />
        </div>
        <div className="message-content">
          <div className="message-meta">
            <span className="message-name" style={{ color: meta.color }}>{meta.name}</span>
          </div>
          <div className="message-text typing-indicator">
            <span style={{ background: meta.color }} />
            <span style={{ background: meta.color }} />
            <span style={{ background: meta.color }} />
          </div>
        </div>
      </div>
    </div>
  );
}

export function RoundDivider({ round, title }) {
  return (
    <div className="message-round-divider">
      <span className="message-round-label">
        ROUND {round} — {title}
      </span>
    </div>
  );
}

export function MessageBubble({ agentId, text, round, isStreaming }) {
  const meta = AGENT_META[agentId];
  if (!meta) return null;

  return (
    <div className="message">
      <div
        className="message-bubble"
        data-agent={agentId}
        style={{ '--agent-color': meta.color, '--agent-bg': meta.bg }}
      >
        <div className="message-avatar" style={{
          background: meta.bg,
          borderColor: meta.color,
        }}>
          <PixelCharacter
            agentId={agentId}
            state={isStreaming ? 'talking' : 'idle'}
            size={3}
          />
        </div>
        <div className="message-content">
          <div className="message-meta">
            <span className="message-name" style={{ color: meta.color }}>
              {meta.name}
            </span>
            <span className="message-round-tag">R{round}</span>
          </div>
          <div className="message-text">
            {text}
            {isStreaming && <span className="cursor" style={{ background: meta.color }} />}
          </div>
        </div>
      </div>
    </div>
  );
}

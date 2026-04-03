import PixelCharacter from './PixelCharacter';

const AGENT_META = {
  optimist:    { name: '낙관론자',  color: 'var(--optimist)',    bgVar: 'var(--optimist-bg)' },
  critic:      { name: '비판론자',  color: 'var(--critic)',      bgVar: 'var(--critic-bg)' },
  realist:     { name: '현실주의자', color: 'var(--realist)',    bgVar: 'var(--realist-bg)' },
  businessman: { name: '사업가',    color: 'var(--businessman)', bgVar: 'var(--businessman-bg)' },
  veteran:   { name: '개발 20년차',    color: 'var(--veteran)',   bgVar: 'var(--veteran-bg)' },
  judge:       { name: '심판',      color: 'var(--judge)',       bgVar: 'var(--judge-bg)' },
};

export function TypingIndicator({ agentId }) {
  const meta = AGENT_META[agentId];
  if (!meta) return null;
  return (
    <div className="message">
      <div className="message-bubble" style={{ '--agent-color': meta.color, '--agent-bg': meta.bgVar }}>
        <div className="message-avatar" style={{ background: meta.bgVar, borderColor: meta.color }}>
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
        style={{ '--agent-color': meta.color, '--agent-bg': meta.bgVar }}
      >
        <div className="message-avatar" style={{
          background: meta.bgVar,
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

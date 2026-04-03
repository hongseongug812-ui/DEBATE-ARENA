import PixelCharacter from './PixelCharacter';

const AGENT_INFO = {
  optimist:   { name: '낙관론자',  role: 'Optimist — 기회 탐색',    color: 'var(--optimist)' },
  critic:     { name: '비판론자',  role: 'Critic — 리스크 분석',    color: 'var(--critic)' },
  realist:    { name: '현실주의자', role: 'Realist — 현실 판단',    color: 'var(--realist)' },
  businessman:{ name: '사업가',    role: 'Businessman — 비즈니스 관점', color: 'var(--businessman)' },
  veteran:  { name: '개발 20년차',    role: '20yr Dev — 실전 경험',   color: 'var(--veteran)' },
  judge:      { name: '심판',      role: 'Judge — 최종 결론',       color: 'var(--judge)' },
};

const STATE_LABELS = {
  idle: '대기',
  talking: '발언 중',
  reacting: '반응',
};

export default function Sidebar({
  isOpen,
  onClose,
  agentStates,
  currentRound,
  isDebating,
}) {
  return (
    <>
      {isOpen && (
        <div className="sidebar-backdrop" onClick={onClose} />
      )}
      <aside className="sidebar" data-open={isOpen}>
        {/* Header */}
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <div className="sidebar-logo-dot" style={{
              background: isDebating ? 'var(--optimist)' : 'var(--accent)',
              boxShadow: isDebating
                ? '0 0 8px var(--optimist)'
                : '0 0 8px var(--accent)',
            }} />
            <h1>DEBATE ARENA</h1>
          </div>
          <p className="sidebar-subtitle">AI 멀티에이전트 토론 플랫폼</p>
        </div>

        {/* Agent Roster */}
        <div className="agent-roster">
          {Object.entries(AGENT_INFO).map(([id, info]) => {
            const state = agentStates[id] || 'idle';
            const isActive = state !== 'idle';

            return (
              <div
                key={id}
                className="agent-card"
                data-active={isActive}
                style={{
                  '--agent-color': info.color,
                  '--agent-glow': info.color.replace(')', ', 0.3)').replace('var(', 'rgba('),
                  '--agent-bg': info.color.replace(')', ', 0.08)').replace('var(', 'rgba('),
                }}
              >
                <div className="agent-card-avatar">
                  <PixelCharacter agentId={id} state={state} size={3} />
                </div>
                <div className="agent-card-info">
                  <div className="agent-card-name" style={{ color: info.color }}>
                    {info.name}
                  </div>
                  <div className="agent-card-role">{info.role}</div>
                </div>
                <div
                  className="agent-card-status"
                  data-state={state}
                  style={{
                    '--agent-color': info.color,
                    '--agent-bg': info.color,
                    color: isActive ? info.color : undefined,
                    background: isActive
                      ? undefined
                      : undefined,
                  }}
                >
                  {STATE_LABELS[state] || state}
                </div>
              </div>
            );
          })}
        </div>

        {/* Round Indicator */}
        <div className="round-indicator">
          <div className="round-indicator-label">
            {isDebating ? `ROUND ${currentRound}` : 'READY'}
          </div>
          <div className="round-dots">
            {Array.from({ length: Math.max(currentRound + 1, 3) }, (_, i) => i + 1).map((r) => (
              <div
                key={r}
                className="round-dot"
                data-active={currentRound === r}
                data-complete={currentRound > r}
              />
            ))}
          </div>
        </div>
      </aside>
    </>
  );
}

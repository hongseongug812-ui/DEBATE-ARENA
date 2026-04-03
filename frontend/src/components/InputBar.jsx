import { useState } from 'react';

export default function InputBar({ onSubmit, onFeedback, isDebating, debateDone, sessionId }) {
  const [value, setValue] = useState('');
  const isFeedbackMode = debateDone && sessionId && !isDebating;

  const handleSubmit = () => {
    if (!value.trim() || isDebating) return;
    if (isFeedbackMode) {
      onFeedback(value.trim());
    } else {
      onSubmit(value.trim());
    }
    setValue('');
  };

  return (
    <div className="input-bar">
      {isFeedbackMode && (
        <div className="feedback-hint">
          💬 피드백을 입력하면 에이전트들이 반영해서 다시 토론합니다
          &nbsp;·&nbsp;
          <span
            className="feedback-new-btn"
            onClick={() => { onSubmit && window.location.reload(); }}
          >
            새 토론 시작
          </span>
        </div>
      )}
      <div className="input-bar-inner">
        <input
          type="text"
          className="input-field"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          placeholder={
            isDebating
              ? '토론 진행 중...'
              : isFeedbackMode
              ? '예: 다른 아이디어 줘봐 / 이 방향으로 더 구체화해줘 / 비용이 적은 방향으로...'
              : '고민이나 질문을 입력하세요...'
          }
          disabled={isDebating}
        />
        <button
          className="submit-btn"
          onClick={handleSubmit}
          disabled={isDebating || !value.trim()}
          data-loading={isDebating}
          data-feedback={isFeedbackMode}
        >
          {isDebating ? '토론 중...' : isFeedbackMode ? '피드백' : 'START'}
        </button>
      </div>
    </div>
  );
}

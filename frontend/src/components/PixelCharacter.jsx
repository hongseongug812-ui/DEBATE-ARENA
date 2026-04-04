import { useRef, useEffect } from 'react';

/**
 * 픽셀 아트 스프라이트 데이터
 * 0=transparent, 1=body, 2=eye-white, 3=eye-pupil, 4=hat/accessory
 */
const SPRITE_DATA = {
  // 대표 (CEO) — 왕관
  ceo: {
    body: '#dc2626',
    pixels: [
      [0,4,0,0,4,4,0,0,4,0],
      [0,4,4,4,4,4,4,4,4,0],
      [0,1,1,1,1,1,1,1,1,0],
      [0,1,2,3,1,1,2,3,1,0],
      [0,1,1,1,1,1,1,1,1,0],
      [0,0,1,0,1,1,0,1,0,0],
      [0,0,0,1,1,1,1,0,0,0],
      [0,0,1,1,1,1,1,1,0,0],
      [0,1,1,0,1,1,0,1,1,0],
      [0,0,1,0,0,0,0,1,0,0],
    ],
  },
  // CFO — 두꺼운 안경
  cfo: {
    body: '#16a34a',
    pixels: [
      [0,0,0,1,1,1,1,0,0,0],
      [0,0,1,1,1,1,1,1,0,0],
      [0,1,1,1,1,1,1,1,1,0],
      [0,1,4,3,4,4,4,3,4,1],
      [0,1,4,4,4,1,4,4,4,1],
      [0,0,1,1,1,1,1,1,0,0],
      [0,0,0,1,4,4,1,0,0,0],
      [0,0,1,1,4,4,1,1,0,0],
      [0,1,1,0,1,1,0,1,1,0],
      [0,0,0,1,0,0,1,0,0,0],
    ],
  },
  // CTO — 안테나
  cto: {
    body: '#2563eb',
    pixels: [
      [0,0,0,0,4,4,0,0,0,0],
      [0,0,0,1,1,1,1,0,0,0],
      [0,0,1,1,1,1,1,1,0,0],
      [0,1,2,3,1,1,2,3,1,0],
      [0,1,1,4,4,4,4,1,1,0],
      [0,0,1,0,0,0,0,1,0,0],
      [0,0,0,1,1,1,1,0,0,0],
      [0,0,1,1,4,4,1,1,0,0],
      [0,1,1,0,1,1,0,1,1,0],
      [0,0,1,0,0,0,0,1,0,0],
    ],
  },
  // CMO — 삐죽한 헤어
  cmo: {
    body: '#db2777',
    pixels: [
      [0,1,0,1,0,1,0,1,0,0],
      [1,1,1,1,1,1,1,1,1,0],
      [0,1,1,1,1,1,1,1,1,0],
      [0,1,2,3,1,1,2,3,1,0],
      [0,1,1,1,1,1,1,1,1,0],
      [0,0,1,0,1,1,0,1,0,0],
      [0,0,0,1,1,1,1,0,0,0],
      [0,0,1,1,1,1,1,1,0,0],
      [0,1,1,0,1,1,0,1,1,0],
      [0,0,1,0,0,0,0,1,0,0],
    ],
  },
  // 법무팀장 — 무표정 + 정장
  legal: {
    body: '#b45309',
    pixels: [
      [0,0,0,1,1,1,1,0,0,0],
      [0,0,1,1,1,1,1,1,0,0],
      [0,1,1,1,1,1,1,1,1,0],
      [0,1,2,3,1,1,2,3,1,0],
      [0,1,1,1,1,1,1,1,1,0],
      [0,0,1,1,1,1,1,1,0,0],
      [0,0,0,1,4,4,1,0,0,0],
      [0,0,1,1,1,1,1,1,0,0],
      [0,1,1,0,1,1,0,1,1,0],
      [0,0,1,0,0,0,0,1,0,0],
    ],
  },
  // MZ신입 — 헤드폰
  junior: {
    body: '#d97706',
    pixels: [
      [0,0,4,1,1,1,1,4,0,0],
      [0,4,1,1,1,1,1,1,4,0],
      [0,1,1,1,1,1,1,1,1,0],
      [0,1,2,3,1,1,2,3,1,0],
      [0,1,1,1,1,1,1,1,1,0],
      [0,0,1,0,1,1,0,1,0,0],
      [0,0,0,1,1,1,1,0,0,0],
      [0,0,1,1,1,1,1,1,0,0],
      [0,1,1,0,1,1,0,1,1,0],
      [0,0,1,0,0,0,0,1,0,0],
    ],
  },
  // 의장 (Chair) — 의사봉 모자
  chair: {
    body: '#6b7280',
    pixels: [
      [0,0,1,1,1,1,1,1,0,0],
      [0,0,0,4,4,4,4,0,0,0],
      [0,0,0,1,1,1,1,0,0,0],
      [0,1,2,3,1,1,2,3,1,0],
      [0,1,1,1,1,1,1,1,1,0],
      [0,0,1,0,1,1,0,1,0,0],
      [0,0,0,1,1,1,1,0,0,0],
      [0,0,1,1,1,1,1,1,0,0],
      [0,1,1,0,1,1,0,1,1,0],
      [0,0,1,0,0,0,0,1,0,0],
    ],
  },
};

export default function PixelCharacter({ agentId, state = 'idle', size = 4 }) {
  const canvasRef = useRef(null);
  const sprite = SPRITE_DATA[agentId];

  useEffect(() => {
    if (!sprite) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animId;
    let tick = 0;

    const colorMap = {
      0: 'transparent',
      1: sprite.body,
      2: '#ffffff',
      3: '#111111',
      4: '#ffe066',
    };

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      let offsetY = 0;
      if (state === 'idle') {
        offsetY = Math.sin(tick * 0.05) * 1.5;
      } else if (state === 'talking') {
        offsetY = Math.sin(tick * 0.12) * 3;
      } else if (state === 'reacting') {
        offsetY = Math.sin(tick * 0.25) * 3 * Math.cos(tick * 0.15);
      }

      sprite.pixels.forEach((row, y) => {
        row.forEach((cell, x) => {
          if (cell === 0) return;
          ctx.fillStyle = colorMap[cell];
          ctx.fillRect(x * size, y * size + offsetY, size, size);
        });
      });

      // Talking mouth animation
      if (state === 'talking' && Math.sin(tick * 0.18) > 0) {
        ctx.fillStyle = '#111';
        ctx.fillRect(4 * size, 5 * size + offsetY, 2 * size, size * 0.8);
      }

      tick++;
      animId = requestAnimationFrame(draw);
    };

    draw();
    return () => cancelAnimationFrame(animId);
  }, [sprite, state, size]);

  if (!sprite) return null;

  return (
    <canvas
      ref={canvasRef}
      width={10 * size}
      height={12 * size}
      style={{ imageRendering: 'pixelated', display: 'block' }}
    />
  );
}

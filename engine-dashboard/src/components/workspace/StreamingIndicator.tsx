import React from 'react';

export function StreamingIndicator() {
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  if (reducedMotion) {
    return <span className="text-text-tertiary">…</span>;
  }

  return (
    <span className="inline-flex gap-1 items-center h-[18px]">
      <span className="w-1.5 h-1.5 rounded-full bg-text-secondary animate-[pulse_1s_infinite] delay-0" />
      <span className="w-1.5 h-1.5 rounded-full bg-text-secondary animate-[pulse_1s_infinite] delay-150" />
      <span className="w-1.5 h-1.5 rounded-full bg-text-secondary animate-[pulse_1s_infinite] delay-300" />
    </span>
  );
}

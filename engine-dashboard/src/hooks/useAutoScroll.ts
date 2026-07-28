import { useEffect, useRef, useState } from 'react';

export function useAutoScroll(dependencies: any[]) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showJumpButton, setShowJumpButton] = useState(false);
  
  const scrollToBottom = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  };
  
  useEffect(() => {
    if (!scrollRef.current) return;
    const el = scrollRef.current;
    
    // Check if we are near the bottom (within 100px)
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
    
    if (isNearBottom) {
      scrollToBottom();
      setShowJumpButton(false);
    } else {
      setShowJumpButton(true);
    }
  }, dependencies);

  return { scrollRef, showJumpButton, scrollToBottom };
}

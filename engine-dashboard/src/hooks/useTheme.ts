import { useState, useEffect } from 'react';
import { useRuntime } from '../runtime/RuntimeContext';

export function useTheme() {
  const { state, dispatch } = useRuntime();
  
  return {
    theme: state.themeMode,
    toggleTheme: () => dispatch({ type: 'THEME_TOGGLED' })
  };
}

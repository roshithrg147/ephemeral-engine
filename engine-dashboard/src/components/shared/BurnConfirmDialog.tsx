import React from 'react';
import * as Dialog from '@radix-ui/react-dialog';

interface BurnConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sessionId: string;
  onConfirm: () => void;
  isBurning: boolean;
  error: string | null;
}

export function BurnConfirmDialog({
  open,
  onOpenChange,
  sessionId,
  onConfirm,
  isBurning,
  error
}: BurnConfirmDialogProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-surface-overlay backdrop-blur-sm z-50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content 
          data-testid="burn-confirm-dialog"
          className="fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border border-border-strong bg-surface-1 p-6 shadow-xl rounded-xl data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%]"
        >
          <div className="flex flex-col space-y-1.5 text-center sm:text-left">
            <Dialog.Title className="text-lg font-semibold leading-none tracking-tight text-text-primary">
              Burn Session?
            </Dialog.Title>
            <Dialog.Description className="text-sm text-text-secondary">
              This will permanently invalidate session <span className="font-mono text-text-code">{sessionId}</span>. This cannot be undone.
            </Dialog.Description>
          </div>
          
          {error && (
            <div className="p-3 rounded-md bg-message-error-bg text-message-error-fg text-sm border border-[rgba(221,68,68,0.3)]">
              Failed to burn session: {error}. Please try again.
            </div>
          )}

          <div className="flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2 mt-4">
            <Dialog.Close asChild>
              <button 
                disabled={isBurning}
                data-testid="burn-confirm-cancel"
                className="mt-2 sm:mt-0 px-4 py-2 bg-transparent text-text-primary border border-border-default rounded-md hover:bg-surface-2 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
            </Dialog.Close>
            <button
              onClick={onConfirm}
              disabled={isBurning}
              data-testid="burn-confirm-submit"
              className="px-4 py-2 bg-status-expired text-white border border-[rgba(0,0,0,0.1)] rounded-md hover:bg-red-600 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isBurning ? (
                <>
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Burning...
                </>
              ) : 'Burn Session'}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

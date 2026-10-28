import type { ReactNode } from "react";

export function EvidenceDrawer({ open, onClose, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/50" onClick={onClose}>
      <div
        className="h-full w-full max-w-xl overflow-y-auto border-l border-slate-800 bg-slate-950 p-6"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">证据</h3>
          <button onClick={onClose} className="rounded-md border border-slate-700 px-2 py-1 text-xs text-slate-300">
            关闭
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

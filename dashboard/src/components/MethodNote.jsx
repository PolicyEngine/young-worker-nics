"use client";

import { useState } from "react";

/**
 * Collapsible per-section methodology explainer. The `text` string comes
 * verbatim from data.methods.* in the results JSON — written by the
 * pipeline, never composed in the dashboard.
 */
export default function MethodNote({ text, children }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="note-card mt-4 rounded-r-xl p-4">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 text-left"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <span className="eyebrow note-eyebrow">How we computed this</span>
        <span className="eyebrow note-eyebrow">{open ? "Hide" : "Show"}</span>
      </button>
      {open && (
        <div className="note-body mt-3 text-sm leading-6">
          <p>{text}</p>
          {children}
        </div>
      )}
    </div>
  );
}

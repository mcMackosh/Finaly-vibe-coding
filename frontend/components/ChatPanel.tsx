"use client";

import { useEffect, useRef, useState } from "react";
import { useStore } from "@/lib/store";
import { formatPrice } from "@/lib/format";
import type { ChatActions, ChatMessage } from "@/lib/types";

function ActionSummary({ actions }: { actions: ChatActions }) {
  const lines: string[] = [];
  for (const t of actions.trades ?? []) {
    lines.push(
      `${t.side === "buy" ? "Bought" : "Sold"} ${t.quantity} ${t.ticker} @ ${formatPrice(t.price)}`,
    );
  }
  for (const c of actions.watchlist_changes ?? []) {
    lines.push(
      `${c.action === "add" ? "Added" : "Removed"} ${c.ticker} ${
        c.action === "add" ? "to" : "from"
      } watchlist`,
    );
  }
  if (lines.length === 0 && !actions.error) return null;

  return (
    <div className="mt-2 space-y-1">
      {lines.map((line, i) => (
        <div
          key={i}
          className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <path d="M2 5L4.5 7.5L8.5 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          {line}
        </div>
      ))}
      {actions.error && (
        <div className="inline-flex items-center gap-1.5 rounded-full bg-rose-500/10 px-3 py-1 text-xs font-medium text-rose-400">
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <path d="M2 2L8 8M8 2L2 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          {actions.error}
        </div>
      )}
    </div>
  );
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[82%] rounded-2xl px-4 py-3 text-sm ${
          isUser
            ? "rounded-br-sm bg-accent text-white"
            : "rounded-bl-sm border border-border bg-surface-raised text-text-primary"
        }`}
      >
        <p className="whitespace-pre-wrap break-words leading-relaxed">{msg.content}</p>
        {!isUser && msg.actions && <ActionSummary actions={msg.actions} />}
      </div>
    </div>
  );
}

export function ChatPanel({
  open,
  onToggle,
}: {
  open: boolean;
  onToggle: () => void;
}) {
  const { chatMessages, sendChat, chatPending } = useStore();
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [chatMessages, chatPending]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || chatPending) return;
    setInput("");
    await sendChat(text).catch(() => {});
  };

  if (!open) {
    return (
      <button
        onClick={onToggle}
        className="flex h-full w-12 shrink-0 flex-col items-center justify-center gap-2 border-l border-border bg-surface text-text-muted transition-colors hover:bg-surface-raised hover:text-accent"
        aria-label="Open AI assistant"
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <path d="M3 5C3 3.9 3.9 3 5 3H15C16.1 3 17 3.9 17 5V11C17 12.1 16.1 13 15 13H12L8 17V13H5C3.9 13 3 12.1 3 11V5Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <span
          className="text-[9px] font-semibold uppercase tracking-wider"
          style={{ writingMode: "vertical-rl" }}
        >
          Copilot
        </span>
      </button>
    );
  }

  return (
    <aside className="flex h-full w-80 shrink-0 flex-col border-l border-border bg-surface">
      {/* Header */}
      <header className="flex shrink-0 items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/10">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M2 4C2 3.45 2.45 3 3 3H11C11.55 3 12 3.45 12 4V9C12 9.55 11.55 10 11 10H8.5L6 12.5V10H3C2.45 10 2 9.55 2 9V4Z" stroke="#06b6d4" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <div>
            <h2 className="text-sm font-semibold text-text-primary">AI Copilot</h2>
            <p className="text-[10px] text-text-muted">Powered by OpenRouter</p>
          </div>
        </div>
        <button
          onClick={onToggle}
          className="flex h-7 w-7 items-center justify-center rounded-lg text-text-muted transition-colors hover:bg-surface-raised hover:text-text-primary"
          aria-label="Collapse"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M2 2L12 12M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </button>
      </header>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
        {chatMessages.length === 0 && !chatPending && (
          <div className="flex flex-col items-center justify-center gap-3 py-8 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent/10">
              <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
                <path d="M3 5C3 3.9 3.9 3 5 3H17C18.1 3 19 3.9 19 5V14C19 15.1 18.1 16 17 16H13L9 20V16H5C3.9 16 3 15.1 3 14V5Z" stroke="#06b6d4" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <p className="text-xs text-text-muted leading-relaxed max-w-[200px]">
              Ask me to analyze your portfolio, place trades, or manage your watchlist.
            </p>
          </div>
        )}
        {chatMessages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}
        {chatPending && (
          <div className="flex justify-start">
            <div className="rounded-2xl rounded-bl-sm border border-border bg-surface-raised px-4 py-3">
              <span className="inline-flex gap-1">
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-text-muted [animation-delay:0ms]"/>
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-text-muted [animation-delay:150ms]"/>
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-text-muted [animation-delay:300ms]"/>
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={submit} className="shrink-0 border-t border-border p-3">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit(e);
              }
            }}
            rows={2}
            placeholder="Ask FinAlly…"
            className="flex-1 resize-none rounded-xl border border-border bg-surface-raised px-3 py-2 text-sm text-text-primary outline-none focus:border-accent placeholder:text-text-muted/50"
          />
          <button
            type="submit"
            disabled={!input.trim() || chatPending}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent text-white shadow-sm transition-all hover:bg-accent/90 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Send"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M1 8L15 1L8 15L7 9L1 8Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>
      </form>
    </aside>
  );
}

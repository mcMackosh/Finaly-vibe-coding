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
    <div className="mt-1.5 space-y-1">
      {lines.map((line, i) => (
        <div
          key={i}
          className="rounded border border-up/40 bg-up/10 px-2 py-1 font-mono text-xs text-up"
        >
          {line}
        </div>
      ))}
      {actions.error && (
        <div className="rounded border border-down/40 bg-down/10 px-2 py-1 font-mono text-xs text-down">
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
        className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
          isUser
            ? "bg-purple text-white"
            : "bg-surface-raised text-text-primary"
        }`}
      >
        <p className="whitespace-pre-wrap break-words">{msg.content}</p>
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
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
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
        className="flex h-full w-10 shrink-0 flex-col items-center justify-center gap-2 border-l border-border bg-surface text-text-muted hover:text-accent"
        aria-label="Open AI assistant"
      >
        <span className="text-lg">💬</span>
        <span
          className="text-xs font-semibold uppercase tracking-wider"
          style={{ writingMode: "vertical-rl" }}
        >
          AI Assistant
        </span>
      </button>
    );
  }

  return (
    <aside className="flex h-full w-80 shrink-0 flex-col border-l border-border bg-surface">
      <header className="flex shrink-0 items-center justify-between border-b border-border px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
          AI Assistant
        </h2>
        <button
          onClick={onToggle}
          className="text-text-muted hover:text-text-primary"
          aria-label="Collapse assistant"
        >
          ✕
        </button>
      </header>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-3">
        {chatMessages.length === 0 && !chatPending && (
          <p className="text-center text-xs text-text-muted">
            Ask FinAlly to analyze your portfolio, place trades, or manage your
            watchlist.
          </p>
        )}
        {chatMessages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}
        {chatPending && (
          <div className="flex justify-start">
            <div className="rounded-lg bg-surface-raised px-3 py-2 text-sm text-text-muted">
              <span className="inline-flex gap-1">
                <span className="animate-bounce">•</span>
                <span className="animate-bounce [animation-delay:0.15s]">•</span>
                <span className="animate-bounce [animation-delay:0.3s]">•</span>
              </span>
            </div>
          </div>
        )}
      </div>

      <form onSubmit={submit} className="shrink-0 border-t border-border p-2">
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
            placeholder="Message FinAlly…"
            className="flex-1 resize-none rounded border border-border bg-background px-2 py-1.5 text-sm text-text-primary outline-none focus:border-blue"
          />
          <button
            type="submit"
            disabled={!input.trim() || chatPending}
            className="rounded bg-purple px-3 py-1.5 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </form>
    </aside>
  );
}

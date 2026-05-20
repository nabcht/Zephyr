import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import type { LucideIcon } from "lucide-react";
import ReactMarkdown, { type Components } from "react-markdown";
import { Link } from "react-router-dom";
import remarkGfm from "remark-gfm";

import { WorkspaceHeader } from "./WorkspaceHeader";
import type { MarkdownDocument } from "../types/api";

interface MarkdownDocumentPageProps {
  slug: string;
  eyebrow: string;
  fallbackTitle: string;
  fallbackSubtitle: string;
  icon: LucideIcon;
  actions?: ReactNode;
  children?: ReactNode;
}

function resolveDocumentHref(href?: string): string | undefined {
  if (!href) {
    return undefined;
  }

  const normalized = href.split("\\").join("/").replace(/^\.\//, "").toLowerCase();
  switch (normalized) {
    case "docs.md":
      return "/docs";
    case "features.md":
      return "/features";
    case "glossary.md":
      return "/glossary";
    case "api_docs.md":
      return "/api-docs";
    case "privacy.md":
      return "/privacy";
    case "terms.md":
      return "/terms";
    default:
      return href;
  }
}

const markdownComponents: Components = {
  h2: ({ node: _node, ...props }) => <h2 className="mt-8 text-2xl font-semibold text-primary" {...props} />,
  h3: ({ node: _node, ...props }) => <h3 className="mt-6 text-lg font-semibold text-primary" {...props} />,
  h4: ({ node: _node, ...props }) => <h4 className="mt-5 text-base font-semibold text-primary" {...props} />,
  p: ({ node: _node, ...props }) => <p className="text-sm leading-7 text-text-muted" {...props} />,
  ul: ({ node: _node, ...props }) => <ul className="space-y-3 pl-6 text-sm leading-7 text-text-muted" {...props} />,
  ol: ({ node: _node, ...props }) => <ol className="space-y-3 pl-6 text-sm leading-7 text-text-muted" {...props} />,
  li: ({ node: _node, ...props }) => <li className="list-disc" {...props} />,
  a: ({ node: _node, href, children, ...props }) => {
    const resolvedHref = resolveDocumentHref(href);
    if (resolvedHref?.startsWith("/")) {
      return (
        <Link to={resolvedHref} className="font-medium text-accent underline decoration-accent/30 underline-offset-4" {...props}>
          {children}
        </Link>
      );
    }

    const isExternal = Boolean(resolvedHref?.startsWith("http://") || resolvedHref?.startsWith("https://"));
    return (
      <a
        href={resolvedHref}
        className="font-medium text-accent underline decoration-accent/30 underline-offset-4"
        target={isExternal ? "_blank" : undefined}
        rel={isExternal ? "noreferrer" : undefined}
        {...props}
      >
        {children}
      </a>
    );
  },
  blockquote: ({ node: _node, ...props }) => (
    <blockquote className="border-l-4 border-secondary/60 bg-surface-container-low px-space-md py-space-sm text-sm leading-7 text-text-muted" {...props} />
  ),
  pre: ({ node: _node, ...props }) => <pre className="overflow-x-auto rounded-xl bg-surface-container p-space-md text-xs leading-6 text-primary" {...props} />,
  code: ({ node: _node, className, children, ...props }) => {
    const value = String(children).replace(/\n$/, "");
    const inline = !value.includes("\n") && !className;
    return (
      <code
        className={
          inline
            ? "rounded bg-surface-container px-1.5 py-1 font-mono text-[0.9em] text-primary"
            : `font-mono text-xs text-primary ${className ?? ""}`.trim()
        }
        {...props}
      >
        {value}
      </code>
    );
  },
  table: ({ node: _node, ...props }) => (
    <div className="overflow-x-auto rounded-xl border border-border-subtle">
      <table className="min-w-full divide-y divide-border-subtle text-sm" {...props} />
    </div>
  ),
  thead: ({ node: _node, ...props }) => <thead className="bg-surface-container-lowest" {...props} />,
  tbody: ({ node: _node, ...props }) => <tbody className="divide-y divide-border-subtle bg-surface" {...props} />,
  tr: ({ node: _node, ...props }) => <tr {...props} />,
  th: ({ node: _node, ...props }) => <th className="px-space-sm py-space-sm text-left font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted" {...props} />,
  td: ({ node: _node, ...props }) => <td className="px-space-sm py-space-sm align-top text-text-muted" {...props} />,
  hr: ({ node: _node, ...props }) => <hr className="border-border-subtle" {...props} />,
};

function MarkdownBody({ content }: { content: string }) {
  return (
    <article className="rounded-xl border border-border-subtle bg-surface p-space-lg shadow-sm">
      <div className="space-y-5">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
          {content}
        </ReactMarkdown>
      </div>
    </article>
  );
}

async function requestDocument(slug: string, signal: AbortSignal): Promise<MarkdownDocument> {
  const response = await fetch(`/api/docs/${slug}`, { signal });
  if (!response.ok) {
    let message = `Request failed with ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === "string" && payload.detail.trim()) {
        message = payload.detail;
      }
    } catch {
      // Fall back to the status-based error message.
    }
    throw new Error(message);
  }

  return (await response.json()) as MarkdownDocument;
}

export function MarkdownDocumentPage({ slug, eyebrow, fallbackTitle, fallbackSubtitle, icon, actions, children }: MarkdownDocumentPageProps) {
  const [document, setDocument] = useState<MarkdownDocument | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();

    async function load(): Promise<void> {
      setIsLoading(true);
      setError(null);

      try {
        setDocument(await requestDocument(slug, controller.signal));
      } catch (loadError) {
        if (loadError instanceof DOMException && loadError.name === "AbortError") {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "Unknown error");
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    }

    void load();
    return () => controller.abort();
  }, [slug]);

  const title = document?.title ?? fallbackTitle;
  const subtitle = document ? `Rendered directly from ${document.source_path}.` : fallbackSubtitle;

  return (
    <div className="space-y-6">
      <WorkspaceHeader eyebrow={eyebrow} title={title} subtitle={subtitle} icon={icon} actions={actions} />

      {error ? (
        <article className="rounded-xl border border-red-200 bg-red-50 p-space-md text-sm leading-6 text-red-900">{error}</article>
      ) : null}

      {isLoading ? (
        <article className="rounded-xl border border-border-subtle bg-surface p-space-lg text-sm leading-6 text-text-muted shadow-sm">
          Loading markdown from Docs/{slug}.md...
        </article>
      ) : null}

      {document ? <MarkdownBody content={document.content} /> : null}

      {children}
    </div>
  );
}
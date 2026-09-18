import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

function isIdToken(text: string) {
  return /^(RM\d+|CUST\d+|CALL_|FND-|CASE_)/i.test(text);
}

const components: Components = {
  h1: ({ children }) => (
    <h1 className="text-base font-bold text-slate-900 dark:text-slate-50 mt-4 mb-2 border-b border-slate-200 dark:border-slate-700 pb-1.5">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-sm font-bold text-slate-800 dark:text-slate-100 mt-4 mb-1.5 flex items-center gap-2">
      <span className="w-1 h-4 rounded-full bg-blue-500 shrink-0 inline-block" />
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-xs font-bold uppercase tracking-wide text-slate-500 dark:text-slate-400 mt-3 mb-1">
      {children}
    </h3>
  ),
  p: ({ children }) => (
    <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed mb-2 last:mb-0">
      {children}
    </p>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-slate-900 dark:text-slate-100">
      {children}
    </strong>
  ),
  em: ({ children }) => (
    <em className="italic text-slate-600 dark:text-slate-400">{children}</em>
  ),
  ul: ({ children }) => (
    <ul className="space-y-1 my-2 pl-1 list-none">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="space-y-1 my-2 pl-1 list-none">{children}</ol>
  ),
  li: ({ children }: any) => (
    <li className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
      <span className="shrink-0 w-1.5 h-1.5 rounded-full bg-blue-400 mt-2" />
      <span className="flex-1">{children}</span>
    </li>
  ),
  code: ({ children, inline }: any) => {
    const text = String(children).trim();
    if (inline) {
      if (isIdToken(text)) {
        return (
          <span className="inline-block px-1.5 py-0.5 rounded bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300 text-[11px] font-mono font-semibold">
            {text}
          </span>
        );
      }
      return (
        <code className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-[11px] font-mono border border-slate-200 dark:border-slate-700">
          {text}
        </code>
      );
    }
    return (
      <pre className="my-2 p-3 rounded-lg bg-slate-950 dark:bg-slate-900 border border-slate-800 overflow-x-auto">
        <code className="text-[11px] font-mono text-slate-200 leading-relaxed">
          {children}
        </code>
      </pre>
    );
  },
  blockquote: ({ children }) => (
    <blockquote className="my-2 pl-3 border-l-4 border-blue-400 dark:border-blue-600 bg-blue-50/50 dark:bg-blue-950/20 rounded-r-md py-1.5 pr-2 text-sm text-slate-700 dark:text-slate-300 italic">
      {children}
    </blockquote>
  ),
  hr: () => (
    <hr className="my-3 border-t border-slate-200 dark:border-slate-700" />
  ),
  table: ({ children }) => (
    <div className="my-3 w-full overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700 shadow-sm">
      <table className="w-full text-sm border-collapse">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-slate-100 dark:bg-slate-800/80">{children}</thead>
  ),
  tbody: ({ children }) => (
    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
      {children}
    </tbody>
  ),
  tr: ({ children }) => (
    <tr className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
      {children}
    </tr>
  ),
  th: ({ children }) => (
    <th className="px-3 py-2 text-left text-[11px] font-bold uppercase tracking-wide text-slate-500 dark:text-slate-400 whitespace-nowrap border-b border-slate-200 dark:border-slate-700">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-3 py-2 text-xs text-slate-700 dark:text-slate-300 whitespace-nowrap">
      {children}
    </td>
  ),
};

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({
  content,
  className,
}) => {
  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
};

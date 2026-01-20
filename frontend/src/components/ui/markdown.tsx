/**
 * Markdown renderer component with GitHub Flavored Markdown support.
 * Styled for theme support with emerald accents.
 */

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";
import type { Components } from "react-markdown";

interface MarkdownProps {
  content: string;
  className?: string;
}

const components: Components = {
  // Headers
  h1: ({ children, ...props }) => (
    <h1
      className="text-xl font-bold text-foreground mb-3 mt-4 first:mt-0"
      {...props}
    >
      {children}
    </h1>
  ),
  h2: ({ children, ...props }) => (
    <h2
      className="text-lg font-semibold text-foreground mb-2 mt-3 first:mt-0"
      {...props}
    >
      {children}
    </h2>
  ),
  h3: ({ children, ...props }) => (
    <h3
      className="text-base font-semibold text-foreground mb-2 mt-3 first:mt-0"
      {...props}
    >
      {children}
    </h3>
  ),
  h4: ({ children, ...props }) => (
    <h4 className="text-sm font-semibold text-foreground mb-1 mt-2" {...props}>
      {children}
    </h4>
  ),

  // Paragraph
  p: ({ children, ...props }) => (
    <p className="text-foreground/90 mb-2 last:mb-0 leading-relaxed" {...props}>
      {children}
    </p>
  ),

  // Strong/Bold
  strong: ({ children, ...props }) => (
    <strong className="font-semibold text-foreground" {...props}>
      {children}
    </strong>
  ),

  // Emphasis/Italic
  em: ({ children, ...props }) => (
    <em className="italic text-foreground/90" {...props}>
      {children}
    </em>
  ),

  // Links
  a: ({ children, href, ...props }) => (
    <a
      href={href}
      className="text-emerald-600 dark:text-emerald-400 hover:text-emerald-500 dark:hover:text-emerald-300 underline underline-offset-2 transition-colors"
      target="_blank"
      rel="noopener noreferrer"
      {...props}
    >
      {children}
    </a>
  ),

  // Unordered List
  ul: ({ children, ...props }) => (
    <ul className="list-disc list-inside mb-2 space-y-1 text-foreground/90" {...props}>
      {children}
    </ul>
  ),

  // Ordered List
  ol: ({ children, ...props }) => (
    <ol
      className="list-decimal list-inside mb-2 space-y-1 text-foreground/90"
      {...props}
    >
      {children}
    </ol>
  ),

  // List Item
  li: ({ children, ...props }) => (
    <li className="text-foreground/90" {...props}>
      {children}
    </li>
  ),

  // Blockquote
  blockquote: ({ children, ...props }) => (
    <blockquote
      className="border-l-2 border-emerald-500/50 pl-3 my-2 text-muted-foreground italic"
      {...props}
    >
      {children}
    </blockquote>
  ),

  // Inline Code
  code: ({ children, className, ...props }) => {
    // Check if it's a code block (has language class) or inline code
    const isCodeBlock = className?.includes("language-");

    if (isCodeBlock) {
      return (
        <code
          className={cn(
            "block bg-muted rounded-lg p-3 my-2 overflow-x-auto text-sm font-mono text-emerald-600 dark:text-emerald-300",
            className
          )}
          {...props}
        >
          {children}
        </code>
      );
    }

    return (
      <code
        className="bg-muted text-emerald-600 dark:text-emerald-300 px-1.5 py-0.5 rounded text-sm font-mono"
        {...props}
      >
        {children}
      </code>
    );
  },

  // Code Block wrapper
  pre: ({ children, ...props }) => (
    <pre
      className="bg-muted rounded-lg p-3 my-2 overflow-x-auto"
      {...props}
    >
      {children}
    </pre>
  ),

  // Table
  table: ({ children, ...props }) => (
    <div className="overflow-x-auto my-3">
      <table
        className="w-full border-collapse text-sm"
        {...props}
      >
        {children}
      </table>
    </div>
  ),

  // Table Head
  thead: ({ children, ...props }) => (
    <thead className="bg-muted" {...props}>
      {children}
    </thead>
  ),

  // Table Body
  tbody: ({ children, ...props }) => (
    <tbody className="divide-y divide-border" {...props}>
      {children}
    </tbody>
  ),

  // Table Row
  tr: ({ children, ...props }) => (
    <tr className="border-b border-border last:border-0" {...props}>
      {children}
    </tr>
  ),

  // Table Header Cell
  th: ({ children, ...props }) => (
    <th
      className="px-3 py-2 text-left font-semibold text-foreground/90 whitespace-nowrap"
      {...props}
    >
      {children}
    </th>
  ),

  // Table Data Cell
  td: ({ children, ...props }) => (
    <td className="px-3 py-2 text-foreground/80" {...props}>
      {children}
    </td>
  ),

  // Horizontal Rule
  hr: (props) => <hr className="border-border my-4" {...props} />,

  // Strikethrough (GFM)
  del: ({ children, ...props }) => (
    <del className="text-muted-foreground line-through" {...props}>
      {children}
    </del>
  ),
};

export function Markdown({ content, className }: MarkdownProps) {
  return (
    <div className={cn("markdown-content", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}

/**
 * Streaming markdown component that shows a cursor while streaming.
 * Falls back to plain text during streaming to avoid layout jumps.
 */
interface StreamingMarkdownProps {
  content: string;
  isStreaming?: boolean;
  className?: string;
}

export function StreamingMarkdown({
  content,
  isStreaming = false,
  className,
}: StreamingMarkdownProps) {
  if (isStreaming) {
    // While streaming, show plain text with cursor to avoid layout jumps
    return (
      <div className={cn("whitespace-pre-wrap text-foreground/90", className)}>
        {content}
        <span className="inline-block w-2 h-4 ml-0.5 bg-emerald-500 dark:bg-emerald-400 animate-pulse rounded-sm" />
      </div>
    );
  }

  // When done streaming, render full markdown
  return <Markdown content={content} className={className} />;
}

export default Markdown;

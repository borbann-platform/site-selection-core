import { Link } from "@tanstack/react-router";
import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { stripStructuredChatMarkers } from "@/lib/chatReferences";
import { cn } from "@/lib/utils";
import { decorateMarkdownWithEntityLinks } from "@/lib/chatReferences";

interface MarkdownProps {
  content: string;
  className?: string;
}

function InlineCode({ children, className, ...props }: React.ComponentProps<"code">) {
  const isCodeBlock = className?.includes("language-");

  if (isCodeBlock) {
    return (
      <code
        className={cn(
          "block overflow-x-auto rounded-[1.15rem] border border-black/10 bg-stone-950 px-4 py-3 text-[13px] leading-6 text-stone-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] dark:border-white/10 dark:bg-stone-950",
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
      className="rounded-md border border-black/8 bg-black/[0.045] px-1.5 py-0.5 font-mono text-[0.9em] text-foreground dark:border-white/10 dark:bg-white/[0.08]"
      {...props}
    >
      {children}
    </code>
  );
}

const components: Components = {
  h1: ({ children, ...props }) => (
    <h1
      className="mb-4 mt-6 text-[clamp(1.6rem,2vw,2rem)] font-semibold tracking-[-0.03em] text-foreground first:mt-0"
      {...props}
    >
      {children}
    </h1>
  ),
  h2: ({ children, ...props }) => (
    <h2
      className="mb-3 mt-5 text-[clamp(1.25rem,1.6vw,1.5rem)] font-semibold tracking-[-0.025em] text-foreground first:mt-0"
      {...props}
    >
      {children}
    </h2>
  ),
  h3: ({ children, ...props }) => (
    <h3
      className="mb-2 mt-4 text-base font-semibold tracking-[-0.02em] text-foreground first:mt-0"
      {...props}
    >
      {children}
    </h3>
  ),
  h4: ({ children, ...props }) => (
    <h4 className="mb-2 mt-3 text-sm font-semibold uppercase tracking-[0.12em] text-muted-foreground" {...props}>
      {children}
    </h4>
  ),
  p: ({ children, ...props }) => (
    <p className="mb-3 text-[15px] leading-7 text-foreground/88 last:mb-0" {...props}>
      {children}
    </p>
  ),
  strong: ({ children, ...props }) => (
    <strong className="font-semibold text-foreground" {...props}>
      {children}
    </strong>
  ),
  em: ({ children, ...props }) => (
    <em className="italic text-foreground/82" {...props}>
      {children}
    </em>
  ),
  a: ({ children, href, ...props }) => {
    if (typeof href === "string" && href.startsWith("app://property/")) {
      const propertyId = href.slice("app://property/".length);
      return (
        <Link
          to="/property/$propertyId"
          params={{ propertyId }}
          className="inline-flex items-center gap-1 rounded-full border border-brand/20 bg-brand/10 px-2.5 py-1 text-[0.92em] font-medium text-brand no-underline transition-colors hover:bg-brand/16 hover:text-brand"
          {...props}
        >
          {children}
        </Link>
      );
    }

    if (typeof href === "string" && href.startsWith("app://listing/")) {
      const listingKey = decodeURIComponent(href.slice("app://listing/".length));
      return (
        <Link
          to="/listing/$listingKey"
          params={{ listingKey }}
          className="inline-flex items-center gap-1 rounded-full border border-brand/20 bg-brand/10 px-2.5 py-1 text-[0.92em] font-medium text-brand no-underline transition-colors hover:bg-brand/16 hover:text-brand"
          {...props}
        >
          {children}
        </Link>
      );
    }

    return (
      <a
        href={href}
        className="font-medium text-brand underline decoration-brand/35 underline-offset-4 transition-colors hover:text-brand/80"
        target="_blank"
        rel="noopener noreferrer"
        {...props}
      >
        {children}
      </a>
    );
  },
  ul: ({ children, ...props }) => (
    <ul className="mb-3 list-disc space-y-1.5 pl-5 text-[15px] leading-7 text-foreground/88" {...props}>
      {children}
    </ul>
  ),
  ol: ({ children, ...props }) => (
    <ol className="mb-3 list-decimal space-y-1.5 pl-5 text-[15px] leading-7 text-foreground/88" {...props}>
      {children}
    </ol>
  ),
  li: ({ children, ...props }) => (
    <li className="pl-1 marker:text-foreground/45" {...props}>
      {children}
    </li>
  ),
  blockquote: ({ children, ...props }) => (
    <blockquote
      className="my-4 rounded-r-[1.15rem] border-l-[3px] border-brand/55 bg-brand/6 px-4 py-3 text-[15px] italic leading-7 text-foreground/76"
      {...props}
    >
      {children}
    </blockquote>
  ),
  code: InlineCode,
  pre: ({ children, ...props }) => (
    <pre className="my-4 overflow-x-auto" {...props}>
      {children}
    </pre>
  ),
  table: ({ children, ...props }) => (
    <div className="my-4 overflow-x-auto rounded-[1.15rem] border border-black/8 bg-white/80 shadow-[0_14px_40px_rgba(15,23,42,0.06)] dark:border-white/8 dark:bg-white/[0.03]">
      <table className="min-w-full border-collapse text-sm" {...props}>
        {children}
      </table>
    </div>
  ),
  thead: ({ children, ...props }) => (
    <thead className="bg-black/[0.03] text-foreground dark:bg-white/[0.04]" {...props}>
      {children}
    </thead>
  ),
  tbody: ({ children, ...props }) => (
    <tbody className="divide-y divide-black/6 dark:divide-white/8" {...props}>
      {children}
    </tbody>
  ),
  tr: ({ children, ...props }) => <tr {...props}>{children}</tr>,
  th: ({ children, ...props }) => (
    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.14em] text-foreground/58" {...props}>
      {children}
    </th>
  ),
  td: ({ children, ...props }) => (
    <td className="px-4 py-3 text-[14px] leading-6 text-foreground/82" {...props}>
      {children}
    </td>
  ),
  hr: (props) => <hr className="my-5 border-black/8 dark:border-white/10" {...props} />,
  del: ({ children, ...props }) => (
    <del className="text-muted-foreground line-through" {...props}>
      {children}
    </del>
  ),
};

export function Markdown({ content, className }: MarkdownProps) {
  const decoratedContent = decorateMarkdownWithEntityLinks(
    stripStructuredChatMarkers(content)
  );

  return (
    <div className={cn("markdown-content", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {decoratedContent}
      </ReactMarkdown>
    </div>
  );
}

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
    return (
      <div className={cn("whitespace-pre-wrap text-[15px] leading-7 text-foreground/88", className)}>
        {content}
        <span className="ml-1 inline-block h-4 w-2 rounded-full bg-brand/65 align-middle animate-pulse" />
      </div>
    );
  }

  return <Markdown content={content} className={className} />;
}

export default Markdown;

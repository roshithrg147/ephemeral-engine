import React, { useState } from 'react';
import { Copy, Check, Code, Terminal, FileCode } from 'lucide-react';

interface FormattedMarkdownProps {
  content: string;
}

export function FormattedMarkdown({ content }: FormattedMarkdownProps) {
  // Pre-process raw JSON dumps if received
  const cleanContent = React.useMemo(() => {
    if (!content) return '';
    let text = content.trim();

    if (text.startsWith('```json')) {
      const closing = text.lastIndexOf('```');
      if (closing > 7) {
        text = text.substring(7, closing).trim();
      }
    }

    if (text.startsWith('{') && text.endsWith('}')) {
      try {
        const parsed = JSON.parse(text);
        if (parsed && typeof parsed === 'object') {
          const extracted = parsed.text || parsed.message || parsed.content;
          if (extracted && typeof extracted === 'string') {
            return extracted.trim();
          }
        }
      } catch {}
    }

    return text;
  }, [content]);

  // Split into code blocks vs standard text blocks
  const blocks = React.useMemo(() => {
    const result: Array<{ type: 'code' | 'text'; language?: string; content: string }> = [];
    const codeBlockRegex = /```(\w+)?\n([\s\S]*?)```/g;
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = codeBlockRegex.exec(cleanContent)) !== null) {
      if (match.index > lastIndex) {
        result.push({
          type: 'text',
          content: cleanContent.substring(lastIndex, match.index),
        });
      }
      result.push({
        type: 'code',
        language: match[1] || 'code',
        content: match[2].trim(),
      });
      lastIndex = match.index + match[0].length;
    }

    if (lastIndex < cleanContent.length) {
      result.push({
        type: 'text',
        content: cleanContent.substring(lastIndex),
      });
    }

    return result;
  }, [cleanContent]);

  return (
    <div className="space-y-3 text-[14px] leading-relaxed text-text-primary">
      {blocks.map((block, idx) => {
        if (block.type === 'code') {
          return <CodeCard key={idx} language={block.language || 'code'} code={block.content} />;
        }
        return <FormattedTextLines key={idx} text={block.content} />;
      })}
    </div>
  );
}

function CodeCard({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const displayLang = language.toUpperCase();

  return (
    <div className="my-3 rounded-lg border border-border-default bg-[#0d1117] overflow-hidden shadow-md">
      {/* Code Header */}
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-[#161b22] border-b border-border-default text-xs font-mono text-text-secondary select-none">
        <div className="flex items-center gap-1.5">
          {language === 'bash' || language === 'sh' ? (
            <Terminal className="w-3.5 h-3.5 text-accent" />
          ) : (
            <FileCode className="w-3.5 h-3.5 text-accent" />
          )}
          <span className="font-semibold text-[11px] text-text-primary">{displayLang}</span>
        </div>

        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-[11px] px-2 py-1 rounded bg-surface-2 hover:bg-surface-3 text-text-tertiary hover:text-text-primary transition-colors border border-border-subtle"
          title="Copy code"
        >
          {copied ? (
            <>
              <Check className="w-3 h-3 text-status-healthy" />
              <span className="text-status-healthy font-medium">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="w-3 h-3" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>

      {/* Code Body */}
      <pre className="p-3.5 overflow-x-auto text-[13px] font-mono leading-relaxed text-slate-100 bg-[#0d1117]">
        <code>{code}</code>
      </pre>
    </div>
  );
}

function FormattedTextLines({ text }: { text: string }) {
  const lines = text.split('\n');

  return (
    <div className="space-y-1.5">
      {lines.map((line, lineIdx) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={lineIdx} className="h-1" />;

        // Headings
        if (line.startsWith('# ')) {
          return (
            <h1 key={lineIdx} className="text-lg font-bold text-text-primary mt-4 mb-2 border-b border-border-default pb-1">
              {renderInlineFormatting(line.substring(2))}
            </h1>
          );
        }
        if (line.startsWith('## ')) {
          return (
            <h2 key={lineIdx} className="text-base font-bold text-text-primary mt-3.5 mb-1.5 border-b border-border-subtle pb-0.5">
              {renderInlineFormatting(line.substring(3))}
            </h2>
          );
        }
        if (line.startsWith('### ')) {
          return (
            <h3 key={lineIdx} className="text-sm font-semibold text-text-primary mt-3 mb-1">
              {renderInlineFormatting(line.substring(4))}
            </h3>
          );
        }

        // Unordered List (- or *)
        if (/^[-*]\s+/.test(trimmed)) {
          const listContent = trimmed.replace(/^[-*]\s+/, '');
          return (
            <div key={lineIdx} className="flex items-start gap-2 pl-2 my-0.5">
              <span className="text-accent text-xs mt-1 font-bold">•</span>
              <div className="flex-1">{renderInlineFormatting(listContent)}</div>
            </div>
          );
        }

        // Numbered List (1. 2. etc)
        const numMatch = trimmed.match(/^(\d+)\.\s+(.*)/);
        if (numMatch) {
          return (
            <div key={lineIdx} className="flex items-start gap-2 pl-2 my-0.5">
              <span className="text-xs font-mono font-bold text-accent bg-accent/10 px-1.5 py-0.5 rounded border border-accent/20">
                {numMatch[1]}
              </span>
              <div className="flex-1 mt-0.5">{renderInlineFormatting(numMatch[2])}</div>
            </div>
          );
        }

        // Blockquote (> )
        if (trimmed.startsWith('> ')) {
          return (
            <blockquote key={lineIdx} className="border-l-2 border-accent pl-3 italic text-text-secondary my-1 bg-surface-2/40 py-1 rounded-r">
              {renderInlineFormatting(trimmed.substring(2))}
            </blockquote>
          );
        }

        // Standard Paragraph Line
        return <p key={lineIdx}>{renderInlineFormatting(line)}</p>;
      })}
    </div>
  );
}

function renderInlineFormatting(text: string) {
  // Regex to match inline code (`code`), bold (**bold**), and italic (*italic*)
  const tokens: React.ReactNode[] = [];
  let remaining = text;
  let keyIdx = 0;

  while (remaining) {
    // Inline code
    const codeMatch = remaining.match(/^(.*?)`([^`]+)`([\s\S]*)$/);
    if (codeMatch) {
      if (codeMatch[1]) tokens.push(parseBoldItalics(codeMatch[1], keyIdx++));
      tokens.push(
        <code key={`code-${keyIdx++}`} className="px-1.5 py-0.5 mx-0.5 rounded bg-surface-3 text-accent font-mono text-[12px] border border-border-default">
          {codeMatch[2]}
        </code>
      );
      remaining = codeMatch[3];
      continue;
    }

    tokens.push(parseBoldItalics(remaining, keyIdx++));
    break;
  }

  return <>{tokens}</>;
}

function parseBoldItalics(text: string, baseKey: number): React.ReactNode {
  const parts: React.ReactNode[] = [];
  const boldRegex = /\*\*([^*]+)\*\*/g;
  let lastIdx = 0;
  let match: RegExpExecArray | null;

  while ((match = boldRegex.exec(text)) !== null) {
    if (match.index > lastIdx) {
      parts.push(text.substring(lastIdx, match.index));
    }
    parts.push(
      <strong key={`bold-${baseKey}-${match.index}`} className="font-semibold text-text-primary">
        {match[1]}
      </strong>
    );
    lastIdx = match.index + match[0].length;
  }

  if (lastIdx < text.length) {
    parts.push(text.substring(lastIdx));
  }

  return <>{parts}</>;
}

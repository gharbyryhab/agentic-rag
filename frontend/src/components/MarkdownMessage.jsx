import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import SyntaxHighlighter from "react-syntax-highlighter";
import { atomOneDark } from "react-syntax-highlighter/dist/esm/styles/hljs";
import { Check, Copy } from "lucide-react";

// ── Code block with language label + copy button ──────────────────────────────

function CodeBlock({ language, code }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl overflow-hidden my-3">
      {/* Header bar */}
      <div className="flex items-center justify-between bg-[#21252b] px-4 py-2">
        <span className="text-[11px] text-slate-400 font-mono select-none">
          {language ?? "text"}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 text-[11px] text-slate-400
                     hover:text-white transition-colors duration-150"
        >
          {copied ? <Check size={11} /> : <Copy size={11} />}
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>
      {/* Highlighted code */}
      <SyntaxHighlighter
        style={atomOneDark}
        language={language ?? "text"}
        PreTag="div"
        customStyle={{
          margin: 0,
          borderRadius: 0,
          fontSize: "0.8rem",
          padding: "1rem",
          lineHeight: "1.65",
        }}
        wrapLongLines
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}

// ── Component map (stable module-level ref avoids react-markdown rerenders) ───

const MD_COMPONENTS = {
  // Unwrap react-markdown's <pre> so SyntaxHighlighter controls its own wrapper
  pre({ children }) {
    return <>{children}</>;
  },

  code({ node, className, children, ...props }) {
    const lang = /language-(\w+)/.exec(className ?? "")?.[1];
    const codeStr = String(children).replace(/\n$/, "");
    // Block code: has a language tag OR multiline (fenced block without lang)
    if (lang || codeStr.includes("\n")) {
      return <CodeBlock language={lang} code={codeStr} />;
    }
    // Inline code
    return (
      <code
        className="bg-slate-100 text-slate-700 text-[0.82em] font-mono
                   px-1.5 py-0.5 rounded"
        {...props}
      >
        {children}
      </code>
    );
  },

  p({ children }) {
    return <p className="mb-3 last:mb-0 leading-relaxed">{children}</p>;
  },

  a({ node, href, children, ...props }) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-indigo-600 hover:text-indigo-700 underline underline-offset-2
                   transition-colors duration-150"
        {...props}
      >
        {children}
      </a>
    );
  },

  ul({ children }) {
    return (
      <ul className="list-disc list-outside pl-5 mb-3 last:mb-0 space-y-1">
        {children}
      </ul>
    );
  },

  ol({ children }) {
    return (
      <ol className="list-decimal list-outside pl-5 mb-3 last:mb-0 space-y-1">
        {children}
      </ol>
    );
  },

  li({ children }) {
    return <li className="leading-relaxed">{children}</li>;
  },

  h1({ children }) {
    return (
      <h1 className="text-base font-bold text-slate-900 mb-2 mt-4 first:mt-0">
        {children}
      </h1>
    );
  },

  h2({ children }) {
    return (
      <h2 className="text-sm font-bold text-slate-900 mb-2 mt-4 first:mt-0">
        {children}
      </h2>
    );
  },

  h3({ children }) {
    return (
      <h3 className="text-sm font-semibold text-slate-800 mb-1.5 mt-3 first:mt-0">
        {children}
      </h3>
    );
  },

  blockquote({ children }) {
    return (
      <blockquote className="border-l-2 border-slate-300 pl-3 my-2 text-slate-600 italic">
        {children}
      </blockquote>
    );
  },

  strong({ children }) {
    return <strong className="font-semibold text-slate-900">{children}</strong>;
  },

  hr() {
    return <hr className="my-3 border-slate-200" />;
  },

  // GFM tables
  table({ children }) {
    return (
      <div className="overflow-x-auto my-3">
        <table className="text-xs border-collapse w-full">{children}</table>
      </div>
    );
  },
  th({ children }) {
    return (
      <th className="border border-slate-200 bg-slate-50 px-3 py-1.5
                     text-left font-semibold text-slate-700">
        {children}
      </th>
    );
  },
  td({ children }) {
    return (
      <td className="border border-slate-200 px-3 py-1.5 text-slate-600">
        {children}
      </td>
    );
  },
};

// ── Public component ──────────────────────────────────────────────────────────

export default function MarkdownMessage({ content }) {
  return (
    <div className="text-sm text-slate-800">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
        {content}
      </ReactMarkdown>
    </div>
  );
}

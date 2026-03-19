/**
 * MarkdownRenderer.jsx — лёгкий рендерер Markdown (без внешних зависимостей).
 *
 * Поддержка:
 *   • Блоки кода (```lang ... ```) с подсветкой и кнопкой копирования
 *   • Инлайн-код (`code`)
 *   • Заголовки (# ## ### ####)
 *   • Жирный (**text**), курсив (*text*)
 *   • Маркированные и нумерованные списки
 *   • Ссылки [text](url)
 *   • Горизонтальные линии (---)
 *   • Параграфы
 */
import { useState, useCallback } from "react";

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [text]);

  return (
    <button
      className="md-copy-btn"
      onClick={handleCopy}
      title="Копировать"
    >
      {copied ? "✓" : "⧉"}
    </button>
  );
}

function CodeBlock({ language, code }) {
  return (
    <div className="md-code-block">
      <div className="md-code-header">
        <span className="md-code-lang">{language || "code"}</span>
        <CopyButton text={code} />
      </div>
      <pre className="md-code-pre">
        <code>{code}</code>
      </pre>
    </div>
  );
}

/**
 * Парсит инлайн-разметку внутри текстовой строки.
 * Возвращает массив React-элементов.
 */
function parseInline(text, keyPrefix = "il") {
  if (!text) return [text];

  const parts = [];
  let remaining = text;
  let idx = 0;

  // Паттерны (в порядке приоритета)
  const patterns = [
    // inline code
    { re: /`([^`]+)`/, render: (m, k) => <code key={k} className="md-inline-code">{m[1]}</code> },
    // bold
    { re: /\*\*(.+?)\*\*/, render: (m, k) => <strong key={k}>{m[1]}</strong> },
    // italic
    { re: /\*(.+?)\*/, render: (m, k) => <em key={k}>{m[1]}</em> },
    // link
    { re: /\[([^\]]+)\]\(([^)]+)\)/, render: (m, k) => (
      <a key={k} href={m[2]} target="_blank" rel="noopener noreferrer" className="md-link">{m[1]}</a>
    )},
  ];

  while (remaining.length > 0) {
    let earliest = null;
    let earliestIndex = Infinity;
    let matchedPattern = null;

    for (const pat of patterns) {
      const match = remaining.match(pat.re);
      if (match && match.index < earliestIndex) {
        earliest = match;
        earliestIndex = match.index;
        matchedPattern = pat;
      }
    }

    if (!earliest || !matchedPattern) {
      parts.push(remaining);
      break;
    }

    // Текст до совпадения
    if (earliestIndex > 0) {
      parts.push(remaining.slice(0, earliestIndex));
    }

    parts.push(matchedPattern.render(earliest, `${keyPrefix}-${idx}`));
    idx++;

    remaining = remaining.slice(earliestIndex + earliest[0].length);
  }

  return parts;
}


/**
 * Главный компонент.
 */
export default function MarkdownRenderer({ content }) {
  if (!content) return null;

  const text = String(content);
  const elements = [];
  let i = 0;

  // Разбиваем на строки
  const lines = text.split("\n");
  let lineIdx = 0;

  while (lineIdx < lines.length) {
    const line = lines[lineIdx];

    // ── Блоки кода ────────────────────────────────
    if (line.trimStart().startsWith("```")) {
      const lang = line.trimStart().slice(3).trim();
      const codeLines = [];
      lineIdx++;
      while (lineIdx < lines.length && !lines[lineIdx].trimStart().startsWith("```")) {
        codeLines.push(lines[lineIdx]);
        lineIdx++;
      }
      lineIdx++; // Пропускаем закрывающий ```
      elements.push(<CodeBlock key={`cb-${i}`} language={lang} code={codeLines.join("\n")} />);
      i++;
      continue;
    }

    // ── Горизонтальная линия ──────────────────────
    if (/^[-*_]{3,}\s*$/.test(line.trim())) {
      elements.push(<hr key={`hr-${i}`} className="md-hr" />);
      i++;
      lineIdx++;
      continue;
    }

    // ── Заголовки ────────────────────────────────
    const headingMatch = line.match(/^(#{1,4})\s+(.+)/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const Tag = `h${level}`;
      elements.push(
        <Tag key={`h-${i}`} className={`md-heading md-h${level}`}>
          {parseInline(headingMatch[2], `h${i}`)}
        </Tag>
      );
      i++;
      lineIdx++;
      continue;
    }

    // ── Списки (маркированные) ───────────────────
    if (/^\s*[-*+]\s/.test(line)) {
      const listItems = [];
      while (lineIdx < lines.length && /^\s*[-*+]\s/.test(lines[lineIdx])) {
        const itemText = lines[lineIdx].replace(/^\s*[-*+]\s/, "");
        listItems.push(
          <li key={`li-${i}-${listItems.length}`}>{parseInline(itemText, `li${i}${listItems.length}`)}</li>
        );
        lineIdx++;
      }
      elements.push(<ul key={`ul-${i}`} className="md-list">{listItems}</ul>);
      i++;
      continue;
    }

    // ── Списки (нумерованные) ────────────────────
    if (/^\s*\d+[.)]\s/.test(line)) {
      const listItems = [];
      while (lineIdx < lines.length && /^\s*\d+[.)]\s/.test(lines[lineIdx])) {
        const itemText = lines[lineIdx].replace(/^\s*\d+[.)]\s/, "");
        listItems.push(
          <li key={`oli-${i}-${listItems.length}`}>{parseInline(itemText, `oli${i}${listItems.length}`)}</li>
        );
        lineIdx++;
      }
      elements.push(<ol key={`ol-${i}`} className="md-list md-ol">{listItems}</ol>);
      i++;
      continue;
    }

    // ── Пустая строка ────────────────────────────
    if (!line.trim()) {
      lineIdx++;
      continue;
    }

    // ── Обычный параграф ─────────────────────────
    const paraLines = [];
    while (
      lineIdx < lines.length &&
      lines[lineIdx].trim() &&
      !lines[lineIdx].trimStart().startsWith("```") &&
      !lines[lineIdx].match(/^#{1,4}\s/) &&
      !/^\s*[-*+]\s/.test(lines[lineIdx]) &&
      !/^\s*\d+[.)]\s/.test(lines[lineIdx]) &&
      !/^[-*_]{3,}\s*$/.test(lines[lineIdx].trim())
    ) {
      paraLines.push(lines[lineIdx]);
      lineIdx++;
    }

    if (paraLines.length) {
      elements.push(
        <p key={`p-${i}`} className="md-paragraph">
          {parseInline(paraLines.join("\n"), `p${i}`)}
        </p>
      );
      i++;
    }
  }

  return <div className="md-root">{elements}</div>;
}

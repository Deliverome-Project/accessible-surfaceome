export function highlightJSON(obj: unknown): string {
  const json = JSON.stringify(obj, null, 2);
  return json
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"([^"\\]*(?:\\.[^"\\]*)*)"(\s*:)/g, '<span class="k">"$1"</span>$2')
    .replace(/: "([^"\\]*(?:\\.[^"\\]*)*)"/g, ': <span class="s">"$1"</span>')
    .replace(/: (true|false)/g, ': <span class="b">$1</span>')
    .replace(/: (null)/g, ': <span class="nul">$1</span>')
    .replace(/: (-?\d+\.?\d*)/g, ': <span class="n">$1</span>');
}

/*
 * CSS-module stub loader for the viewer's render-test scripts.
 *
 * The viewer's components import CSS modules (``import styles from
 * "./Foo.module.css"``) — Webpack handles those during ``next build`` /
 * ``next dev`` by treating each ``.module.css`` import as an object of
 * generated class names. Plain ``tsx`` (Node + esbuild) has no idea
 * what to do with a stylesheet, so it tries to parse the CSS as JS
 * and explodes on the first ``.foo { ... }`` selector.
 *
 * This loader intercepts every ``*.module.css`` (and plain ``*.css``)
 * import and substitutes a tiny JS stub. The stub exports a ``Proxy``
 * whose ``get`` returns the requested key — so ``styles.sortBtn``
 * returns ``"sortBtn"``, good enough for render-side tests.
 *
 * Wired in via ``tests/helpers/register.mjs`` which is passed to
 * ``node --import`` before the test file runs.
 */
export function load(url, ctx, nextLoad) {
  if (url.endsWith(".module.css") || url.endsWith(".css")) {
    return {
      format: "module",
      source:
        "const stub = new Proxy({}, { get: (_t, k) => (typeof k === 'string' ? k : undefined) });\nexport default stub;\n",
      shortCircuit: true,
    };
  }
  return nextLoad(url, ctx);
}

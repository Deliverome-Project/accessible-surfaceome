/*
 * Wire the CSS-module stub loader into the running Node process via
 * ``module.register``. Imported with ``node --import`` so the loader
 * is active before the test file resolves any imports.
 *
 * Usage:
 *   npx tsx --import ./tests/helpers/register.mjs tests/<file>.test.tsx
 */
import { register } from "node:module";
import { pathToFileURL } from "node:url";

register(
  "./css-loader.mjs",
  pathToFileURL(new URL("./", import.meta.url).pathname),
);

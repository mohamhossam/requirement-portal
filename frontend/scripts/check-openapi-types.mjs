import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";

const root = resolve(import.meta.dirname, "..");
const temporaryDirectory = mkdtempSync(join(tmpdir(), "smb-openapi-"));
const generated = join(temporaryDirectory, "schema.d.ts");
const executable = resolve(
  root,
  "node_modules",
  ".bin",
  process.platform === "win32" ? "openapi-typescript.cmd" : "openapi-typescript",
);

try {
  const result = spawnSync(
    executable,
    ["openapi.json", "-o", generated],
    { cwd: root, stdio: "inherit", shell: process.platform === "win32" },
  );
  if (result.error) console.error(result.error);
  if (result.status !== 0) process.exit(result.status ?? 1);

  const normalize = (value) => value.replaceAll("\r\n", "\n");
  const expected = normalize(readFileSync(resolve(root, "src/api/schema.d.ts"), "utf8"));
  const actual = normalize(readFileSync(generated, "utf8"));
  if (expected !== actual) {
    console.error("src/api/schema.d.ts is stale; run npm run api:generate.");
    process.exit(1);
  }
} finally {
  rmSync(temporaryDirectory, { recursive: true, force: true });
}

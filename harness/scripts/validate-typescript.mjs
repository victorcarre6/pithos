import fs from "node:fs";
import process from "node:process";
import ts from "typescript";

const path = process.argv[2];
if (!path) {
  process.stderr.write("usage: validate-typescript.mjs <path>\n");
  process.exit(2);
}

const source = fs.readFileSync(path, "utf8");
const result = ts.transpileModule(source, {
  fileName: path,
  reportDiagnostics: true,
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
});
const errors = (result.diagnostics ?? []).filter(
  (diagnostic) => diagnostic.category === ts.DiagnosticCategory.Error,
);

for (const diagnostic of errors) {
  const message = ts.flattenDiagnosticMessageText(diagnostic.messageText, "\n");
  process.stderr.write(`TS${diagnostic.code}: ${message}\n`);
}

process.exit(errors.length === 0 ? 0 : 1);


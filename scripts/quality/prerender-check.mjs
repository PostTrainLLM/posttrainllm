export function prerenderOptOut(text, fileName, ts) {
  let sourceText = text;
  if (fileName.endsWith(".astro")) {
    const match = text.match(/^---\s*\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/);
    sourceText = match?.[1] ?? "";
  }
  const source = ts.createSourceFile(
    fileName,
    sourceText,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS,
  );
  let found = false;
  const unwrap = (node) => {
    while (
      node &&
      (ts.isParenthesizedExpression(node) ||
        ts.isAsExpression(node) ||
        ts.isTypeAssertionExpression(node) ||
        ts.isSatisfiesExpression(node) ||
        ts.isNonNullExpression(node))
    )
      node = node.expression;
    return node;
  };
  function visit(node) {
    if (
      ts.isVariableStatement(node) &&
      node.modifiers?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword)
    ) {
      for (const d of node.declarationList.declarations) {
        if (
          ts.isIdentifier(d.name) &&
          d.name.text === "prerender" &&
          unwrap(d.initializer)?.kind !== ts.SyntaxKind.TrueKeyword
        )
          found = true;
      }
    }
    if (
      ts.isExportDeclaration(node) &&
      node.exportClause &&
      ts.isNamedExports(node.exportClause) &&
      node.exportClause.elements.some(
        (element) =>
          element.name.text === "prerender" ||
          element.propertyName?.text === "prerender",
      )
    )
      found = true;
    ts.forEachChild(node, visit);
  }
  visit(source);
  return found;
}

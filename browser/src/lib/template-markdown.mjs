import { authoredHtmlToMarkdown } from "./authored-markdown.mjs";

/** Read authored Astro expressions without evaluating JavaScript or rendering HTML. */
export function authoredExpressions(source) {
  const result = [];
  for (let i = 0; i < source.length; i++) {
    if (source[i] !== "{") continue;
    const start = i;
    let depth = 1;
    let quote = "";
    for (i++; i < source.length && depth; i++) {
      const char = source[i];
      if (quote) {
        if (char === "\\") i++;
        else if (char === quote) quote = "";
      } else if (char === '"' || char === "'" || char === "`") quote = char;
      else if (char === "{") depth++;
      else if (char === "}") depth--;
    }
    if (depth) throw new Error("Unclosed authored expression");
    result.push({ start, end: i, code: source.slice(start + 1, i - 1).trim() });
    i--;
  }
  return result;
}

/** Each expression must be mapped explicitly; no eval or general object traversal. */
export function projectAuthoredTemplate(source, resolve) {
  const expressions = authoredExpressions(source);
  const values = [];
  let result = "",
    cursor = 0;
  for (const expression of expressions) {
    const value = resolve(expression.code);
    if (value === undefined)
      throw new Error(`Unmapped authored expression: ${expression.code}`);
    result += source.slice(cursor, expression.start);
    if (source[expression.start - 1] === "=") {
      if (
        typeof value !== "string" &&
        typeof value !== "number" &&
        typeof value !== "boolean"
      )
        throw new Error("Attribute requires a scalar");
      result += `"${String(value).replaceAll("&", "&amp;").replaceAll('"', "&quot;")}"`;
    } else {
      const marker = `SOURCE_VALUE_${values.length}_END`;
      values.push(String(value));
      result += marker;
    }
    cursor = expression.end;
  }
  result += source.slice(cursor);
  return authoredHtmlToMarkdown(result).replace(
    /SOURCE_VALUE_(\d+)_END/g,
    (_, index) => values[Number(index)],
  );
}

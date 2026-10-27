export function authoredExpressions(
  source: string,
): Array<{ start: number; end: number; code: string }>;
export function projectAuthoredTemplate(
  source: string,
  resolve: (code: string) => string | number | boolean | undefined,
): string;

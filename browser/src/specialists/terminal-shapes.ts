/** Portable terminal allocation bounds, checked before constructing a runtime. */
function parameterSizes(c: Record<string, number>): number[] {
  const d = c.d_model,
    m = c.d_mlp;
  return [
    333 * d,
    c.context_length * d,
    d,
    d,
    ...Array.from({ length: c.n_layers }, () => [
      d,
      d,
      d * d,
      d,
      d * d,
      d,
      d * d,
      d,
      d * d,
      d,
      d,
      d,
      d * m,
      m,
      m * d,
      d,
    ]).flat(),
  ];
}

export function validateConfig(c: Record<string, number>): number[] {
  const limits = {
    context_length: 2048,
    d_model: 256,
    n_heads: 16,
    n_layers: 8,
    d_mlp: 1024,
  };
  if (
    !c ||
    c.vocab_size !== 333 ||
    c.dropout !== 0 ||
    Object.entries(limits).some(
      ([key, max]) => !Number.isInteger(c[key]) || c[key] < 1 || c[key] > max,
    ) ||
    c.d_model % c.n_heads
  )
    throw new Error("Unsupported terminal inference configuration.");
  const sizes = parameterSizes(c),
    count = sizes.reduce((a, b) => a + b, 0);
  const attention = c.n_heads * c.context_length ** 2;
  const activations =
    c.n_layers *
    (attention + c.context_length * (12 * c.d_model + 2 * c.d_mlp));
  const estimatedBytes = 4 * (activations + c.context_length * 333 + 5 * count);
  if (
    count > 5_000_000 ||
    attention * 4 > 128 * 1024 ** 2 ||
    estimatedBytes > 256 * 1024 ** 2
  )
    throw new Error(
      "Terminal artifact exceeds the 256 MiB portable estimated tensor allocation envelope.",
    );
  return sizes;
}

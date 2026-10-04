const ASTRO_VERSION = "7.2.8";

function packageFailure(context) {
  for (const [label, pkg] of Object.entries(context.packages ?? {})) {
    if (!pkg.devDependencies?.astro)
      return `${label} Astro is no longer dev-only`;
    if (pkg.dependencies?.astro || pkg.dependencies?.["http-cache-semantics"])
      return `${label} vulnerable graph moved into runtime dependencies`;
  }
  if (
    context.packages?.browser?.devDependencies?.astro !== "^7.2.8" ||
    context.packages?.docsSite?.devDependencies?.astro !== ASTRO_VERSION
  )
    return "Astro package declaration changed; requalify the dependency graph";
  return "";
}

function versionsFailure(lockfile) {
  if (!lockfile?.includes("http-cache-semantics@4.2.0"))
    return "lockfile no longer has the qualified package snapshot";
  const versions = [
    ...(lockfile ?? "").matchAll(/^  astro@([^(:]+)(?:\(|:)/gm),
  ].map((match) => match[1]);
  if (
    versions.length === 0 ||
    versions.some((version) => version !== ASTRO_VERSION)
  )
    return "Astro version changed; requalify framework behavior";
  return "";
}

function importerFailure(lockfile, importer) {
  const marker = `  ${importer}:\n`;
  const start = lockfile.indexOf(marker);
  if (start < 0) return `${importer} lock importer is missing`;
  const tail = lockfile.slice(start + marker.length);
  const devStart = tail.indexOf("    devDependencies:\n");
  if (devStart < 0) return `${importer} Astro is no longer a dev dependency`;
  const section = tail.slice(devStart + "    devDependencies:\n".length);
  const lines = section.split("\n");
  const astro = lines.indexOf("      astro:");
  const exact =
    astro >= 0 &&
    lines[astro + 1] ===
      `        specifier: ${importer === "browser" ? "^" : ""}7.2.8` &&
    lines[astro + 2]?.startsWith("        version: 7.2.8(");
  return exact
    ? ""
    : `${importer} lock importer no longer pins Astro 7.2.8 as a dev dependency`;
}

export function packageAndLockFailure(context) {
  const packageError = packageFailure(context);
  if (packageError) return packageError;
  const versionError = versionsFailure(context.lockfile);
  if (versionError) return versionError;
  for (const importer of ["browser", "docs-site"]) {
    const error = importerFailure(context.lockfile ?? "", importer);
    if (error) return error;
  }
  return "";
}

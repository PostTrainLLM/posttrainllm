export const siteIdentity = {
  name: "PostTrainLLM",
  url: "https://posttrainllm.com",
  summary:
    "A Mac-local LLM specialist factory: post-training, evidence-gated packaging, MLX runtime work, and a WebGPU learning playground.",
  logo: "https://posttrainllm.com/favicon.svg",
  sameAs: ["https://github.com/PostTrainLLM/posttrainllm"],
  openapi: "https://posttrainllm.com/openapi.json",
  trainingAllowed: true,
  excludedPaths: [
    "/api (except public discovery)",
    "/auth",
    "/admin",
    "browser-local uploads, progress, model state, and unpublished factory runs",
  ],
};
export const identitySchema = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": `${siteIdentity.url}/#organization`,
      name: siteIdentity.name,
      url: siteIdentity.url,
      logo: siteIdentity.logo,
      sameAs: siteIdentity.sameAs,
    },
    {
      "@type": "WebSite",
      "@id": `${siteIdentity.url}/#app`,
      name: siteIdentity.name,
      url: siteIdentity.url,
      description: siteIdentity.summary,
      publisher: { "@id": `${siteIdentity.url}/#organization` },
    },
  ],
};

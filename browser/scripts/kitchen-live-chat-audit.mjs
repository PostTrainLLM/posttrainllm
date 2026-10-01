// One actual optimizer step and same-model inference/export; no external pretrained chat.
process.env.LIVE_COOK = "1";
await import("./kitchen-cook-audit.mjs");

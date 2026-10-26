/** Keep the pthread bootstrap as its own module under COOP/COEP. */
import * as ort from "onnxruntime-web/wasm";
import wasmUrl from "onnxruntime-web/ort-wasm-simd-threaded.wasm?url";
import mjsUrl from "onnxruntime-web/ort-wasm-simd-threaded.mjs?url";

// Embedded Emscripten glue starts its pthread at import.meta.url. In a bundled
// application worker that re-enters our message handler instead of the glue.
ort.env.wasm.wasmPaths = { wasm: wasmUrl, mjs: mjsUrl };
ort.env.wasm.numThreads = 2;
export { ort };

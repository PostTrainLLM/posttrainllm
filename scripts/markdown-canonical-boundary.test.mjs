import assert from 'node:assert/strict';
import test from 'node:test';
import { createAgentSurfaceManifest } from '../browser/src/lib/agent-surfaces/manifest.mjs';
import { createAgentSurfaceHandler } from '../browser/src/lib/agent-surfaces/handler.mjs';

test('unknown Markdown paths cannot advertise a foreign canonical origin', async () => {
  const origin = 'https://public.example';
  const manifest = createAgentSurfaceManifest({name:'Public',url:origin,summary:'Public source',pages:{'/':'# Home\n'}});
  const handler = createAgentSurfaceHandler({manifest});
  for (const path of ['/api/md//evil.example/x', '//evil.example/x.md']) {
    const response = await handler(new Request(origin + path));
    assert.equal(response.status,404,path);
    assert.equal(new URL(response.headers.get('Content-Location')).origin,origin,path);
    assert.ok(response.headers.get('Link').startsWith(`<${origin}/`),path);
  }
});

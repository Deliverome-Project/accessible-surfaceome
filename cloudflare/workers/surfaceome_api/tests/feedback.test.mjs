import { test, mock } from 'node:test';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import worker from './worker.bundle.mjs';

const base = 'https://api.example.org/surfaceome';
const pdf = new File(['%PDF-1.7\npaper content'], 'paper.pdf', { type: 'application/pdf' });
const fields = { gene: 'GENE1', name: 'Reader', email: 'reader@example.org', subject: 'Paper', comment: 'New evidence', turnstile_token: 'ok', public_requested: false, paper_rights_confirmed: true };
function form(files = [pdf], overrides = {}) {
  const data = new FormData();
  for (const [key, value] of Object.entries({ ...fields, ...overrides })) data.set(key, String(value));
  for (const file of files) data.append('papers', file);
  return new Request(`${base}/v1/feedback/submit`, { method: 'POST', body: data });
}
function setup(t, { emailFailure = false, storageFailure = false, dbFailure = false, turnstile = true } = {}) {
  const objects = new Map(), rows = new Map(), emails = [], batches = [], queries = [];
  const env = {
    MAGIC_LINK_SECRET: 'test-secret', TURNSTILE_SECRET_KEY: 'test-turnstile',
    RESEND_API_KEY: 'test-resend', MAINTAINER_EMAIL: 'maintainer@example.org',
    FEEDBACK_RATELIMIT: { get: async () => null, put: async () => {} },
    FEEDBACK_PAPERS: {
      async put(key, stream) { if (storageFailure) throw new Error('R2 failed'); objects.set(key, await new Response(stream).text()); },
      async get(key) { return objects.has(key) ? { body: objects.get(key) } : null; },
    },
    FEEDBACK_DB: {
      prepare(sql) { return { bind(...args) { return { sql, args, first: async () => rows.get(args[0]) }; } }; },
      async batch(statements) {
        if (dbFailure) throw new Error('D1 failed');
        batches.push(statements);
        for (const { sql, args } of statements) if (sql.includes('INSERT INTO feedback_paper')) rows.set(args[0], { object_key: args[2], filename: args[3] });
      },
    },
    DB: { prepare(sql) { return { bind(...args) { queries.push({ sql, args }); return { all: async () => ({ results: Array.from({ length: 51 }, (_, i) => ({ id: String(i), gene_symbol: 'GENE1', comment: 'approved' })) }) }; } }; } },
  };
  t.mock.method(globalThis, 'fetch', async (url, init) => {
    if (url.includes('siteverify')) return Response.json({ success: turnstile });
    assert.equal(url, 'https://api.resend.com/emails');
    emails.push(JSON.parse(init.body));
    return new Response('{}', { status: emailFailure ? 500 : 200 });
  });
  return { env, objects, rows, emails, batches, queries };
}
async function submit(state, request = form()) { return worker.fetch(request, state.env, {}); }
function paperUrl(email) {
  return email.html.match(/href="([^"]+\/v1\/feedback\/paper[^\"]+)"/)[1].replaceAll('&amp;', '&');
}
test('PDF is persisted privately, attached to email and downloadable only with its signed link', async t => {
  const state = setup(t);
  const response = await submit(state);
  assert.equal(response.status, 200);
  assert.equal(state.objects.size, 1);
  assert.match(state.batches[0][1].args[5], /authorized to upload each attached version/);
  assert.equal(state.batches[0][0].args[7], 0, 'multipart false does not publish');
  const email = state.emails[0];
  assert.equal(Buffer.from(email.attachments[0].content, 'base64').toString(), await pdf.text());
  const link = paperUrl(email);
  const download = await worker.fetch(new Request(link), state.env, {});
  assert.equal(download.status, 200);
  assert.equal(await download.text(), await pdf.text());
  assert.equal(download.headers.get('Cache-Control'), 'private, no-store');
  assert.match(download.headers.get('Content-Disposition'), /^attachment;/);
  const invalid = new URL(link); invalid.searchParams.set('t', 'forged');
  assert.equal((await worker.fetch(new Request(invalid), state.env, {})).status, 403);
  invalid.searchParams.delete('t');
  assert.equal((await worker.fetch(new Request(invalid), state.env, {})).status, 403);
  const otherPaper = new URL(link); otherPaper.searchParams.set('id', crypto.randomUUID());
  assert.equal((await worker.fetch(new Request(otherPaper), state.env, {})).status, 403);
});

test('mixed-case gene symbols work for submissions and both public routes', async t => {
  const state = setup(t);
  assert.equal((await submit(state, form([], { gene: 'C11orf24' }))).status, 200);
  assert.equal(state.batches[0][0].args[1], 'C11orf24');
  for (const path of ['/v1/feedback/public?gene=C11orf24', '/v1/genes/C11orf24/feedback']) {
    const response = await worker.fetch(new Request(base + path), state.env, {});
    assert.equal(response.status, 200);
    assert.equal((await response.json()).gene, 'C11orf24');
  }
  for (const query of state.queries) assert.match(query.sql, /gene_symbol = \? COLLATE NOCASE/);
});

test('invalid public filters are rejected before querying the database', async t => {
  const state = setup(t);
  for (const query of ['gene=', 'gene=a%20b', 'offset=-1', 'offset=1.5', 'offset=10000000']) {
    const response = await worker.fetch(new Request(`${base}/v1/feedback/public?${query}`), state.env, {});
    assert.equal(response.status, 400);
  }
  assert.equal(state.queries.length, 0);
});
test('expired signed links are denied', async t => {
  const state = setup(t); const id = crypto.randomUUID(); const expires = '1000000000';
  const token = createHmac('sha256', state.env.MAGIC_LINK_SECRET).update(`paper:${id}:${expires}`).digest('base64url');
  const response = await worker.fetch(new Request(`${base}/v1/feedback/paper?id=${id}&expires=${expires}&t=${token}`), state.env, {});
  assert.equal(response.status, 403);
  assert.equal(response.headers.get('Cache-Control'), 'private, no-store');
});
test('legacy JSON submissions work without R2 or attachments', async t => {
  const state = setup(t); delete state.env.FEEDBACK_PAPERS;
  const response = await submit(state, new Request(`${base}/v1/feedback/submit`, { method: 'POST', body: JSON.stringify(fields) }));
  assert.equal(response.status, 200); assert.equal(state.emails[0].attachments, undefined);
});
test('rejects disguised PDFs, too many files, and oversized requests before persisting', async t => {
  const state = setup(t);
  for (const [request, code] of [
    [form([new File(['html'], 'paper.pdf', { type: 'application/pdf' })]), 'invalid_pdf'],
    [form([pdf, pdf, pdf, pdf]), 'too_many_papers'],
    [form([new File(['%PDF-', new Uint8Array(10 * 1024 * 1024)], 'big.pdf')]), 'upload_too_large'],
  ]) {
    const response = await submit(state, request); assert.equal((await response.json()).error, code);
  }
  assert.equal(state.batches.length, 0); assert.equal(state.objects.size, 0);
});
test('stream limit rejects a body with no Content-Length', async t => {
  const state = setup(t);
  const request = new Request(`${base}/v1/feedback/submit`, {
    method: 'POST', duplex: 'half',
    body: new ReadableStream({ start(c) { c.enqueue(new Uint8Array(65537)); c.close(); } }),
  });
  assert.equal((await submit(state, request)).status, 413);
});
test('missing upload storage returns an actionable error', async t => {
  const state = setup(t); delete state.env.FEEDBACK_PAPERS;
  const response = await submit(state); assert.equal(response.status, 503);
  assert.equal((await response.json()).error, 'uploads_unavailable');
});
test('Turnstile rejection prevents storage and email', async t => {
  const state = setup(t, { turnstile: false });
  assert.equal((await submit(state)).status, 400);
  assert.equal(state.objects.size, 0); assert.equal(state.emails.length, 0);
});
test('storage failures do not report success or email incomplete submissions', async t => {
  for (const options of [{ storageFailure: true }, { dbFailure: true }]) {
    const state = setup(t, options);
    assert.equal((await submit(state)).status, 503);
    assert.equal(state.emails.length, 0);
    mock.restoreAll();
  }
});
test('email failure preserves the feedback and papers', async t => {
  const state = setup(t, { emailFailure: true });
  assert.equal((await submit(state)).status, 200);
  assert.equal(state.objects.size, 1); assert.equal(state.rows.size, 1); assert.equal(state.batches.length, 1);
});
test('public feeds support gene filtering, gene URL and broad pagination without private fields', async t => {
  const state = setup(t);
  for (const path of ['/v1/feedback/public', '/v1/feedback/public?gene=GENE1&offset=50', '/v1/genes/GENE1/feedback']) {
    const response = await worker.fetch(new Request(base + path), state.env, {});
    assert.equal(response.status, 200);
    assert.equal(response.headers.get('Cache-Control'), 'no-store');
    const body = await response.json(); assert.equal(body.notes.length, 50);
    assert.equal(body.next_offset, path.includes('offset=50') ? 100 : 50);
  }
  assert.deepEqual(state.queries.map(q => q.args), [[0], ['GENE1', 50], ['GENE1', 0]]);
  for (const { sql } of state.queries) {
    assert.match(sql, /FROM feedback_public/);
    assert.doesNotMatch(sql, /email|object_key|feedback_paper|SELECT \*/);
  }
});

test('uploads require explicit rights acknowledgment, including multipart false', async t => {
  const state = setup(t);
  for (const value of [false, '', 'yes']) {
    const response = await submit(state, form([pdf], { paper_rights_confirmed: value }));
    assert.equal(response.status, 400);
    assert.equal((await response.json()).error, 'paper_rights_required');
  }
  assert.equal(state.objects.size, 0);
});

// Synthetic DOM/network only. Never drives a real human-appraisal session.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

function fixture() {
  class Element {
    constructor() {this.children = []; this.textContent = ''; this.hidden = false;}
    append(...items) {this.children.push(...items);}
    replaceChildren() {this.children = []; this.textContent = '';}
    reset() {}
  }
  const elements = {}, requests = [], events = {}, replacements = [];
  const element = id => elements[id] ||= new Element();
  const context = vm.createContext({
    document: {getElementById: element, createElement: () => new Element(), createTextNode: value => value},
    location: {hash: '#synthetic-review-token'}, history: {replaceState: (...args) => replacements.push(args)},
    fetch: (url, options) => new Promise(resolve => requests.push({url, options,
      respond: value => resolve({ok: true, json: async () => value})})),
    window: {addEventListener: (name, callback) => events[name] = callback}, setInterval() {},
    FormData: class {get() {return 'true';}}
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, 'knowledge_human_review.js'), 'utf8'), context);
  return {context, element, requests, events, replacements};
}
const tick = () => new Promise(resolve => setImmediate(resolve));
const state = {status: 'review', nonce: 'synthetic-nonce', packet: {
  caseId: 'SYNTHETIC', question: '<script>must remain text</script>', answerSummary: 'Synthetic answer',
  points: [{quote: 'Synthetic quote', citation: {title: '<img onerror="no execution">'}}],
  evidence: [{evidenceRef: 'e1', content: 'Synthetic source', title: 'Source'}]
}};

test('no automatic human response; markup remains literal; fragment cleared', async () => {
  const f = fixture(); f.requests[0].respond(state); await tick();
  assert.equal(f.element('question').textContent, state.packet.question);
  assert.equal(f.requests.length, 1);
  assert.equal(f.requests[0].url, '/state');
  assert.equal(f.replacements[0][2], '/');
  assert.equal(f.element('rubric').children.length, 4);
  for (const field of f.element('rubric').children) {
    for (const label of field.children.slice(1)) assert.equal(label.children[0].checked, undefined);
  }
});

test('a stale poll cannot redisplay a submitted answer', async () => {
  const f = fixture(); f.requests[0].respond(state); await tick();
  const polling = vm.runInContext('poll()', f.context);
  assert.equal(f.requests.length, 2);
  f.element('ack').checked = true; f.element('reason').value = 'none';
  const submission = f.element('form').onsubmit({preventDefault() {}});
  assert.equal(f.requests[2].url, '/decision');
  f.requests[2].respond({accepted: true}); await submission;
  assert.equal(f.element('review').hidden, true);
  f.requests[1].respond(state); await polling;
  assert.equal(f.element('review').hidden, true);
  assert.equal(f.element('question').textContent, '');
});

test('closing the page cancels with a finite body and clears all content', async () => {
  const f = fixture(); f.requests[0].respond(state); await tick();
  f.events.pagehide();
  assert.equal(f.requests[1].url, '/close');
  assert.equal(f.requests[1].options.body, '{"close":true}');
  assert.equal(f.requests[1].options.keepalive, true);
  assert.equal(f.element('question').textContent, '');
  assert.equal(f.element('review').hidden, true);
});

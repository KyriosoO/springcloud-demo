const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const pagePath = path.resolve(__dirname, '../../main/resources/static/agent.html');
const page = fs.readFileSync(pagePath, 'utf8');
const script = page.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(script, 'agent.html must contain its render script');

function render(result) {
    const classes = new Set(['empty']);
    const processedText = {
        textContent: '',
        classList: {
            add: value => classes.add(value),
            remove: value => classes.delete(value),
            toggle: (value, active) => active ? classes.add(value) : classes.delete(value)
        },
        set innerHTML(_value) {
            throw new Error('unsafe HTML rendering');
        }
    };
    const elements = new Map([
        ['processedText', processedText],
        ['question', {value: '', focus() {}}],
        ['run', {addEventListener() {}}],
        ['clear', {addEventListener() {}}],
        ['status', {textContent: ''}]
    ]);
    const context = vm.createContext({document: {getElementById: id => elements.get(id)}});
    vm.runInContext(script, context, {timeout: 1000, filename: pagePath});
    context.renderProcessedText(result);
    return {text: processedText.textContent, empty: classes.has('empty')};
}

test('cited limited answer displays each claim with its own quote and citation', () => {
    const result = render({
        summaryType: 'cited_limited_answer',
        answerSummary: '1. 若题述事实准确，可按所引条款判断。\n2. 仅按指定条款，仍需核实条件。',
        points: [
            {quote: '模拟原文A', citation: {evidenceId: 'ev-a', title: '文件甲', documentNumber: '甲〔1〕号'}},
            {quote: '模拟原文B', citation: {evidenceId: 'ev-b', title: '文件乙', writtenDate: '2026-01-01'}}
        ]
    });
    assert.equal(result.empty, false);
    assert.match(result.text, /第1点有限回答：若题述事实准确，可按所引条款判断。\n第1点原文依据：模拟原文A\n第1点引用：ev-a · 文件甲 · 甲〔1〕号/);
    assert.match(result.text, /第2点有限回答：仅按指定条款，仍需核实条件。\n第2点原文依据：模拟原文B\n第2点引用：ev-b · 文件乙 · 2026-01-01/);
});

test('unpaired limited answer fails closed in the summary panel', () => {
    const result = render({
        summaryType: 'cited_limited_answer',
        answerSummary: '1. 有限判断',
        points: []
    });
    assert.equal(result.empty, true);
    assert.match(result.text, /无法逐点对应/);
    assert.doesNotMatch(result.text, /有限判断/);
});

test('missing citation identity fails closed in the summary panel', () => {
    const result = render({
        summaryType: 'cited_limited_answer',
        answerSummary: '1. 有限判断',
        points: [{quote: '模拟原文', citation: {title: '文件甲'}}]
    });
    assert.equal(result.empty, true);
    assert.match(result.text, /无法逐点对应/);
    assert.doesNotMatch(result.text, /有限判断/);
});

test('extractive result retains the verified summary rendering', () => {
    assert.deepEqual(render({summaryType: 'extractive_evidence', answerSummary: '1. 原文摘录'}), {
        text: '1. 原文摘录', empty: false
    });
});

test('untrusted citation text remains inert plain text', () => {
    const result = render({
        summaryType: 'cited_limited_answer',
        answerSummary: '1. 有限判断',
        points: [{quote: '<img src=x onerror=alert(1)>', citation: {evidenceId: 'ev-x', title: '<script>alert(1)</script>'}}]
    });
    assert.match(result.text, /<img src=x onerror=alert\(1\)>/);
    assert.match(result.text, /<script>alert\(1\)<\/script>/);
});

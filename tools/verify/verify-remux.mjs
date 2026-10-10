// Exercise generator regression outputs with the vendored AIOStreams evaluator.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { StreamSelector } from './dist/vendor/streamExpression.js';

const directory = process.argv[2];
const items = JSON.parse(readFileSync(join(directory, '1080p-remux.expressions.json')));
const regexes = JSON.parse(readFileSync(join(directory, '1080p-remux.regexes.json')));
const addon = {
  preset: { id: 'fixture', type: 'fixture', options: {} },
  manifestUrl: 'https://fixture.local/manifest.json', enabled: true,
  name: 'fixture', timeout: 20000,
};
for (const queryType of ['movie', 'series']) {
  const selector = new StreamSelector({ queryType });
  for (const [group, remux, quality, expectedTier] of [
    ['SiCFoI', true, 'BluRay REMUX', 'Remux Tier 4'],
    ['BTN', true, 'BluRay REMUX', 'Remux Tier 4'],
    ['ATELiER', true, 'BluRay REMUX', 'Remux Tier 3'],
    ['UNKNOWN', true, 'BluRay REMUX', null],
    ['SiCFoI', false, 'BluRay', null],
    ['SiCFoI', true, 'DVD REMUX', null],
  ]) {
    const filename = `Example.2026.1080p.${remux ? 'REMUX.' : ''}x264-${group}.mkv`;
    const stream = { id: 'fixture', type: 'debrid', addon, filename,
      parsedFile: { quality, resolution: '1080p', audioChannels: [],
        visualTags: [], audioTags: [], languages: [] },
      rankedRegexesMatched: regexes.filter(({ pattern }) => {
        const end = pattern.lastIndexOf('/');
        return new RegExp(pattern.slice(1, end), pattern.slice(end + 1)).test(filename);
      }).map(({ name }) => name) };
    const selected = [];
    for (const item of items) {
      if ((await selector.select([stream], item.expression)).length) selected.push(item);
    }
    assert.equal(selected.length, expectedTier ? 1 : 0, `${queryType}: ${filename} / ${quality}`);
    if (expectedTier) {
      assert.ok(selected[0].expression.includes(`/*${expectedTier}*/`));
      assert.equal(selected[0].score, expectedTier.endsWith('4') ? 200 : 300);
    }
  }
  // Arr rule: required title passes regardless of an optional title match.
  // Check the equivalent required-only expression against the actual engine.
  for (const [names, expected] of [[['Remux'], 1], [['SiCFoI'], 0], [['Remux', 'SiCFoI'], 1], [[], 0]]) {
    const stream = { id: 'required-fixture', type: 'debrid', addon, rankedRegexesMatched: names };
    assert.equal((await selector.select([stream], 'regexMatched(streams, "Remux")')).length, expected);
  }
}
console.log('PASS: SiCFoI move, existing groups, required title, DVD exclusion, movie/series');

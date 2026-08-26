import assert from "node:assert/strict";
import test from "node:test";

import {normalizeSpectrum, smoothLevels, splitFrequencyBands} from "../web/audio-core.mjs";


test("normalizes analyser bytes", () => {
  assert.deepEqual(normalizeSpectrum(new Uint8Array([0, 128, 255])), [0, 128 / 255, 1]);
});


test("splits silence and isolated bands", () => {
  assert.deepEqual(splitFrequencyBands([]), [0, 0, 0]);
  assert.deepEqual(splitFrequencyBands([1, 1, 0, 0, 0, 0]), [1, 0, 0]);
  assert.deepEqual(splitFrequencyBands([0, 0, 1, 1, 0, 0]), [0, 1, 0]);
  assert.deepEqual(splitFrequencyBands([0, 0, 0, 0, 1, 1]), [0, 0, 1]);
});


test("smooths each band independently", () => {
  const result = smoothLevels([0, 0.5, 1], [1, 0.5, 0], 0.25);

  assert.deepEqual(result, [0.25, 0.5, 0.75]);
});

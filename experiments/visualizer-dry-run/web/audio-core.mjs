export function normalizeSpectrum(bytes) {
  return Array.from(bytes, (value) => value / 255);
}


export function splitFrequencyBands(spectrum) {
  if (spectrum.length === 0) {
    return [0, 0, 0];
  }

  const firstBoundary = Math.floor(spectrum.length / 3);
  const secondBoundary = Math.floor((2 * spectrum.length) / 3);
  const slices = [
    spectrum.slice(0, firstBoundary),
    spectrum.slice(firstBoundary, secondBoundary),
    spectrum.slice(secondBoundary),
  ];

  return slices.map(mean);
}


export function smoothLevels(previous, current, alpha) {
  return previous.map((value, index) => {
    const retained = value * (1 - alpha);
    const incoming = current[index] * alpha;

    return retained + incoming;
  });
}


function mean(values) {
  if (values.length === 0) {
    return 0;
  }

  const total = values.reduce((sum, value) => sum + value, 0);

  return total / values.length;
}

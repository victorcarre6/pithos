import {normalizeSpectrum, smoothLevels, splitFrequencyBands} from "./audio-core.mjs";


const themes = {
  neon: ["#00f6ff", "#ff2bd6", "#ffe600"],
  acid: ["#a7ff00", "#00ff9d", "#9d00ff"],
  ember: ["#ff3b1f", "#ff8a00", "#ffdf6c"],
};

const canvas = document.querySelector("canvas");
const context = canvas.getContext("2d");
const deviceSelect = document.querySelector("#device");
const status = document.querySelector("#status");
const startButton = document.querySelector("#start");
const fullscreenButton = document.querySelector("#fullscreen");
const themeSelect = document.querySelector("#theme");

let audioContext;
let analyser;
let stream;
let animationFrame;
let levels = [0, 0, 0];


async function start(deviceId = "") {
  stopStream();

  const audio = deviceId ? {deviceId: {exact: deviceId}} : true;
  stream = await navigator.mediaDevices.getUserMedia({audio, video: false});
  audioContext ??= new AudioContext();
  await audioContext.resume();

  const source = audioContext.createMediaStreamSource(stream);
  analyser = audioContext.createAnalyser();
  analyser.fftSize = 1024;
  analyser.smoothingTimeConstant = 0;
  source.connect(analyser);

  await refreshDevices();
  status.textContent = "live";
  startButton.textContent = "restart";
  draw();
}


async function startSelectedDevice() {
  status.textContent = "requesting audio…";
  try {
    await start(deviceSelect.value);
  } catch (error) {
    const denied = error.name === "NotAllowedError";
    status.textContent = denied ? "audio permission denied" : "audio unavailable";
  }
}


function stopStream() {
  if (animationFrame) {
    cancelAnimationFrame(animationFrame);
  }
  if (stream) {
    stream.getTracks().forEach((track) => track.stop());
  }
}


async function refreshDevices() {
  const devices = await navigator.mediaDevices.enumerateDevices();
  const inputs = devices.filter((device) => device.kind === "audioinput");
  const selected = deviceSelect.value;
  deviceSelect.replaceChildren();

  inputs.forEach((device, index) => {
    const option = document.createElement("option");
    option.value = device.deviceId;
    option.textContent = device.label || `audio input ${index + 1}`;
    deviceSelect.append(option);
  });

  if (inputs.some((device) => device.deviceId === selected)) {
    deviceSelect.value = selected;
  }
}


function draw() {
  resizeCanvas();

  const bytes = new Uint8Array(analyser.frequencyBinCount);
  analyser.getByteFrequencyData(bytes);
  const spectrum = normalizeSpectrum(bytes);
  const current = splitFrequencyBands(spectrum);
  levels = smoothLevels(levels, current, 0.22);

  drawBackground();
  drawBands(levels, themes[themeSelect.value]);
  animationFrame = requestAnimationFrame(draw);
}


function resizeCanvas() {
  const ratio = window.devicePixelRatio || 1;
  const width = Math.floor(window.innerWidth * ratio);
  const height = Math.floor(window.innerHeight * ratio);
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
}


function drawBackground() {
  context.fillStyle = "rgba(3, 4, 12, 0.22)";
  context.fillRect(0, 0, canvas.width, canvas.height);
}


function drawBands(values, colors) {
  const bandWidth = canvas.width / values.length;
  values.forEach((value, index) => {
    const padding = bandWidth * 0.16;
    const height = Math.max(4, value * canvas.height * 0.88);
    const x = index * bandWidth + padding;
    const y = canvas.height - height;

    context.shadowBlur = 42;
    context.shadowColor = colors[index];
    context.fillStyle = colors[index];
    context.fillRect(x, y, bandWidth - 2 * padding, height);
  });
  context.shadowBlur = 0;
}


startButton.addEventListener("click", startSelectedDevice);
deviceSelect.addEventListener("change", startSelectedDevice);
fullscreenButton.addEventListener("click", async () => {
  try {
    await document.documentElement.requestFullscreen();
  } catch {
    status.textContent = "fullscreen unavailable";
  }
});
window.addEventListener("beforeunload", stopStream);

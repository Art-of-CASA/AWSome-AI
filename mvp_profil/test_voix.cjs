// Régression : la calibration initiale ne doit pas jeter le premier mot.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync(path.join(__dirname, 'composant_voix', 'index.html'), 'utf8');
const source = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const messages = [];
const elements = new Map();
const element = (id) => {
  if (!elements.has(id)) elements.set(id, {style: {}, textContent: '', className: ''});
  return elements.get(id);
};
const contexte = vm.createContext({
  window: {parent: {postMessage: (m) => messages.push(m)}, addEventListener: () => {}},
  document: {getElementById: element, body: {scrollHeight: 80}, documentElement: {style: {setProperty() {}}}},
  setTimeout() {}, btoa: (s) => Buffer.from(s, 'binary').toString('base64'),
  navigator: {}, assert, messages,
});
vm.runInContext(source, contexte);
vm.runInContext(`
  tauxEntree = 16000;
  demarre = true;
  ecouter();
  const trame = (amplitude) => ({inputBuffer: {getChannelData: () => new Float32Array(2048).fill(amplitude)}});
  // La personne commence à répondre dès « Je vous écoute », avant la fin des 700 ms.
  for (let i = 0; i < 4; i++) traiterAudio(trame(0.08));
  assert.equal(parole, true, 'La première parole doit être détectée pendant la calibration.');
  assert.ok(tampon.length > 0, 'Le premier mot doit rester dans le tampon.');
  for (let i = 0; i < 10; i++) traiterAudio(trame(0));
  const audios = messages.filter(m => m.value && m.value.kind === 'audio');
  assert.equal(audios.length, 1, 'Une seule réponse complète est envoyée.');
  assert.ok(audios[0].value.wav.length > 100, 'Le WAV contient les échantillons conservés.');
  assert.ok(seuil < 0.03, 'La parole ne doit pas être calibrée comme bruit de fond.');
  etat = 'parle';
  for (let i = 0; i < 10; i++) traiterAudio(trame(0.08));
  assert.equal(messages.filter(m => m.value && m.value.kind === 'audio').length, 1,
    'La voix de la question ne crée pas une réponse utilisateur.');
`, contexte);
console.log('Voix OK : premier mot conservé pendant la calibration, un envoi unique, aucun écho de la question.');

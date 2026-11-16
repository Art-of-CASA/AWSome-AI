// Protocole et cycle de vie du composant réel, dans une VM sans navigateur ni micro réels.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync(path.join(__dirname, 'composant_voix', 'index.html'), 'utf8');
const source = html.match(/<script>([\s\S]*?)<\/script>/)[1];
let numeroInstance = 0;

function creer() {
  const messages = [], audios = [], contextes = [], pistes = [], temporisateurs = [], evenements = {};
  const elements = new Map();
  const mode = { rejetAudio: false, erreurMicro: null, acquisitions: 0 };
  const element = id => {
    if (!elements.has(id)) elements.set(id, { style: {}, textContent: '', className: '', disabled: false });
    return elements.get(id);
  };
  class FauxAudio {
    constructor(url) { this.url = url; this.paused = true; this.currentTime = 0; this.lectures = 0; audios.push(this); }
    play() {
      this.paused = false; this.lectures += 1;
      return mode.rejetAudio ? Promise.reject(new Error('lecture indisponible')) : Promise.resolve();
    }
    pause() { this.paused = true; }
    terminer() { this.paused = true; if (this.onended) this.onended(); }
  }
  const noeud = () => ({ connect() {}, disconnect() {}, gain: { value: 0 } });
  class FauxContexte {
    constructor() { this.state = 'suspended'; this.sampleRate = 16000; this.destination = {}; this.fermetures = 0; contextes.push(this); }
    createMediaStreamSource() { return noeud(); }
    createScriptProcessor() { return noeud(); }
    createGain() { return noeud(); }
    async resume() { this.state = 'running'; }
    async suspend() { this.state = 'suspended'; }
    async close() { this.state = 'closed'; this.fermetures += 1; }
  }
  const parent = { postMessage: m => messages.push(m) };
  const fenetre = { parent, crypto: { randomUUID: () => 'montage-' + (++numeroInstance) }, AudioContext: FauxContexte,
    addEventListener: (nom, fn) => { evenements[nom] = fn; } };
  const contexte = vm.createContext({
    window: fenetre,
    document: { getElementById: element, body: { scrollHeight: 180 }, documentElement: { style: { setProperty() {} } } },
    setTimeout: fn => temporisateurs.push(fn),
    btoa: s => Buffer.from(s, 'binary').toString('base64'),
    Audio: FauxAudio,
    navigator: { mediaDevices: { async getUserMedia() {
      mode.acquisitions += 1;
      if (mode.erreurMicro) throw mode.erreurMicro;
      const piste = { enabled: true, readyState: 'live', arrets: 0,
        stop() { this.arrets += 1; this.readyState = 'ended'; this.enabled = false; } };
      pistes.push(piste);
      return { getAudioTracks: () => [piste], getTracks: () => [piste] };
    } } },
  });
  vm.runInContext(source, contexte);
  return {
    messages, audios, contextes, pistes, mode, element,
    lire: expression => vm.runInContext(expression, contexte),
    render(args = {}, sourceMessage = parent) {
      evenements.message({ source: sourceMessage, data: { type: 'streamlit:render', args: {
        session_id: 'session-1', question_id: 'question-1', playback_id: 1, n: 1,
        question_text: 'Dans combien d’années aurez-vous besoin de cet argent ?',
        audio: 'MP3-FAUX', ack: 0, voix: true, veille: false, attente: false, fin: false, termine: false, ...args,
      } } });
    },
    async cliquer() { await element('bouton').onclick(); await drainer(); },
    async terminerAudio() {
      audios.at(-1).terminer();
      while (temporisateurs.length) temporisateurs.shift()();
      await drainer();
    },
    quitter() { evenements.pagehide(); },
  };
}

async function drainer() { await new Promise(resolve => setImmediate(resolve)); }
const messagesDe = (h, kind) => h.messages.filter(m => m.value && m.value.kind === kind).map(m => m.value);
function paroleComplete(h) {
  h.lire(`
    {
      const trame = amplitude => ({ inputBuffer: { getChannelData: () => new Float32Array(2048).fill(amplitude) } });
      for (let i = 0; i < 4; i++) traiterAudio(trame(0.08));
      for (let i = 0; i < 10; i++) traiterAudio(trame(0));
    }
  `);
}

async function main() {
  // Un parent étranger, une identité manquante ou un rendu en attente n'ouvrent jamais le micro.
  let h = creer();
  h.render({}, {});
  assert.equal(h.lire('premierRender'), true, 'Un message provenant d’une autre fenêtre est ignoré.');
  h.render({ question_id: '', audio: '' }); await h.cliquer();
  assert.equal(h.mode.acquisitions, 0); assert.equal(h.audios.length, 0);
  h.render({ attente: true });
  assert.equal(h.lire('etat'), 'reflexion'); assert.equal(h.mode.acquisitions, 0);
  assert.ok(!source.includes('__simulerEnonce') && !source.includes('__demarrerSansMicro'), 'Pas de points d’accès de test en production.');

  // La question est affichée comme texte sûr et doit être effectivement lue avant toute capture.
  h = creer(); h.render({ question_text: '<b>Question visible</b>' });
  assert.equal(h.element('question').textContent, '<b>Question visible</b>');
  await h.cliquer();
  assert.equal(h.lire('etat'), 'parle'); assert.equal(h.mode.acquisitions, 0);
  paroleComplete(h); assert.equal(messagesDe(h, 'audio').length, 0, 'La lecture ne devient jamais une réponse utilisateur.');
  await h.terminerAudio();
  assert.equal(h.lire('etat'), 'ecoute'); assert.equal(h.pistes[0].enabled, true);
  assert.equal(h.contextes[0].state, 'running', 'Le contexte audio est explicitement repris.');
  paroleComplete(h);
  let retours = messagesDe(h, 'audio');
  assert.equal(retours.length, 1); assert.ok(retours[0].wav.length > 100);
  assert.equal(retours[0].question_id, 'question-1'); assert.equal(retours[0].playback_id, 1);
  assert.equal(retours[0].session_id, 'session-1'); assert.ok(retours[0].instance_id.startsWith('montage-'));
  assert.equal(retours[0].n, 1); assert.equal(h.pistes[0].enabled, false);
  assert.ok(h.lire('seuil') < 0.03, 'Le premier mot pendant la calibration reste de la parole.');
  paroleComplete(h); assert.equal(messagesDe(h, 'audio').length, 1, 'Une seule réponse est envoyée avant acquittement.');

  // L'acquittement transporte la réponse, mais ne doit jamais réouvrir automatiquement le micro
  // pour la même question : une transcription vide ne peut donc pas provoquer une boucle de captures.
  h.render({ ack: 1, attendre_reprise_explicite: true }); await drainer();
  assert.equal(h.lire('etat'), 'reflexion');
  assert.equal(h.element('etat').textContent, 'Réponse reçue');
  assert.equal(h.element('bouton').disabled, true);
  h.render({ ack: 1, echec_transcription: 1, attendre_reprise_explicite: true }); await drainer();
  assert.equal(h.lire('etat'), 'erreur_micro');
  assert.equal(h.element('bouton').textContent, 'Réessayer le micro');
  await h.cliquer();
  assert.equal(h.lire('etat'), 'ecoute');
  h.render({ ack: 1, echec_transcription: 1, attendre_reprise_explicite: true }); await drainer();
  assert.equal(h.lire('etat'), 'ecoute', 'Un même échec déjà vu ne réarme ni ne coupe une nouvelle écoute.');

  // Une nouvelle question invalide les anciens callbacks et les buffers de l'ancien sujet.
  const ancienOnEnded = h.audios[0].onended;
  h.render({ question_id: 'question-2', playback_id: 2, n: 2, ack: 1, question_text: 'Combien de mois de réserve avez-vous ?' });
  assert.equal(h.lire('etat'), 'parle'); assert.equal(h.pistes[0].enabled, false);
  ancienOnEnded(); await drainer();
  assert.equal(h.lire('etat'), 'parle', 'Une ancienne fin de lecture ne démarre pas l’écoute du nouveau sujet.');
  await h.terminerAudio(); paroleComplete(h);
  retours = messagesDe(h, 'audio');
  assert.equal(retours.length, 2); assert.equal(retours[1].question_id, 'question-2');
  assert.equal(retours[1].playback_id, 2); assert.equal(retours[1].n, 2);

  // Pause pendant la lecture : même lecteur et même position à la reprise ; pause micro = pistes désactivées.
  h = creer(); h.render(); await h.cliquer();
  h.audios[0].currentTime = 2.5;
  await h.cliquer(); assert.equal(h.lire('etat'), 'pause');
  await h.cliquer();
  assert.equal(h.audios.length, 1); assert.equal(h.audios[0].lectures, 2); assert.equal(h.audios[0].currentTime, 2.5);
  await h.terminerAudio();
  await h.cliquer(); assert.equal(h.pistes[0].enabled, false); assert.equal(h.contextes[0].state, 'suspended');
  await h.cliquer(); assert.equal(h.pistes[0].enabled, true); assert.equal(h.audios.length, 1);
  await h.cliquer();
  h.render({ question_id: 'question-2', playback_id: 2, n: 2 });
  assert.equal(h.audios.length, 1, 'Une nouvelle lecture attend la reprise volontaire.');
  await h.cliquer(); assert.equal(h.audios.length, 2);
  await h.terminerAudio(); assert.equal(h.lire('etat'), 'ecoute');

  // Veille QCM et attente réseau coupent réellement les pistes ; fin et fermeture libèrent le périphérique.
  h.render({ question_id: 'question-2', playback_id: 2, n: 2, veille: true });
  assert.equal(h.pistes[0].enabled, false); assert.equal(h.lire('etat'), 'veille');
  paroleComplete(h); assert.equal(messagesDe(h, 'audio').length, 0);
  h.render({ question_id: 'question-3', playback_id: 3, n: 3, attente: true });
  assert.equal(h.pistes[0].enabled, false); assert.equal(h.audios.length, 2);
  h.render({ question_id: 'question-3', playback_id: 3, n: 3 }); await h.terminerAudio();
  assert.equal(h.lire('etat'), 'ecoute');
  h.render({ termine: true }); await drainer();
  assert.equal(h.pistes[0].arrets, 1); assert.equal(h.contextes[0].state, 'closed');
  assert.equal(h.element('bouton').disabled, true);
  h.quitter(); assert.equal(h.pistes[0].arrets, 1, 'La libération est idempotente.');

  h = creer(); h.render(); await h.cliquer(); await h.terminerAudio(); h.quitter(); await drainer();
  assert.equal(h.pistes[0].arrets, 1); assert.equal(h.contextes[0].state, 'closed');

  // Fin de conversation : un seul message même si plusieurs événements ended arrivent.
  h = creer(); h.render({ fin: true, ack: 7 }); await h.cliquer();
  const fin = h.audios[0].onended;
  fin(); fin(); await drainer();
  const termines = messagesDe(h, 'termine');
  assert.equal(termines.length, 1); assert.equal(termines[0].n, 8);
  assert.equal(termines[0].question_id, 'question-1'); assert.equal(termines[0].playback_id, 1);
  assert.equal(h.mode.acquisitions, 0);

  // Un remontage reprend le compteur ack, change l'instance et conserve le rattachement à la session.
  const instanceAvant = termines[0].instance_id;
  h = creer(); h.render({ ack: 8 }); await h.cliquer(); await h.terminerAudio(); paroleComplete(h);
  const remonte = messagesDe(h, 'audio')[0];
  assert.equal(remonte.n, 9); assert.notEqual(remonte.instance_id, instanceAvant);
  assert.equal(remonte.session_id, 'session-1');

  // Erreur audio : jamais d'écoute silencieuse ; Réessayer demande explicitement une nouvelle synthèse.
  h = creer(); h.render({ audio: '', lecture_error: 'Synthèse indisponible' }); await h.cliquer();
  assert.equal(h.lire('etat'), 'erreur_audio'); assert.equal(h.mode.acquisitions, 0);
  assert.equal(h.element('sous').textContent, 'Synthèse indisponible');
  await h.cliquer();
  const rejouer = messagesDe(h, 'rejouer');
  assert.equal(rejouer.length, 1); assert.equal(rejouer[0].question_id, 'question-1');
  assert.equal(rejouer[0].playback_id, 1); assert.equal(rejouer[0].n, 1);
  h.render({ playback_id: 2, n: 2, ack: 1 }); await h.terminerAudio();
  assert.equal(h.lire('etat'), 'ecoute');

  h = creer(); h.mode.rejetAudio = true; h.render(); await h.cliquer();
  const erreur = h.audios[0].onerror;
  erreur(); await drainer();
  assert.equal(h.lire('etat'), 'erreur_audio'); assert.equal(h.mode.acquisitions, 0);
  await h.cliquer(); assert.equal(messagesDe(h, 'rejouer').length, 1);
  h.mode.rejetAudio = false; h.render({ playback_id: 2, n: 2, ack: 1 });
  erreur(); assert.equal(h.lire('etat'), 'parle', 'Le callback de l’ancien lecteur n’altère pas la nouvelle lecture.');

  // Un refus micro est distinct de l'erreur audio et se retente sans répéter la question.
  h = creer(); h.mode.erreurMicro = { name: 'NotAllowedError' }; h.render(); await h.cliquer(); await h.terminerAudio();
  assert.equal(h.lire('etat'), 'erreur_micro'); assert.match(h.element('sous').textContent, /refusé/);
  h.mode.erreurMicro = null; await h.cliquer();
  assert.equal(h.lire('etat'), 'ecoute'); assert.equal(h.audios.length, 1);

  console.log('Voix OK : identités question/lecture/session/instance, lecture avant micro, transitions, pause/reprise, compteur de remontage, erreurs et libération des pistes.');
}

main().catch(err => { console.error(err); process.exitCode = 1; });

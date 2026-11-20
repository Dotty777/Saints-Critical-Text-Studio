/**
 * Saints Concordance decoder for pack schema saints-concordance-pack/v3 (no dependencies, ES5).
 *
 *   var c = SaintsConcordance.create(hebPack, grcPack, latPack, hubsPack);   // any subset, parsed JSON
 *   c.findLemmas('ἀρχή')            -> [{id, lang, lemma, key, rootId, pos, gloss, formula}]
 *   c.lemmaVerses('G0746')          -> sorted anchor ids (book*10000000 + chapter*10000 + verse*10)
 *   c.rootVerses(rootId)            -> verses of every lemma of the family
 *   c.hubSenseVerses(senseId)       -> verses of a curated colour-hub sense
 *   c.ref(anchorId)                 -> {book, slug, chapter, verse, label}
 * Verse numbers are the Saints.Bible (Greek/Septuagint) numbers used by the site.
 */
(function (global) {
  'use strict';
  var SCHEMA = 'saints-concordance-pack/v3';

  function decodeVarints(b64) {
    if (!b64) return [];
    var bin = atob(b64), out = [], acc = 0, shift = 0, prev = 0, i, b;
    for (i = 0; i < bin.length; i++) {
      b = bin.charCodeAt(i);
      acc += (b & 0x7f) * Math.pow(2, shift);
      if (b & 0x80) {
        shift += 7;
      } else {
        prev = prev + acc;
        out.push(prev);
        acc = 0;
        shift = 0;
      }
    }
    return out;
  }

  function decodeAnchorVerseId(avid) {
    var book = Math.floor(avid / 10000000), rem = avid % 10000000;
    return { book: book, chapter: Math.floor(rem / 10000), verse: Math.floor((rem % 10000) / 10) };
  }

  function bare(s) {
    s = String(s || '').toLowerCase();
    if (s.normalize) s = s.normalize('NFD');
    return s.replace(/[̀-֑ͯ-ׇ]/g, '').replace(/ς/g, 'σ');
  }

  function Concordance() {
    this.books = {}; this.roots = {}; this.lemmas = {}; this.byKey = {}; this.rootMembers = {};
    this.postings = {}; this.hubs = []; this.senses = {}; this.sensePostings = {};
  }

  Concordance.prototype.addPack = function (pack) {
    var self = this, k;
    if (!pack || pack.schema !== SCHEMA) throw new Error('Saints Concordance: unsupported pack ' + (pack && pack.schema));
    (pack.books || []).forEach(function (b) { self.books[b[0]] = { order: b[0], slug: b[1], usfm: b[2], title: b[3] }; });
    (pack.roots || []).forEach(function (r) {
      self.roots[r[0]] = { id: r[0], lang: r[1], label: r[2], homograph: r[3], gloss: r[4], source: r[5], translit: r[6] || '' };
    });
    (pack.lemmas || []).forEach(function (l) {
      var o = { id: l[0], lang: l[1], lemma: l[2], key: l[3], rootId: l[4], pos: l[5], gloss: l[6], formula: l[7],
                content: l[8] !== 0, verseCount: l[9] || 0, translit: l[10] || '' };
      self.lemmas[o.id] = o;
      if (o.key) self.byKey[o.key] = o;
      (self.rootMembers[o.rootId] = self.rootMembers[o.rootId] || []).push(o.id);
    });
    for (k in (pack.lemma_postings || {})) if (pack.lemma_postings.hasOwnProperty(k)) self.postings[k] = pack.lemma_postings[k];
    (pack.hubs || []).forEach(function (h) {
      var hub = { id: h[0], slug: h[1], word: h[2], colour: h[3], note: h[4], senses: [], members: h[6] || [], theme: h[7] || '' };
      (h[5] || []).forEach(function (s) {
        var sense = { id: s[0], offset: s[1], word: s[2], role: s[3], nuance: s[4], hub: hub,
                      colour: s[5] || hub.colour, theme: s[6] || hub.theme, chosen: s[3] !== 'unreviewed' };
        hub.senses.push(sense);
        self.senses[sense.id] = sense;
      });
      self.hubs.push(hub);
    });
    for (k in (pack.sense_postings || {})) if (pack.sense_postings.hasOwnProperty(k)) self.sensePostings[k] = pack.sense_postings[k];
    return this;
  };

  Concordance.prototype.lemma = function (idOrKey) {
    return this.lemmas[idOrKey] || this.byKey[idOrKey] || null;
  };

  Concordance.prototype.lemmaVerses = function (idOrKey) {
    var l = this.lemma(idOrKey);
    return l ? decodeVarints(this.postings[String(l.id)]) : [];
  };

  Concordance.prototype.rootVerses = function (rootId) {
    var seen = {}, out = [], self = this;
    (this.rootMembers[rootId] || []).forEach(function (lid) {
      decodeVarints(self.postings[String(lid)]).forEach(function (v) { if (!seen[v]) { seen[v] = 1; out.push(v); } });
    });
    return out.sort(function (a, b) { return a - b; });
  };

  Concordance.prototype.hubSenseVerses = function (senseId) {
    return decodeVarints(this.sensePostings[String(senseId)]);
  };

  Concordance.prototype.findLemmas = function (query, limit) {
    var q = bare(query), out = [], id, l;
    if (!q) return out;
    for (id in this.lemmas) {
      if (!this.lemmas.hasOwnProperty(id)) continue;
      l = this.lemmas[id];
      if (bare(l.lemma).indexOf(q) === 0 || (l.translit && bare(l.translit).indexOf(q) === 0) ||
          String(l.key).toLowerCase() === q || bare(l.gloss).indexOf(q) !== -1) out.push(l);
      if (out.length >= (limit || 50)) break;
    }
    return out;
  };

  Concordance.prototype.ref = function (avid) {
    var d = decodeAnchorVerseId(avid), b = this.books[d.book] || {};
    return { book: b.title || String(d.book), slug: b.slug || '', chapter: d.chapter, verse: d.verse,
             label: (b.title || d.book) + ' ' + d.chapter + ':' + d.verse };
  };

  global.SaintsConcordance = {
    schema: SCHEMA,
    create: function () {
      var c = new Concordance(), i;
      for (i = 0; i < arguments.length; i++) if (arguments[i]) c.addPack(arguments[i]);
      return c;
    },
    decodeVarints: decodeVarints,
    decodeAnchorVerseId: decodeAnchorVerseId
  };
})(typeof window !== 'undefined' ? window : this);

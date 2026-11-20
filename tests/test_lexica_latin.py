"""Tests for studio.lexica.latin (Lewis & Short driven Latin lemma + root tagger).

Offline: they read the Lewis & Short XML inside the Studio (through the cache in data/) and, when it is
present, the Studio database read-only.  Tests that need either skip cleanly when it is missing.
Every expected lemma below was checked by hand against the verse and Lewis & Short; several are
regressions found while building the tagger (18 Nov 2026).
"""

import re
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from studio.lexica import LemmaEntry, TokenTag, tokenize_verse  # noqa: E402
from studio.lexica import latin as L  # noqa: E402

HAVE_LS = L.ls_path().exists()

# The corpus priors are computed from the Studio's own Latin text.  When another test module has pointed
# the Studio at a sandbox (CTS_DATA_DIR, e.g. test_concordance), use the real database read-only here, and
# forget any priors already built from the sandbox's few verses.
_LIVE_DB = ROOT / "data" / "studio.db"
_ORIG_DB_PATH = L.db_path
HAVE_DB = _LIVE_DB.exists()


def setUpModule() -> None:
    if HAVE_DB and L.db_path() != _LIVE_DB:
        L.db_path = lambda: _LIVE_DB  # type: ignore[assignment]
        L.reset_cache()


def tearDownModule() -> None:
    if L.db_path is not _ORIG_DB_PATH:
        L.db_path = _ORIG_DB_PATH  # type: ignore[assignment]
        L.reset_cache()


def tag(text: str, book: str = "genesis", chapter: int = 1, verse: int = 1):
    return L.tag_chapter(book, chapter, {verse: text})[verse]


def lemma_of(text: str, word: str, nth: int = 0):
    hits = [t for t in tag(text) if t.surface == word]
    return hits[nth].lemma_key


@unittest.skipUnless(HAVE_LS, "Lewis & Short XML not present")
class ParadigmReconstructionTests(unittest.TestCase):
    """L&S abbreviates genitives and principal parts; these rebuild them."""

    def test_genitives(self):
        cases = {("caput", "itis"): "capitis", ("princeps", "cipis"): "principis", ("rex", "regis"): "regis",
                 ("sermo", "onis"): "sermonis", ("pauper", "peris"): "pauperis", ("mons", "tis"): "montis",
                 ("frater", "tris"): "fratris", ("virgo", "ginis"): "virginis", ("multitudo", "dinis"): "multitudinis",
                 ("iter", "itineris"): "itineris", ("sanguis", "inis"): "sanguinis"}
        for (hb, tail), want in cases.items():
            self.assertEqual(L._attach_gen(L._b(hb), tail), L._b(want), (hb, tail))

    def test_principal_parts(self):
        def part(hb, w, t, prefix="", cut=None):
            return L._attach_part(L._b(hb), L._b(w), L._b(t), prefix, cut)[0]
        cases = [(("accipio", "accipi", "cepi", "ac"), "accepi"), (("dico", "dic", "xi"), "dixi"),
                 (("respondeo", "respond", "di"), "respondi"), (("aperio", "aperi", "erui"), "aperui"),
                 (("propono", "propon", "posui", "pro"), "proposui"),       # not 'posui'
                 (("consisto", "consist", "stiti", "con"), "constiti"), (("capio", "capi", "cepi"), "cepi"),
                 (("audio", "audi", "ivi"), "audivi"), (("statuo", "statu", "ui"), "statui")]
        for args, want in cases:
            self.assertEqual(part(*args), L._b(want), args)

    def test_head_text_parsing(self):
        hm = L._head_morph("pōno, pŏsŭi , pŏsĭtum, 3 , v. a. for posno, posino")
        self.assertEqual(hm["parts"], ["pŏsŭi", "pŏsĭtum", "3"])
        self.assertTrue(hm["pos"].startswith("v. a."))
        hm = L._head_morph("terra , ae , f. perh. Sanscr. root tarsh-")
        self.assertEqual((hm["parts"], hm["gender"]), (["ae"], "f"))
        hm = L._head_morph("regno, āvi, ātum, 1, v. n. and a.")          # 'v. n.' is not part + gender
        self.assertEqual(hm["parts"], ["āvi", "ātum", "1"])


@unittest.skipUnless(HAVE_LS, "Lewis & Short XML not present")
class ContractTests(unittest.TestCase):
    def test_one_tag_per_token(self):
        text = "Dixitque Deus: Fiat lux. Et facta est lux."
        tags = tag(text)
        toks = tokenize_verse(text, "lat")
        self.assertEqual([t.surface for t in tags], toks)
        self.assertEqual([t.index for t in tags], list(range(1, len(toks) + 1)))
        self.assertTrue(all(isinstance(t, TokenTag) for t in tags))

    def test_every_emitted_key_is_in_the_lexicon(self):
        lex = L.load_lexicon()
        self.assertTrue(all(isinstance(e, LemmaEntry) for e in list(lex.values())[:50]))
        texts = ["In principio creavit Deus cælum et terram.",
                 "In principio erat Verbum, et Verbum erat apud Deum, et Deus erat Verbum.",
                 "Et cognovit Bacchides, et congregavit universam multitudinem suam: et his, qui de Judæa erant, denuntiavit.",
                 "Dominus regit me, et nihil mihi deerit: in loco pascuæ ibi me collocavit."]
        for text in texts:
            for t in tag(text):
                if t.lemma_key is not None:
                    self.assertIn(t.lemma_key, lex, t)
                    self.assertEqual(lex[t.lemma_key].lang, "lat")

    def test_untagged_is_never_a_guess(self):
        for t in tag("Cum autem venisset, et cum eo discipuli ejus."):
            if t.lemma_key is None:
                self.assertEqual((t.method, t.confidence), ("untagged", 0.0))
            else:
                self.assertGreater(t.confidence, 0.0)

    def test_sources_and_licences_recorded(self):
        lex = L.load_lexicon()
        self.assertIn("CC BY-SA", lex["lat:principium"].source)
        for e in lex.values():
            self.assertTrue(e.source, e.lemma_key)
            self.assertIn(e.root_source, ("LewisShort-etym", "self"))

    def test_no_quarantined_data_in_module(self):
        src = Path(L.__file__).read_text(encoding="utf-8")
        for bad in ("05_Tier5", "local-nc-only", ".conllu", "NT_UD_Latin_PROIEL", "Rahlfs", "BHSA"):
            self.assertNotIn(bad, src)


@unittest.skipUnless(HAVE_LS, "Lewis & Short XML not present")
class LemmaTests(unittest.TestCase):
    def test_common_forms(self):
        self.assertEqual(lemma_of("In principio creavit Deus cælum et terram.", "principio"), "lat:principium")
        self.assertEqual(lemma_of("In principio creavit Deus cælum et terram.", "creavit"), "lat:creo")
        self.assertEqual(lemma_of("In principio creavit Deus cælum et terram.", "terram"), "lat:terra")
        self.assertEqual(lemma_of("Et facta est lux.", "est"), "lat:sum#1")
        self.assertEqual(lemma_of("Tulerunt autem tunicam ejus", "Tulerunt"), "lat:fero")
        self.assertEqual(lemma_of("Ille autem cum sustulisset oculos", "sustulisset"), "lat:tollo")
        self.assertEqual(lemma_of("locutus est Dominus ad Moysen", "locutus"), "lat:loquor")
        self.assertEqual(lemma_of("et ingressus est in templum", "ingressus"), "lat:ingredior")
        self.assertEqual(lemma_of("et peperit filium", "peperit"), "lat:pario#2")
        self.assertEqual(lemma_of("Et surrexit Judas", "surrexit"), "lat:surgo")
        self.assertEqual(lemma_of("principes sacerdotum", "principes"), "lat:princeps")
        self.assertEqual(lemma_of("super capitis ejus", "capitis"), "lat:caput")

    def test_regressions_from_development(self):
        self.assertEqual(lemma_of("audivit vocem Domini", "vocem"), "lat:vox")                 # not voco (subj.)
        self.assertEqual(lemma_of("Quid vultis mihi dare", "vultis"), "lat:volo#1")             # not vultus
        self.assertEqual(lemma_of("Laudate Dominum de cælis", "Laudate"), "lat:laudo")         # not adv. laudate
        self.assertEqual(lemma_of("in omnia loca", "loca"), "lat:locus")                        # L&S 'plur. loca'
        self.assertEqual(lemma_of("dii alieni", "dii"), "lat:deus")
        self.assertEqual(lemma_of("beati pauperes spiritu", "pauperes"), "lat:pauper")          # 'pĕris' abbreviation
        self.assertEqual(lemma_of("non erit ibi", "ibi"), "lat:ibi")
        self.assertEqual(lemma_of("Vere hic homo Filius Dei erat", "Vere"), "lat:vere")
        self.assertEqual(lemma_of("venti et mare obediunt ei", "venti"), "lat:ventus")         # venio has no PPP
        self.assertEqual(lemma_of("populi terræ", "populi"), "lat:populus#1")                   # not the poplar
        self.assertEqual(lemma_of("quod fuit ab initio, quod audivimus", "fuit"), "lat:sum#1")
        self.assertEqual(lemma_of("Vado ad Patrem", "Vado"), "lat:vado#1")
        self.assertEqual(lemma_of("servi tui sumus", "tui"), "lat:tuus")

    def test_enclitics(self):
        tags = {t.surface: t for t in tag("Dixitque Deus, atque itaque neque usque quoque bene sine mecum")}
        self.assertEqual((tags["Dixitque"].lemma_key, tags["Dixitque"].prefixes), ("lat:dico#2", ("E:que",)))
        for w, lem in (("atque", "lat:atque"), ("itaque", "lat:itaque"), ("neque", "lat:neque"),
                       ("usque", "lat:usque"), ("quoque", "lat:quoque#1"), ("bene", "lat:bene"), ("sine", "lat:sine")):
            self.assertEqual((tags[w].lemma_key, tags[w].prefixes), (lem, ()), w)
        self.assertEqual((tags["mecum"].lemma_key, tags["mecum"].prefixes), ("lat:ego", ("E:cum",)))

    def test_ambiguity_left_untagged_and_context_rules(self):
        self.assertIsNone(lemma_of("cum venisset", "cum"))
        self.assertEqual(lemma_of("Cum autem venisset", "Cum"), "lat:cum#2")
        self.assertIsNone(lemma_of("Hoc est quod dixi", "quod"))
        self.assertEqual(lemma_of("eo quod non crediderunt", "quod"), "lat:quod#1")
        self.assertEqual(lemma_of("melior est obedientia quam victimæ", "quam"), "lat:quam")
        # tribe / three: decided by the context since 19 Nov 2026, left untagged when the context says nothing
        self.assertEqual(lemma_of("dimidia tribus Manasse", "tribus"), "lat:tribus")
        self.assertEqual(lemma_of("ergo eos custodiæ tribus diebus", "tribus"), "lat:tres")
        self.assertIsNone(lemma_of("Et post tribus", "tribus"))
        self.assertIsNone(lemma_of("recte judicasti", "recte"))      # adverb not an L&S headword: no vocative guess

    def test_content_flags(self):
        tags = {t.surface: t for t in tag("et in terra est qui ejus Dominus")}
        for w in ("et", "in", "est", "qui", "ejus"):
            self.assertFalse(tags[w].is_content, w)
        for w in ("terra", "Dominus"):
            self.assertTrue(tags[w].is_content, w)


@unittest.skipUnless(HAVE_LS, "Lewis & Short XML not present")
class RootTests(unittest.TestCase):
    def test_root_chain_principium(self):
        e = L.load_lexicon()["lat:principium"]
        self.assertEqual((e.root_key, e.root_source), ("lat:capio#1", "LewisShort-etym"))
        self.assertIn("princeps", e.formula)
        self.assertIn("primus + capio", e.formula)

    def test_caput_is_not_capio(self):
        e = L.load_lexicon()["lat:caput"]
        self.assertEqual((e.root_key, e.root_source), ("lat:caput", "self"))

    def test_explicit_families(self):
        lex = L.load_lexicon()
        for key, root in (("lat:accipio", "lat:capio#1"), ("lat:abeo", "lat:eo#1"), ("lat:affero", "lat:fero"),
                          ("lat:laudatio", "lat:laus"), ("lat:rex", "lat:rego"), ("lat:regnum", "lat:rego"),
                          ("lat:resurrectio", "lat:surgo"), ("lat:sanctus", "lat:sancio"),
                          ("lat:peccatum", "lat:pecco")):
            self.assertEqual(lex[key].root_key, root, key)
        # cognates only ('Sanscr.', 'cf.', 'v. domo') give no family
        self.assertEqual(lex["lat:dominus"].root_source, "self")
        self.assertEqual(lex["lat:terra"].root_source, "self")


@unittest.skipUnless(HAVE_LS and HAVE_DB, "Lewis & Short XML or Studio database not present")
class CorpusTests(unittest.TestCase):
    """Need the corpus statistics from data/studio.db (opened read-only)."""

    def test_names(self):
        self.assertEqual(lemma_of("ait Dominus ad Moysen", "Moysen"), "lat:Moses")
        self.assertEqual(lemma_of("Et cognovit Bacchides, et congregavit", "Bacchides"), "lat:Bacchides")
        self.assertEqual(lemma_of("dixit Jesus Petro", "Petro"), "lat:Petrus")
        self.assertEqual(lemma_of("et ait Maria", "Maria"), "lat:Maria#1")             # Mary, not the seas
        self.assertEqual(lemma_of("in nomine Patris, et Filii", "Patris"), "lat:pater")  # not the town Patrae
        self.assertEqual(lemma_of("Abraham genuit Isaac", "Abraham"), "lat:Abraham")
        self.assertEqual(lemma_of("ut loquerentur Judæis", "Judæis"), "lat:Judaeus")
        self.assertEqual(lemma_of("venit Ezechias", "Ezechias"), "lat:Ezechias")

    def test_tag_all_first_chapters(self):
        lex = L.load_lexicon()
        seen = 0
        for book, chapter, verses in L.tag_all():
            self.assertTrue(book and chapter >= 1 and verses)
            for v, tags in verses.items():
                for t in tags:
                    if t.lemma_key:
                        self.assertIn(t.lemma_key, lex)
            seen += 1
            if seen == 3:
                break
        self.assertEqual(seen, 3)


def tags_of(text: str, book: str = "genesis", chapter: int = 1, verse: int = 1):
    return {t.surface: t for t in L.tag_chapter(book, chapter, {verse: text})[verse]}


@unittest.skipUnless(HAVE_LS and HAVE_DB, "Lewis & Short XML or Studio database not present")
class VerifierRegressionTests(unittest.TestCase):
    """Regressions for the independent verification of 18 Nov 2026 (its concrete examples)."""

    def test_names_are_not_split_into_word_plus_enclitic(self):
        # Josue was Ios (an island) + -ve, Ninive Ninus + -ve, Abisue abeo + -ve, Parumne the island Paros
        t = tags_of("Dixitque Moyses ad Josue: Elige viros", "exodus", 17, 9)
        self.assertEqual((t["Josue"].lemma_key, t["Josue"].prefixes), ("lat:Josue", ()))
        t = tags_of("et reversus est Sennacherib et mansit in Ninive", "2-kings", 19, 36)
        self.assertEqual((t["Ninive"].lemma_key, t["Ninive"].prefixes), ("lat:Ninive", ()))
        t = tags_of("Phinees autem genuit Abisue", "1-chronicles", 6, 4)
        self.assertNotIn(t["Abisue"].lemma_key, ("lat:abeo", "lat:Aba"))
        self.assertEqual(t["Abisue"].prefixes, ())
        t = tags_of("Parumne est vobis", "numbers", 16, 9)
        self.assertEqual((t["Parumne"].lemma_key, t["Parumne"].prefixes), ("lat:parum", ("E:ne",)))

    def test_facies_decided_by_context_or_left_untagged(self):
        self.assertEqual(lemma_of("Facies et candelabrum ductile de auro mundissimo", "Facies"), "lat:facio")
        self.assertEqual(lemma_of("Non homicidium facies, non adulterabis", "facies"), "lat:facio")   # Mt 19:18
        self.assertEqual(lemma_of("Non facies calumniam proximo tuo", "facies"), "lat:facio")         # Lv 19:13
        self.assertEqual(lemma_of("Et facies quodcumque dixerint", "facies"), "lat:facio")            # Dt 17:10
        self.assertEqual(lemma_of("Cur tristior est hodie solito facies vestra?", "facies"), "lat:facies")
        self.assertEqual(lemma_of("et facies eorum quasi facies leonis", "facies"), "lat:facies")
        self.assertIsNone(lemma_of("et sicut videris facies cum servis tuis", "facies"))   # undecided: no guess

    def test_aries_paradigm(self):
        self.assertEqual(L._attach_gen("aries", "ĭĕtis"), "arietis")       # not 'ariietis'
        self.assertEqual(L._attach_gen("paries", "ĭĕtis"), "parietis")
        t = tags_of("obtulit arietem pro filio suo et arietes septem")
        self.assertEqual(t["arietem"].lemma_key, "lat:aries")              # not arieto 'to butt'
        self.assertEqual(t["arietes"].lemma_key, "lat:aries")

    def test_adversum_is_the_preposition(self):
        t = tags_of("consurrexit adversum me, et adversus eum")
        self.assertEqual(t["adversum"].lemma_key, "lat:adversus#3")
        self.assertEqual(t["adversus"].lemma_key, "lat:adversus#3")
        self.assertFalse(t["adversum"].is_content)

    def test_pronoun_plus_cum_before_paradigms(self):
        t = tags_of("duxit secum duos, et habitate nobiscum, vobiscum, mecum, tecum")
        for w, lem in (("secum", "lat:sui"), ("nobiscum", "lat:nos"), ("vobiscum", "lat:vos"),
                       ("mecum", "lat:ego"), ("tecum", "lat:tu")):
            self.assertEqual((t[w].lemma_key, t[w].prefixes), (lem, ("E:cum",)), w)

    def test_cumque_is_conjunction_cum_plus_que(self):
        t = tags_of("Cumque obdormisset, tulit unam de costis ejus")
        self.assertEqual((t["Cumque"].lemma_key, t["Cumque"].prefixes), ("lat:cum#2", ("E:que",)))
        self.assertIsNone(lemma_of("cum venisset", "cum"))                  # still left to the context rules

    def test_elijah_and_hebrew_names(self):
        self.assertEqual(lemma_of("Et dixit Elias Thesbites", "Elias"), "lat:Elias#2")      # not 'Elean'
        self.assertEqual(lemma_of("dicebant: Eliam vocat iste", "Eliam"), "lat:Elias#2")
        self.assertEqual(lemma_of("et misit Thou Joram filium suum", "Joram"), "lat:Joram")  # not 'Jora'
        self.assertEqual(lemma_of("sermo Domini ad Jehu filium Hanani", "Jehu"), "lat:Jehu")
        self.assertEqual(lemma_of("Isaiam prophetam filium Amos", "Amos"), "lat:Amos")       # not amor
        self.assertNotEqual(lemma_of("Et de Bete et de Beroth civitatibus", "Bete"), "lat:beto")

    def test_paratus_is_the_participle_of_paro(self):
        self.assertEqual(lemma_of("Paratus sum", "Paratus"), "lat:paro#1")
        self.assertEqual(lemma_of("Paratum cor meum, Deus", "Paratum"), "lat:paro#1")

    def test_variant_fallback_needs_more_evidence(self):
        t = tags_of("ligna setim, et quartam partem hin, et vestibulum palatii")
        for w in ("setim", "hin", "palatii"):                   # Hebrew loanwords / no safe respelling: untagged
            self.assertIsNone(t[w].lemma_key, w)
        self.assertEqual(lemma_of("jam per decem vices nec obedierunt", "vices"), "lat:vicis")    # not vicus
        self.assertEqual(lemma_of("dereliquit consilium senum", "senum"), "lat:senex")             # not sinus
        self.assertEqual(lemma_of("videns despexit dominam suam", "despexit"), "lat:despicio")     # not dispicio
        self.assertEqual(lemma_of("Non maledices surdo", "maledices"), "lat:maledico")            # not maledicus
        # capitalised names are never respelt into Latin words or classical names
        bad = {"Lachis": "lat:lacio", "Achis": "lat:Acis#1", "Tharsis": "lat:Tarsus", "Caree": "lat:careum",
               "Manue": "lat:manus#1", "Vasthi": "lat:vastus"}
        t = tags_of("regem Lachis et Achis regem Geth et Tharsis et Johanan filius Caree nomine Manue reginam Vasthi")
        for w, wrong in bad.items():
            self.assertNotEqual(t[w].lemma_key, wrong, w)

    def test_acrostic_letter_names_untagged(self):
        t = tags_of("Beth Plorans ploravit in nocte", "lamentations", 1, 2)
        self.assertIsNone(t["Beth"].lemma_key)
        self.assertEqual(t["Plorans"].lemma_key, "lat:ploro")
        t = tags_of("Res Vide humilitatem meam", "psalms", 118, 153)
        self.assertIsNone(t["Res"].lemma_key)                               # not res 'thing'
        self.assertEqual(t["Vide"].lemma_key, "lat:video")
        for text in ("He Legem pone mihi, Domine", "Sin Principes persecuti sunt me gratis"):
            first = L.tag_chapter("psalms", 118, {33: text})[33][0]
            self.assertIsNone(first.lemma_key, text)
        # outside the acrostics the same spellings are names: Joshua son of Nun
        self.assertEqual(lemma_of("Josue filius Nun", "Nun"), "lat:Nun")

    def test_mundus_world_or_clean_by_context(self):
        self.assertEqual(lemma_of("Cor mundum crea in me, Deus", "mundum"), "lat:mundus#1")
        self.assertEqual(lemma_of("Vos estis lux mundi", "mundi"), "lat:mundus#2")
        self.assertEqual(lemma_of("et vos mundi estis, sed non omnes", "mundi"), "lat:mundus#1")
        self.assertEqual(lemma_of("Sic enim Deus dilexit mundum", "mundum"), "lat:mundus#2")
        self.assertIsNone(lemma_of("qui de cælo descendit et dat vitam mundo", "mundo"))

    def test_lemma_splits_merged(self):
        self.assertEqual(lemma_of("Inclinavit cælos et descendit", "cælos"), "lat:caelum#2")      # not caelus
        self.assertEqual(lemma_of("sicut solent canes lambere", "canes"), "lat:canis")             # not canes
        self.assertEqual(lemma_of("non mutiet canis ab homine", "canis"), "lat:canis")

    def test_small_ambiguities(self):
        self.assertEqual(lemma_of("Nescio vos", "Nescio"), "lat:nescio")                         # not nescius
        self.assertEqual(lemma_of("Sede a dextris meis", "Sede"), "lat:sedeo")                     # imperative
        self.assertEqual(lemma_of("in sede majestatis suæ", "sede"), "lat:sedes")
        self.assertEqual(lemma_of("Sine modo: sic enim decet nos", "Sine"), "lat:sino")
        self.assertEqual(lemma_of("Nihil in terra sine causa fit", "sine"), "lat:sine")
        self.assertEqual(lemma_of("Præsto sum", "Præsto"), "lat:praesto#1")                       # the adverb
        self.assertEqual(lemma_of("Vivo ego, dicit Dominus", "Vivo"), "lat:vivo")
        self.assertEqual(lemma_of("servire Deo vivo et vero", "vivo"), "lat:vivus")
        self.assertEqual(lemma_of("comprehenderent Baruch scribam et Jeremiam", "scribam"), "lat:scriba")
        self.assertEqual(lemma_of("et scribam super eas verba", "scribam"), "lat:scribo")
        self.assertEqual(lemma_of("Quem quæritis? Jesum Nazarenum", "Quem"), "lat:quis#1")       # interrogative
        self.assertEqual(lemma_of("Quid facis?", "facis"), "lat:facio")                           # not fax
        t = tags_of("Quid hic agis, Elia?")
        self.assertEqual(t["hic"].lemma_key, "lat:hic")       # adverb hīc: L&S lists it under hic
        self.assertTrue(any("adverb" in n for n in t["hic"].notes))

    def test_roots_follow_lewis_and_short(self):
        lex = L.load_lexicon()
        for key, root in (("lat:comedo#1", "lat:edo#1"),        # eat, not edo#2 'give out' -> do 'give'
                          ("lat:colligo#1", "lat:lego#2"),      # '[2. lego, ĕre]', not ligo 'bind'
                          ("lat:dedico", "lat:dico#1"), ("lat:indico#1", "lat:dico#1"),
                          ("lat:praedico#1", "lat:dico#1"),
                          ("lat:quisque", "lat:quis#1"), ("lat:ubique", "lat:ubi"),
                          ("lat:cognosco", "lat:nosco")):       # via 'gnosco, ĕre, v. nosco'
            self.assertEqual(lex[key].root_key, root, key)
        for key, wrong in (("lat:inopia", "lat:Opis#1"), ("lat:inops", "lat:Opis#1"), ("lat:quamvis", "lat:vis"),
                           ("lat:invictus", "lat:in"), ("lat:uterque", "lat:que")):
            self.assertNotEqual(lex[key].root_key, wrong, key)
        self.assertEqual([k for k, e in lex.items() if e.root_key not in lex], [])   # no dangling root (sesceni)

    def test_glosses_are_english_senses_not_grammar_labels(self):
        lex = L.load_lexicon()
        self.assertEqual(lex["lat:facio"].gloss, "to make, do")
        self.assertEqual(lex["lat:do#1"].gloss, "to give")
        self.assertIn("citizenship", lex["lat:civitas"].gloss)
        self.assertIn("city", lex["lat:civitas"].gloss)
        self.assertIn("to put", lex["lat:pono"].gloss)
        self.assertIn("to answer", lex["lat:respondeo"].gloss)
        self.assertIn("face", lex["lat:facies"].gloss)
        for key in ("lat:morior", "lat:vivo", "lat:coepio", "lat:bos", "lat:dormio", "lat:sedes", "lat:lac",
                    "lat:sino", "lat:sanctus", "lat:mandatum", "lat:Jacob"):
            g = lex[key].gloss
            self.assertTrue(g, key)
            self.assertNotRegex(g, r"(?i)^(?:imper|futur|pluperf|n\. cr|unt)\b", key)
        self.assertNotIn("Exile and Return", lex["lat:Jacob"].gloss)     # not the first TIPNR bearer listed
        for raw in ("imper.", "N. cr.;", "unt", "futur.", "pluperf. subj.", "Absol.", "Dae."):
            self.assertTrue(L._is_label(raw), raw)
        for raw in ("to make", "face", "a ram", "ox"):
            self.assertFalse(L._is_label(raw), raw)


_BAD_GLOSS = re.compile(r"(?i)aliqu|alicu|\badvv\b|\binfin\b|object-clause|gerundive|\bsupin\b|\bplqpf\b|"
                        r"without a prep|[Ͱ-Ͽἀ-῿]|outextend|\ben trance\b|young est|\s-\s")
_DANGLING_END = re.compile(r"\b(?:of|the|to|and|or|a|an|with|its|for|by)\s*$")


@unittest.skipUnless(HAVE_LS, "Lewis & Short XML not present")
class ReaderGlossTests(unittest.TestCase):
    """The final check of 19 Nov 2026: glosses readers see (its concrete examples)."""

    def test_frequent_lemmas_lead_with_the_biblical_sense(self):
        lex = L.load_lexicon()
        lead = {"lat:respondeo": "to answer", "lat:princeps": "prince", "lat:gens": "nation", "lat:pecco": "to sin",
                "lat:aries": "ram", "lat:praecipio": "to command", "lat:facies": "face", "lat:exercitus#2": "army",
                "lat:saeculum": "age", "lat:jumentum": "beast of burden", "lat:masculus": "male", "lat:ros": "dew",
                "lat:caritas": "love", "lat:mundus#2": "world", "lat:apostolus": "apostle",
                "lat:testamentum": "covenant", "lat:puto": "to think", "lat:sumo": "to take", "lat:lego#2": "to read",
                "lat:edo#1": "to eat", "lat:addo": "to add", "lat:peccatum": "sin", "lat:verbum": "word",
                "lat:cor": "heart", "lat:frater": "brother", "lat:venio": "to come", "lat:scio": "to know",
                "lat:loquor": "to speak", "lat:rogo": "to ask", "lat:impleo": "to fill"}
        for key, want in lead.items():
            self.assertTrue(lex[key].gloss.startswith(want), (key, lex[key].gloss))
        self.assertIn("for ever", lex["lat:saeculum"].gloss)
        self.assertNotIn("zodiac", lex["lat:aries"].gloss)
        self.assertNotIn("promise", lex["lat:respondeo"].gloss)

    def test_no_labels_latin_fragments_or_dangling_words(self):
        lex = L.load_lexicon()
        for key in ("lat:rogo", "lat:impleo", "lat:affero", "lat:sedeo", "lat:accedo", "lat:jubeo", "lat:curo",
                    "lat:haurio", "lat:ignosco", "lat:pius", "lat:extendo", "lat:David", "lat:initium",
                    "lat:Benjamin", "lat:holocaustum", "lat:illudo", "lat:Judas", "lat:Ammon"):
            g = lex[key].gloss
            self.assertTrue(g, key)
            self.assertNotRegex(g, _BAD_GLOSS, key)
            self.assertNotRegex(g, _DANGLING_END, key)
        self.assertNotIn("Jupiler", lex["lat:Ammon"].gloss)

    def test_reviewed_table_covers_the_frequent_lemmas(self):
        lex = L.load_lexicon()
        self.assertGreaterEqual(len(L._SAINTS_GLOSS), 1500)
        missing = [k for k in L._SAINTS_GLOSS if k not in lex]
        self.assertEqual(missing, [])
        for k, g in L._SAINTS_GLOSS.items():
            self.assertNotRegex(g, _BAD_GLOSS, k)

    def test_gloss_cleaner(self):
        latin = {"aliquis"}
        self.assertEqual(L._compose_gloss([[1, "aliquem aliquid", 1], [1, "to ask", 2]], latin), "to ask")
        g = L._compose_gloss([[1, "often referred to τίω, τιμάω, that acts according to duty", 1]], latin)
        self.assertNotRegex(g, r"[Ͱ-Ͽἀ-῿]")
        # a Vulgate-cited sense leads over the classical first sense (apostolus)
        g = L._compose_gloss([[1, "a notice sent to a higher tribunal", 1, False], [2, "an Apostle", 2, True]], latin)
        self.assertTrue(g.lower().startswith("an apostle"), g)
        self.assertEqual(L._drop_dangling("the second king of the Jews, and principal author of the"),
                         "the second king of the Jews, and principal author")
        g = L._compose_gloss([[1, "a whole burnt - offering, holocaust", 1]], latin)
        self.assertIn("burnt-offering", g)

    def test_parts_of_speech(self):
        lex = L.load_lexicon()
        self.assertEqual(lex["lat:amen"].pos, "INTERJ")
        self.assertEqual(lex["lat:princeps"].pos, "N")
        self.assertEqual(lex["lat:plus"].pos, "ADJ")
        self.assertEqual(lex["lat:prior"].pos, "ADJ")
        self.assertEqual(lex["lat:primus"].pos, "ADJ")

    def test_lewis_short_cyrillic_y_headwords(self):
        # 'sўnăgōga' (Cyrillic ў) lost its y before 19 Nov 2026: synagoga had no paradigm at all
        self.assertEqual(L._plain("sўnăgōga"), "synagoga")
        self.assertEqual(lemma_of("venit in synagogam eorum", "synagogam"), "lat:synagoga")

    def test_sum_supine_gives_the_participle(self):
        # 'con-verto, ti, sum' and 're-spondeo, di, sum': the abbreviated supine was dropped as the verb 'sum'
        stems, _x = L._verb_stems("converto", ["ti", "sum", "3"], "con")
        self.assertIn(("convers", "VPP"), stems)
        stems, _x = L._verb_stems("respondeo", ["di", "sum", "2"], "re")
        self.assertIn(("respons", "VPP"), stems)
        self.assertNotIn(("res", "VPP"), stems)                      # not prefix + 'sum' (Resa = respondeo)

    def test_roots_from_explicit_lewis_short_statements(self):
        lex = L.load_lexicon()
        for key, root in (("lat:filia", "lat:filius"), ("lat:fides#1", "lat:fido"), ("lat:familia", "lat:famulus#1"),
                          ("lat:reliquus", "lat:linquo"), ("lat:reliquiae", "lat:linquo"), ("lat:vita", "lat:vivo"),
                          ("lat:sepulcrum", "lat:sepelio"), ("lat:deficio", "lat:facio"),
                          ("lat:sanctifico", "lat:facio"), ("lat:descendo", "lat:scando"),
                          ("lat:malitia", "lat:malus#1"), ("lat:caelestis", "lat:caelum#2")):
            self.assertEqual(lex[key].root_key, root, key)
        for key in ("lat:adolesco", "lat:adoleo#1", "lat:aboleo"):
            self.assertNotEqual(lex[key].root_key, "lat:oleo#1", key)
        self.assertNotEqual(lex["lat:suscipio"].root_key, "lat:sus")          # 'v. a. sus, i. e. subs-capio'
        self.assertEqual(lex["lat:caput"].root_source, "self")


@unittest.skipUnless(HAVE_LS and HAVE_DB, "Lewis & Short XML or Studio database not present")
class FinalCheckRegressionTests(unittest.TestCase):
    """The final check of 19 Nov 2026: names, untagged clusters and wrong-every-time forms."""

    def test_biblical_names_are_not_classical_people(self):
        lex = L.load_lexicon()
        wrong = {"lat:Paulus": ("Cannae", "Cannœ", "consul"), "lat:Timotheus": ("Conon",), "lat:Ammon": ("Jupi",),
                 "lat:Philippus": ("several kings of Macedonia",), "lat:Nicanor": ("grammarian", "painter"),
                 "lat:Anna": ("Dido",), "lat:Anas": ("Spain",), "lat:Mosa": ("Belgic",), "lat:Lais": ("courtesan",),
                 "lat:Elissa": ("Dido",), "lat:Nigris": ("Africa",), "lat:Barium": ("Apulia",),
                 "lat:Belgae": ("Belgians",)}
        for key, bad in wrong.items():
            g = lex[key].gloss
            for b in bad:
                self.assertNotIn(b, g, key)
        self.assertIn("Paul", lex["lat:Paulus"].gloss)
        self.assertIn("Hannah", lex["lat:Anna"].gloss)
        self.assertIn("Peter", lex["lat:Simon#1"].gloss)
        self.assertIn("Iscariot", lex["lat:Judas"].gloss)
        self.assertIn("husband of Mary", lex["lat:Joseph"].gloss)
        self.assertIn("Jew", lex["lat:Judaeus"].gloss)
        self.assertIn("Peter", lex["lat:Petrus"].gloss)

    def test_name_skeletons(self):
        def same(a, z):
            return any(L._skeletons_match(x, y) for x in L._name_keys(a) for y in L._name_keys(z))
        for a, z in (("Paulus", "Paul"), ("Ezechias", "Hezekiah"), ("Nephthali", "Naphtali"), ("Amri", "Omri"),
                     ("Achab", "Ahab"), ("Jacobus", "Ἰάκωβος"), ("Noemi", "Naomi"), ("Lachis", "Lachish")):
            self.assertTrue(same(a, z), (a, z))
        for a, z in (("David", "Judah"), ("David", "Dodo"), ("Achab", "Jacob"), ("Israel", "Azariah")):
            self.assertFalse(same(a, z), (a, z))

    def test_hebrew_names_recognised_at_their_verse(self):
        if not L._TIPNR_PEOPLE:
            self.skipTest("TIPNR not present")
        t = tags_of("invalui vocavitque eum Nephthali", "genesis", 30, 8)
        self.assertEqual(t["Nephthali"].lemma_key, "lat:Nephthali")
        self.assertIn("Naphtali", L.load_lexicon()["lat:Nephthali"].gloss)
        t = tags_of("nuntiavit Abram Hebræo qui habitabat", "genesis", 14, 13)
        self.assertNotEqual(t["Hebræo"].lemma_key, "lat:Hebraeo")            # an inflected form is no headword

    def test_untagged_clusters_now_tagged(self):
        t = tags_of("Igitur sexcentesimo primo anno primo mense")
        self.assertEqual(t["mense"].lemma_key, "lat:mensis")
        self.assertEqual(lemma_of("Igitur sexcentesimo primo anno primo mense", "primo", 1), "lat:primus")
        prim = [x for x in tag("vir primus") if x.surface == "primus"][0]
        self.assertTrue(prim.is_content)                                      # primus was a function word
        self.assertEqual(lemma_of("profugus ad orientalem plagam Eden", "plagam"), "lat:plaga#2")
        self.assertEqual(lemma_of("et facta est plaga magna nimis", "plaga"), "lat:plaga#1")
        self.assertEqual(lemma_of("audiat eum omnis synagoga filiorum Israël", "synagoga"), "lat:synagoga")
        # L&S: occido1 = occīdo [ob-caedo] 'kill'; occido2 = occĭdo [obcado] 'fall, set' (18 Nov re-check)
        self.assertEqual(lemma_of("pro Abel quem occidit Cain", "occidit"), "lat:occido#1")
        self.assertEqual(lemma_of("antequam occidat sol", "occidat"), "lat:occido#2")
        lex = L.load_lexicon()
        self.assertIn("kill", lex["lat:occido#1"].gloss)
        self.assertEqual(lex["lat:occido#1"].root_key, "lat:caedo")
        self.assertIn("sow", lex["lat:sero#1"].gloss)
        self.assertEqual(lex["lat:desero#2"].root_key, "lat:sero#2")
        self.assertNotEqual(lex["lat:deliciae"].root_key, "lat:licium")
        self.assertIn("pay", lex["lat:luo#2"].gloss)
        self.assertEqual(lemma_of("habentes alimenta et quibus tegamur his contenti sumus", "contenti"), "lat:contentus#2")
        self.assertEqual(lemma_of("scribæ eorum et pharisæi", "pharisæi"), "lat:Pharisaeus")
        self.assertEqual(lemma_of("adoravit Israël Deum conversus ad lectuli caput", "conversus"), "lat:converto")
        self.assertEqual(lemma_of("Sed et Seth natus est filius", "natus"), "lat:nascor")
        self.assertEqual(lemma_of("non inveniebatur adjutor similis ejus", "similis"), "lat:similis")
        self.assertEqual(lemma_of("vocavit Laban Tumulus testis", "testis"), "lat:testis#1")
        self.assertEqual(lemma_of("unusquisque fratrem et amicum et proximum suum", "amicum"), "lat:amicus#2")
        self.assertEqual(lemma_of("donec veniam ad dominum meum in Seir", "veniam"), "lat:venio")
        self.assertEqual(lemma_of("impetrabitque ei veniam et dimittetur illi", "veniam"), "lat:venia")
        self.assertEqual(lemma_of("Profectus inde Abraham in terram australem", "Profectus"), "lat:proficiscor")
        self.assertEqual(lemma_of("recordatus Abrahæ liberavit Lot", "Abrahæ"), "lat:Abraham")
        self.assertEqual(lemma_of("ante paradisum voluptatis cherubim", "cherubim"), "lat:Cherub")
        self.assertEqual(lemma_of("tangeremus illud ne forte moriamur", "forte"), "lat:fors")
        self.assertEqual(lemma_of("Complevitque Deus die septimo opus suum", "septimo"), "lat:septimus")
        self.assertEqual(lemma_of("intellexit igitur Noë quod", "intellexit"), "lat:intellego")
        self.assertEqual(lemma_of("Sapiens in verbis seipsum amabilem facit", "seipsum"), "lat:ipse")
        self.assertEqual(lemma_of("septem diebus aliis rursum dimisit columbam", "rursum"), "lat:rursus")

    def test_wrong_every_time_forms(self):
        self.assertEqual(lemma_of("fecitque Abraham grande convivium", "grande"), "lat:grandis")
        self.assertEqual(lemma_of("Salmon de quo ortus est Booz", "ortus"), "lat:orior")
        self.assertEqual(lemma_of("Statimque orta est lepra in fronte ejus", "orta"), "lat:orior")
        self.assertEqual(lemma_of("Exortum est in tenebris lumen", "Exortum"), "lat:exorior")
        self.assertEqual(lemma_of("quantum distat ortus ab occidente", "ortus"), "lat:ortus#2")
        self.assertEqual(lemma_of("his illis sunt deteriora", "deteriora"), "lat:deterior")
        self.assertEqual(lemma_of("et me solum relinquatis", "solum"), "lat:solus#1")
        self.assertEqual(lemma_of("tondebis usque ad solum superficiem terræ", "solum"), "lat:solum#1")
        self.assertEqual(lemma_of("non solum autem", "solum"), "lat:solum#2")
        self.assertEqual(lemma_of("et Joannem fratrem Jacobi", "Jacobi"), "lat:Jacobus")
        self.assertEqual(lemma_of("cum Jacobo et Joanne", "Jacobo"), "lat:Jacobus")
        self.assertEqual(lemma_of("Sarai sterilis nec habebat liberos", "liberos"), "lat:liberi")
        self.assertEqual(lemma_of("Ergo liberi sunt filii", "liberi"), "lat:liber#1")
        self.assertEqual(lemma_of("Libertinorum et Cyrenensium et Alexandrinorum", "Cyrenensium"), "lat:Cyrenensis")
        self.assertEqual(lemma_of("et hasta et clypeo ego autem venio", "clypeo"), "lat:clipeus")
        self.assertEqual(lemma_of("autem eritis in vinculis donec", "vinculis"), "lat:vinculum")
        self.assertNotEqual(lemma_of("Joanna qui fuit Resa qui fuit Zorobabel", "Resa"), "lat:respondeo")
        self.assertEqual(lemma_of("ejus post se versa est in statuam salis", "versa"), "lat:verto")


def _closed_lists():
    """(lemma headword, form) of every hand-listed form, built from the same constants as _install_closed."""
    out = []
    for hb, _n, _pos, forms in L._CLOSED_VERBS + L._CLOSED_PRON:
        out += [(hb, f) for f in forms]
    for hb, pre, trans in L._EO_COMPOUNDS:
        out += [(hb, pre + f) for f in L._EO + (L._EO_PASS if trans else [])]
    for hb, pres, perfs, sups in L._FERO_COMPOUNDS:
        forms = [p + f for p in pres for f in L._FERO_PRES] + [f for p in perfs for f in L._perf(p + "tul")]
        forms += [f for p in sups for f in L._a12(p + "lat") + L._a12(p + "latur") + [p + "latu"]]
        out += [(hb, f) for f in forms]
    for hb, forms in L._IRREG_COMPARISON.items():
        out += [(hb, f) for f in forms]
    for hb, forms in L._EXTRA_FORMS.items():
        out += [(L._b(hb), L._b(f)) for f in forms]
    for key, forms in L._NAME_FORMS.items():
        out += [(L._b(key[4:]), f) for f in forms]
    return out


class MorphTableTests(unittest.TestCase):
    """Parsing codes (TokenTag.morph, 18 Nov 2026): the tables need no data files."""

    def test_every_class_and_ending_has_cells(self):
        for pc, ends in L.ENDINGS.items():
            self.assertIn(pc, L._CLASS_DESC, pc)
            for e in ends:
                self.assertTrue(L._PARADIGM_CELLS.get(pc, {}).get(e or "0"), (pc, e))
        for pc, cells in L._PARADIGM_CELLS.items():      # no cells for endings the class does not have
            for e in cells:
                self.assertIn("" if e == "0" else e, L.ENDINGS[pc], (pc, e))
        for cls in L._HEAD_CELLS:
            self.assertIn(cls, L._CLASS_DESC)

    def test_every_closed_form_has_cells(self):
        pairs = _closed_lists()
        self.assertGreater(len(pairs), 3000)
        missing = [(hb, f) for hb, f in pairs if not L._closed_cells(hb, f)]
        self.assertEqual(missing, [])

    def test_closed_cells(self):
        cases = {("sum", "est"): ["present indicative 3rd singular"],
                 ("sum", "es"): ["present indicative 2nd singular", "present imperative 2nd singular"],
                 ("adsum", "adest"): ["present indicative 3rd singular"],
                 ("is", "eius"): ["genitive singular"],
                 ("hic", "hoc"): ["nominative/accusative neuter singular", "ablative masculine/neuter singular"],
                 ("quidam", "quendam"): ["accusative masculine singular"],
                 ("ille", "illum"): ["accusative masculine singular"],
                 ("ipse", "ipsum"): ["accusative masculine singular", "nominative/accusative neuter singular"],
                 ("affero", "attulit"): ["perfect indicative active 3rd singular"],
                 ("bonus", "melior"): ["comparative nominative/vocative masculine/feminine singular"],
                 ("bonus", "optimam"): ["superlative accusative feminine singular"],
                 ("locus", "loca"): ["nominative/accusative/vocative plural (neuter plural form)"]}
        for (hb, f), want in cases.items():
            self.assertEqual(L._closed_cells(hb, f), want, (hb, f))
        self.assertIn("perfect indicative active 3rd plural", L._closed_cells("transeo", "transierunt"))
        self.assertIn("perfect passive participle nominative masculine singular",
                      L._closed_cells("transeo", "transitus"))
        self.assertEqual(L._closed_cells("abeo", "abitus"), [])          # intransitive: no passive participle

    def test_legend_examples(self):
        leg = L.morph_legend(include_closed=False)
        self.assertEqual(leg["L:N1|am"], "1st declension noun (-a, -ae), ending -am: accusative singular")
        self.assertIn("genitive/dative singular", leg["L:N1|ae"])
        self.assertIn("nominative/vocative plural", leg["L:N1|ae"])           # every cell, not one
        self.assertIn("present indicative active 3rd plural", leg["L:V3A|unt"])
        self.assertIn("future indicative active 1st singular", leg["L:V3A|am"])
        self.assertIn("present subjunctive active 1st singular", leg["L:V3A|am"])
        self.assertIn("vocative singular (fili)", leg["L:N2IUS|0"])
        self.assertIn("supine", leg["L:VPP|um"])
        self.assertIn("not inflected", leg["L:CONJ|head"])
        self.assertIn("no case is derived", leg["L:PROPN|head"])
        for pc, ends in L.ENDINGS.items():
            for e in ends:
                self.assertIn(f"L:{pc}|{e or '0'}", leg)
        for code, text in leg.items():
            self.assertTrue(code.startswith("L:") and text, code)
            self.assertFalse(re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", text), code)


@unittest.skipUnless(HAVE_LS and HAVE_DB, "Lewis & Short XML or Studio database not present")
class MorphTaggingTests(unittest.TestCase):
    """Codes on tagged tokens (lemma choices use the corpus priors from data/studio.db, read-only)."""

    def codes(self, text):
        return {t.surface: (t.lemma_key, t.morph) for t in tag(text)}

    def test_codes_on_tokens(self):
        cases = [
            ("Et facta est lux.", {"Et": "L:CONJ|head", "facta": "L:VPP|a", "est": "L:closed|est"}),
            ("fili mi, audi disciplinam", {"fili": "L:N2IUS|0", "mi": "L:closed|mi", "audi": "L:V4A|i",
                                           "disciplinam": "L:N1|am"}),
            ("et puer crescebat", {"puer": "L:N2R|head", "crescebat": "L:V3A|ebat"}),
            ("qui legit intelligat", {"qui": "L:closed|qui", "legit": "L:V3A|it,L:VPF|it", "intelligat": "L:V3A|at"}),
            ("Dic nobis", {"Dic": "L:V3A|short", "nobis": "L:closed|nobis"}),
            ("Fac mihi", {"Fac": "L:V3IA|short", "mihi": "L:closed|mihi"}),
            ("ait Dominus ad Moysen dicens", {"ait": "L:closed|ait", "Dominus": "L:N2|us", "ad": "L:PREP|head",
                                              "Moysen": "L:NAME|en", "dicens": "L:V2N|ens"}),
            ("et mecum eris", {"mecum": "L:closed|me", "eris": "L:closed|eris"}),
            ("et misit eumque semetipsum", {"misit": "L:VPF|it", "eumque": "L:closed|eum",
                                            "semetipsum": "L:closed|ipsum"}),
            ("et rex Israël", {"rex": "L:N3|head", "Israël": "L:PROPN|head"}),
            ("non est melior patribus meis", {"non": "L:PART|head", "melior": "L:CMP|ior,L:closed|melior",
                                              "patribus": "L:N3|ibus", "meis": "L:A12|is"}),
            ("attulit munera", {"attulit": "L:closed|attulit", "munera": "L:N3N|a"}),
            ("et dabo tibi", {"dabo": "L:V1A|abo", "tibi": "L:closed|tibi"}),
        ]
        for text, want in cases:
            got = self.codes(text)
            for w, code in want.items():
                self.assertEqual(got[w][1], code, (text, w, got[w]))

    def test_every_tagged_token_has_a_code_with_a_legend(self):
        leg = L.morph_legend()
        text = ("In principio creavit Deus cælum et terram. Terra autem erat inanis et vacua, et tenebræ erant super "
                "faciem abyssi: et spiritus Dei ferebatur super aquas. Dixitque Deus: Fiat lux. Et facta est lux.")
        for t in tag(text):
            if t.lemma_key is None:
                self.assertIsNone(t.morph, t)
                continue
            self.assertTrue(t.morph and t.morph.startswith("L:"), t)
            parts = t.morph.split(",")
            self.assertEqual(parts, sorted(set(parts)), t)
            for c in parts:
                self.assertIn(c, leg, t)

    def test_describe_morph(self):
        self.assertEqual(L.describe_morph("L:closed|est", "lat:sum#1"),
                         "hand-listed form 'est': present indicative 3rd singular")
        d = L.describe_morph("L:V3A|it,L:VPF|it")
        self.assertIn("present indicative active 3rd singular", d)
        self.assertIn("perfect indicative active 3rd singular", d)
        self.assertEqual(L.describe_morph(None), "")

    def test_morph_changes_no_lemma_choice(self):
        """Tag whole chapters with and without the parsing step: lemma, method, confidence, notes identical."""
        import sqlite3
        conn = sqlite3.connect(f"file:{_LIVE_DB.as_posix()}?mode=ro", uri=True)
        try:
            chapters = []
            for book, ch in (("genesis", 1), ("john", 1), ("psalms", 118), ("1-kings", 12)):
                rows = conn.execute("SELECT v.verse, v.critical_text FROM verses v JOIN chapters c ON c.id = "
                                    "v.chapter_id WHERE c.language = 'latin' AND c.book_slug = ? AND c.chapter = ?",
                                    (book, ch)).fetchall()
                chapters.append((book, ch, {int(v): t or "" for v, t in rows}))
        finally:
            conn.close()
        self.assertTrue(all(verses for _b, _c, verses in chapters))

        def run():
            out = []
            for book, ch, verses in chapters:
                for v, tags in sorted(L.tag_chapter(book, ch, verses).items()):
                    out += [(book, ch, v, t.index, t.surface, t.lemma_key, t.method, t.confidence, t.is_content,
                             t.prefixes, tuple(t.notes)) for t in tags]
            return out

        with_morph = run()
        real = L._morph_for
        L._morph_for = lambda *a, **k: None          # type: ignore[assignment]
        try:
            without = run()
        finally:
            L._morph_for = real                      # type: ignore[assignment]
        self.assertGreater(len(with_morph), 2000)
        self.assertEqual(with_morph, without)


@unittest.skipUnless(HAVE_LS and HAVE_DB, "Lewis & Short XML or Studio database not present")
class UntaggedResolutionTests(unittest.TestCase):
    """Regressions for the 19 Nov 2026 Latin untagged-token pass (Stage 3A parser/paradigms + Stage 3B syntax)."""

    def test_stage3a_parser_and_paradigm_fixes(self):
        cases = [
            ("Non revertetur furor Domini", "revertetur", "lat:reverto"),
            ("operuit confusio faciem meam", "operuit", "lat:operio"),
            ("et quievit terra quadraginta annis", "quievit", "lat:quiesco"),
            ("exstruxit altare Domino", "exstruxit", "lat:exstruo"),
            ("Circumda tibi vestimentum tuum", "Circumda", "lat:circumdo"),
            ("lavabit vestimenta sua", "lavabit", "lat:lavo"),
            ("cave ne pugnes contra eos", "cave", "lat:caveo"),
            ("dispergam eos in gentibus", "dispergam", "lat:dispergo"),
            ("dispersit superbos mente cordis sui", "dispersit", "lat:dispergo"),
            ("elevata est altitudo ejus", "elevata", "lat:elevo"),
            ("quæcumque prophetavit Jeremias", "prophetavit", "lat:propheto"),
            ("misertus est super eos", "misertus", "lat:misereo"),
            ("de bobus sive de ovibus", "bobus", "lat:bos"),
            ("per vim nihil rapuerit", "vim", "lat:vis"),
            ("in atrio interiori", "interiori", "lat:interior"),
            ("nescierunt viam pacis", "nescierunt", "lat:nescio"),
            ("nescitis enim qua hora", "nescitis", "lat:nescio"),
            ("fecitque Deus duo luminaria magna", "luminaria", "lat:luminare"),
            ("promissionem habens vitæ", "promissionem", "lat:promissio"),
            ("obstupuerunt unusquisque ad proximum", "obstupuerunt", "lat:obstipesco"),
            ("et minime repererunt", "repererunt", "lat:reperio"),
            ("armigerum suum", "armigerum", "lat:armiger"),
            ("oppressit eos", "oppressit", "lat:opprimo"),
            ("in vobismetipsis", "vobismetipsis", "lat:ipse"),
            ("omne quod ruminat", "ruminat", "lat:ruminor"),
            ("prunis ignis", "prunis", "lat:pruna"),
            ("sororem suam", "sororem", "lat:soror"),
            ("a dextris meis", "dextris", "lat:dexter"),
            ("et crucifixerunt eum", "crucifixerunt", "lat:crucifigo"),
            ("et de Philisthinorum manu", "Philisthinorum", "lat:Philisthinus"),
            ("Baalim et Astaroth", "Baalim", "lat:Baal"),
            ("ex hyacintho et purpura", "hyacintho", "lat:Hyacinthus"),
            ("quotidie scrutantes Scripturas", "Scripturas", "lat:scriptura"),
        ]
        for text, tok, want in cases:
            self.assertEqual(lemma_of(text, tok), want, (text, tok))
        # Noëmi (Ruth 1:2) resolved at its verse via TIPNR, not truncated to Noe
        t = tags_of("uxor ejus Noëmi", "ruth", 1, 2)
        self.assertEqual(t["Noëmi"].lemma_key, "lat:Noemi")
        self.assertEqual(lemma_of("et venit Alcimus ad regem", "Alcimus"), "lat:Alcimus")

    def test_stage3b_orthography_priors_and_syntax(self):
        # Orthography: voluit vs volvit; æris vs aëris
        self.assertEqual(lemma_of("quia voluit Dominus occidere eos", "voluit"), "lat:volo#1")
        self.assertEqual(lemma_of("et volvit lapidem magnum", "volvit"), "lat:volvo")
        self.assertEqual(lemma_of("pondus æris omnium vasorum", "æris"), "lat:aes")
        self.assertEqual(lemma_of("potestatis aëris hujus", "aëris"), "lat:aer")
        # Enclitic-stripped _FORM_PRIOR + lemma priors + dual-use rules
        self.assertEqual(lemma_of("Profectique sunt de Ramesse", "Profectique"), "lat:proficiscor")
        self.assertEqual(lemma_of("animalium mundorum", "animalium"), "lat:animal")
        self.assertEqual(lemma_of("spiritus fornicationis", "fornicationis"), "lat:fornicatio#2")
        self.assertEqual(lemma_of("in Silo ad tabernaculum", "Silo"), "lat:Silo")
        self.assertEqual(lemma_of("Mementote vinctorum, tamquam simul vincti", "vinctorum"), "lat:vincio")
        self.assertEqual(lemma_of("Domine, vis dicimus ut ignis descendat?", "vis"), "lat:volo#1")
        self.assertEqual(lemma_of("nulla vis poterat illis lumen præbere", "vis"), "lat:vis")
        # Big-5 syntactic rules (and dative+subjunctive guard on 2 Chr 16:8)
        self.assertEqual(lemma_of("a loco in quo nunc es", "quo"), "lat:qui#1")
        self.assertEqual(lemma_of("Dormivitque cum patribus suis", "cum"), "lat:cum#1")
        self.assertEqual(lemma_of("Et cum vidisset Jesus turbas", "cum"), "lat:cum#2")
        self.assertIsNone(lemma_of("quos cum Domino credidisses, tradidit", "cum"))
        self.assertEqual(lemma_of("propter quod interfecit eum", "quod"), "lat:qui#1")
        self.assertEqual(lemma_of("Quod si non se continent", "Quod"), "lat:quod#1")
        self.assertEqual(lemma_of("Quod cum vidisset armiger ejus", "Quod"), "lat:qui#1")
        self.assertEqual(lemma_of("unusquisque vestrum psalmum habet", "vestrum"), "lat:vos")
        self.assertEqual(lemma_of("Dominum Deum vestrum timete", "vestrum"), "lat:vester")

    def test_stage3c_vulgate_paradigms_names_and_syntax(self):
        cases = [
            # Vulgate paradigms, closed forms, double ordinals, sub-entries, Tier-3 variants
            ("in gazophylacium Domini", "gazophylacium", "lat:gazophylacium"),
            ("factus est terræmotus magnus", "terræmotus", "lat:terraemotus"),
            ("quartadecima die mensis", "quartadecima", "lat:quartusdecimus"),
            ("induti ciliciis et cinere", "ciliciis", "lat:cilicium"),
            ("baptismum pœnitentiæ", "baptismum", "lat:baptismus"),
            ("myrrhæ et aloes", "myrrhæ", "lat:murra#1"),
            ("succidit sycomoros eorum", "sycomoros", "lat:sycaminus"),
            ("odivi ecclesiam malignantium", "odivi", "lat:odi"),
            ("Ecce ego moriturus sum", "moriturus", "lat:morior"),
            ("ultus est Dominus", "ultus", "lat:ulciscor"),
            ("ne dispereat nomen ejus", "dispereat", "lat:dispereo"),
            ("exies de loco isto", "exies", "lat:exeo"),
            ("Quæ cum abiisset, errabat", "abiisset", "lat:abeo"),
            ("domum tuam decent sancta", "decent", "lat:decet"),
            ("quoties volui congregare", "quoties", "lat:quotiens"),
            ("immo beati qui audiunt", "immo", "lat:immo"),
            ("loquebatur judaice et syriace", "judaice", "lat:judaice"),
            ("loquebatur judaice et syriace", "syriace", "lat:syriace"),
            ("ariolos et haruspices", "ariolos", "lat:hariolus"),
            ("arundinem quassatam non confringet", "arundinem", "lat:harundo"),
            ("caracterem bestiæ", "caracterem", "lat:character"),
            ("in beneplacito tuo", "beneplacito", "lat:beneplacitum"),
            ("valefaciens fratribus", "valefaciens", "lat:valefacio"),
            ("accepistis bravium", "bravium", "lat:brabeum"),
            ("ad superiorem portam", "superiorem", "lat:superus"),
            ("qui subintroierunt explorare", "subintroierunt", "lat:subintroeo"),
            ("nuntiavit Abram Hebræo", "Hebræo", "lat:Hebraeus"),
            # Proper names (Cyrillic-y, oblique TIPNR, Greek -poleos, mid-sentence TIPNR)
            ("idolum Chamos", "Chamos", "lat:Chamos"),
            ("natatoria Siloë", "Siloë", "lat:Siloe"),
            ("Phacee filius Romeliæ", "Romeliæ", "lat:Romelias"),
            ("filios Zebedæi", "Zebedæi", "lat:Zebedaeus"),
            ("orationes tuæ, Corneli", "Corneli", "lat:Cornelius"),
            ("sacerdotis Heliopoleos", "Heliopoleos", "lat:Heliopolis"),
            # Verified biblical priors & crisp context splits
            ("omnes sancti ejus", "sancti", "lat:sanctus"),
            ("beati pauperes spiritu", "beati", "lat:beatus"),
            ("rectum est cor ejus", "rectum", "lat:rectus"),
            ("reddite vota vestra", "vota", "lat:votum"),
            ("in mensa regis", "mensa", "lat:mensa"),
            ("mensa est civitas", "mensa", "lat:metior"),
            ("super aquas vivas", "vivas", "lat:vivus"),
            ("ut longo vivas tempore", "vivas", "lat:vivo"),
            ("Tu autem ibis ad patres tuos", "ibis", "lat:eo#1"),
            ("onocrotalus et ericius, ibis et corvus", "ibis", "lat:ibis"),
            ("mille passus vade cum illo", "passus", "lat:passus#3"),
            ("et quasi dira passus", "passus", "lat:patior"),
            ("des mihi in disco caput", "disco", "lat:discus"),
            ("reficientes retia sua", "retia", "lat:rete"),
            # Upgraded Big-5 syntax rules
            ("cum rege Israël", "cum", "lat:cum#1"),
            ("cum exercitu magno", "cum", "lat:cum#1"),
            ("cum servis tuis", "cum", "lat:cum#1"),
            ("cum populo suo", "cum", "lat:cum#1"),
            ("Quæ cum abiisset", "cum", "lat:cum#2"),
            ("cum hæc audisset", "cum", "lat:cum#2"),
            ("cum se non possent", "cum", "lat:cum#2"),
            ("cum centum esset annorum", "cum", "lat:cum#2"),
            ("cor vestrum non turbetur", "vestrum", "lat:vester"),
            ("exercitum vestrum de terra", "vestrum", "lat:vester"),
            ("peccatum vestrum apprehendet vos", "vestrum", "lat:vester"),
            ("Quam cum vidisset", "Quam", "lat:qui#1"),
            ("turrim quam ædificabant", "quam", "lat:qui#1"),
            ("verbum Domini quod factum est", "quod", "lat:qui#1"),
            ("pactum quod observabitis", "quod", "lat:qui#1"),
            ("opus quod fecisti", "quod", "lat:qui#1"),
            ("Quo nato vocavit nomen ejus", "Quo", "lat:qui#1"),
            ("Quo cum pervenisset", "Quo", "lat:qui#1"),
            ("Quo transeunte coram eo", "Quo", "lat:qui#1"),
        ]
        for text, tok, want in cases:
            self.assertEqual(lemma_of(text, tok), want, (text, tok))
        # Verse-contextual TIPNR names cached cleanly after _ensure_priors (and verb-only-capital guard)
        self.assertEqual(tags_of("Super Nabo et super Medaba", "isaiah", 15, 2)["Nabo"].lemma_key, "lat:Nabo")
        self.assertEqual(tags_of("Reversa est cognata tua, Noëmi", "ruth", 1, 15)["Noëmi"].lemma_key, "lat:Noemi")
        self.assertEqual(tags_of("Sidrach, Misach, et Abdenago", "daniel", 3, 93)["Abdenago"].lemma_key, "lat:Abdenago")


if __name__ == "__main__":
    unittest.main()

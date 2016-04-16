# -*- coding: utf-8 -*-
from __future__ import print_function

import sys
import unicodedata
import pkg_resources
import os.path
from collections import defaultdict
import unicodecsv as csv
import regex as re
import panphon


class Epitran(object):
    """Transliterate text in Latin scripts to Unicode IPA."""
    def __init__(self, code):
        self.g2p = self._load_g2p_map(code)
        self.regexp = self._construct_regex()
        self.ft = panphon.FeatureTable()
        self.num_panphon_fts = len(self.ft.names)

    def _load_g2p_map(self, code):
        """Load the code table for the specified language.

        code -- ISO 639-3 code for the language to be loaded
        """
        g2p = defaultdict(list)
        path = os.path.join('data', code + '.csv')
        path = pkg_resources.resource_filename(__name__, path)
        try:
            with open(path, 'rb') as f:
                reader = csv.reader(f, encoding='utf-8')
                reader.next()
                for graph, phon in reader:
                    graph = unicodedata.normalize('NFD', graph)
                    phon = unicodedata.normalize('NFD', phon)
                    g2p[graph].append(phon)
        except IOError:
            print(u'Unknown language.')
            print(u'Add an appropriately-named mapping to the data folder.')
        return g2p

    def _construct_regex(self):
        """Build a regular expression that will greadily match segments from
           the mapping table.
        """
        graphemes = sorted(self.g2p.keys(), key=len, reverse=True)
        #  print(graphemes)
        return re.compile(ur'({})'.format(ur'|'.join(graphemes)), re.I)

    def transliterate(self, text):
        """Transliterate text from orthography to Unicode IPA.

        text -- The text to be transliterated
        """
        def trans(m):
            if m.group(0) in self.g2p:
                return self.g2p[m.group(0)][0]
            else:
                print('Cannot match "{}"!'.format(m.group(0)), file=sys.stderr)
                return m.group(0)
        text = unicodedata.normalize('NFD', text.lower())
        return self.regexp.sub(trans, text)

    def robust_trans_pairs(self, text):
        pairs = []
        while text:
            # print(text)
            match = self.regexp.match(text)
            if match:
                span = match.group(0)
                pairs.append((span, self.transliterate(span)))
                text = text[len(span):]
            else:
                pairs.append((text[0], ''))
                text = text[1:]
        return pairs

    def case_cat_graph_phon_tuples(self, text):
        def detect_case(span):
            cat_0, case_0 = tuple(unicodedata.category(span[0]))
            return 1 if case_0 == 'u' else 0

        def detect_cat(span):
            cat_0, case_0 = tuple(unicodedata.category(span[0]))
            return cat_0

        word = self.robust_trans_pairs(text)
        return [(detect_case(graph), detect_cat(graph), graph, phon) for (graph, phon) in word]

    def plus_vector_tuples(self, text):
        def recode_ft(ft):
            if ft == '+':
                return 1
            elif ft == '0':
                return 0
            elif ft == '-':
                return -1

        def vec2bin(vec):
            return map(recode_ft, vec)

        def to_vector(seg):
            return self.ft.seg_seq[seg], vec2bin(self.ft.segment_to_vector(seg))

        def to_vectors(phon):
            if phon == '':
                return [(-1, [0] * self.num_panphon_fts)]
            else:
                return [to_vector(seg) for seg in self.ft.segs(phon)]

        word = self.case_cat_graph_phon_tuples(text)
        return [(case, cat, graph, phon, to_vectors(phon)) for (case, cat, graph, phon) in word]

    def word_to_pfvector(self, word):
        """Given an orthographic word, returns a phonological feature vector.

        word -- Unicode string representing a word in the orthography specified
                when the class is instantiated.
        return -- a list of tuples (each representing an IPA segment) consisting
                  of <category, lettercase, phonetic_form, ipa_id, vector> where
                  vector is a list of {-1, 0, 1} where -1 represents "-", 0
                  represents "0", and 1 represents "+". Non-letter characters
                  are represented as a sequence of 0s.
        """
        segs = []
        for case, cat, graph, phon, vectors in self.plus_vector_tuples(word):
            for id_, vector in vectors:
                segs.append((cat, case, phon, id_, vector))
        return segs

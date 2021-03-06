#!/usr/bin/env python
"""Trim adaptor sequences from reads; designed for short read sequencing.

Allows trimming of adaptor sequences from a list of SeqRecords produced
by the Biopython SeqIO library.

This can be imported for use in other scripts, or can be run directly. Running
the script with no arguments will run the tests. Run directly, it will convert a
fastq to a fasta output file, trimming with the passed adaptor:

Usage:

    adaptor_trim.py <in fastq file> <out fasta file> <adaptor seq> <number of errors>
"""
from __future__ import with_statement
import sys
import os

from Bio import pairwise2
from Bio.Seq import Seq
from Bio import SeqIO

def _remove_adaptor(seq, region, right_side=True):
    """Remove an adaptor region and all sequence to the right or left.
    """
    # A check for repetitive regions. We handle them below by searching
    # from the left or right depending on the trimming method which should
    # be the expected result.
    #size = len(region)
    #pieces = [str(seq[i:i+size]) for i in range(len(seq) - size)]
    #if pieces.count(region) != 1:
    #    raise ValueError("Non-single match: %s to %s" % (region, seq))
    if right_side:
        try:
            pos = seq.find(region)
        # handle Biopython SeqRecords
        except AttributeError:
            pos = seq.seq.find(region)
        return seq[:pos]
    else:
        try:
            pos = seq.rfind(region)
        # handle Biopython SeqRecords
        except AttributeError:
            pos = seq.seq.rfind(region)
        return seq[pos+len(region):]

def trim_adaptor(seq, adaptor, num_errors, right_side=True):
    """Trim the given adaptor sequence from a starting sequence.

    * seq can be either of:
       - string
       - Biopython SeqRecord
    * adaptor is a string sequence
    * num_errors specifies how many errors are allowed in the match between
    adaptor and the base sequence. Matches with more than this number of errors
    are not allowed.
    """
    gap_char = '-'
    exact_pos = str(seq).find(adaptor)
    if exact_pos >= 0:
        seq_region = str(seq[exact_pos:exact_pos+len(adaptor)])
        adapt_region = adaptor
    else:
        aligns = pairwise2.align.localms(str(seq), str(adaptor), 
                5.0, -4.0, -9.0, -0.5, one_alignment_only=True, 
                gap_char=gap_char)
        if len(aligns) == 0:
            adapt_region, seq_region = ("", "")
        else:
            seq_a, adaptor_a, score, start, end = aligns[0]
            adapt_region = adaptor_a[start:end]
            #print seq_a, adaptor_a, score, start, end
            seq_region = seq_a[start:end]
    matches = sum((1 if s == adapt_region[i] else 0) for i, s in
            enumerate(seq_region))
    # too many errors -- no trimming
    if (len(adaptor) - matches) > num_errors:
        return seq
    # remove the adaptor sequence and return the result
    else:
        return _remove_adaptor(seq, seq_region.replace(gap_char, ""),
                right_side)

def trim_adaptor_w_qual(seq, qual, adaptor, num_errors, right_side=True):
    """Trim an adaptor with an associated quality string.

    Works like trimmed adaptor, but also trims an associated quality score.
    """
    assert len(seq) == len(qual)
    tseq = trim_adaptor(seq, adaptor, num_errors, right_side=right_side)
    if right_side:
        pos = seq.find(tseq)
    else:
        pos = seq.rfind(tseq)
    tqual = qual[pos:pos+len(tseq)]
    assert len(tseq) == len(tqual)
    return tseq, tqual

# ------- Testing Code
import unittest

from Bio.SeqRecord import SeqRecord
from Bio.Seq import Seq
from Bio.Alphabet.IUPAC import unambiguous_dna

class AdaptorAlignTrimTest(unittest.TestCase):
    """Test remove adaptor sequences using local alignments.
    """
    def t_1_simple_trim(self):
        """Trim adaptor from non-complex region with errors and deletions.
        """
        adaptor = "GATCGATCGATC"
        tseq = trim_adaptor("GGG" + adaptor + "CCC", adaptor, 2) # exact
        assert tseq == "GGG"
        tseq = trim_adaptor("GGG" + "GATCGTTCGATC" + "CCC", adaptor, 2)# 1 error
        assert tseq == "GGG"
        tseq = trim_adaptor("GGG" + "GATCGTTCGAAC" + "CCC", adaptor, 2)# 2 errors
        assert tseq == "GGG"
        tseq = trim_adaptor("GGG" + "GATCGATCGTC" + "CCC", adaptor, 2) # deletion
        assert tseq == "GGG"
        tseq = trim_adaptor("GGG" + "GACGATCGTC" + "CCC", adaptor, 2) # deletion
        assert tseq == "GGG"
        tseq = trim_adaptor("GGG" + "GAACGTTGGATC" + "CCC", adaptor, 2)# 3 errors
        assert tseq == "GGGGAACGTTGGATCCCC"
        tseq = trim_adaptor("GGG" + "CATCGGACGTAT" + "CCC", adaptor, 2)# very bad
        assert tseq == "GGGCATCGGACGTATCCC"

    def t_2_alternative_side_trim(self):
        """Trim adaptor from both sides of the sequence.
        """
        adaptor = "GATCGATCGATC"
        tseq = trim_adaptor("GGG" + "GATCGTTCGATC" + "CCC", adaptor, 2)
        assert tseq == "GGG"
        tseq = trim_adaptor("GGG" + "GATCGTTCGATC" + "CCC", adaptor, 2, False)
        assert tseq == "CCC"

    def t_3_repetitive_sequence(self):
        """Trim a repetitive adaptor sequence.
        """
        adaptor = "GATCGATC"
        tseq = trim_adaptor("GGG" + "GATCGATCGATC" + "CCC", adaptor, 2)
        assert tseq == "GGG"
        tseq = trim_adaptor("GGG" + "GATCGATCGATC" + "CCC", adaptor, 2, False)
        assert tseq == "CCC"

    def t_4_passing_seqs(self):
        """Handle both Biopython Seq and SeqRecord objects.
        """
        adaptor = "GATCGATCGATC"
        seq = Seq("GGG" + "GATCGTTCGATC" + "CCC", unambiguous_dna)
        tseq = trim_adaptor(seq, adaptor, 2)
        assert isinstance(tseq, Seq)
        assert tseq.alphabet == unambiguous_dna
        tseq = trim_adaptor(seq=seq, adaptor=adaptor, num_errors=2)
        assert isinstance(tseq, Seq)
        assert tseq.alphabet == unambiguous_dna
        trec = trim_adaptor(SeqRecord(seq, "test_id", "test_name", "test_d"),
                adaptor, 2)
        assert isinstance(trec, SeqRecord)
        assert trec.id == "test_id"
        assert str(trec.seq) == "GGG"
        trec = trim_adaptor(SeqRecord(seq, "test_id", "test_name", "test_d"),
                adaptor, 2, False)
        assert isinstance(trec, SeqRecord)
        assert str(trec.seq) == "CCC"

    def t_5_passing_tuple(self):
        """Handle passing a tuple of sequence and quality as input.
        """
        adaptor = "GATCGATCGATC"
        seq = "GGG" + "GATCGTTCGATC" + "CCC"
        qual = "YDV`a`a^[Xa`a`^`_O"
        tseq, tqual = trim_adaptor_w_qual(seq, qual, adaptor, num_errors=2)
        assert tseq == "GGG"
        assert tqual == "YDV"
        tseq, tqual = trim_adaptor_w_qual(seq, qual, adaptor, num_errors=2,
                right_side=False)
        assert tseq == "CCC"
        assert tqual == "`_O"

    def t_6_no_alignment(self):
        """Correctly handle case with no alignment between adaptor and sequence.
        """
        adaptor = "AAAAAAAAAAAAAA"
        to_trim = "TTTTTTTTTTTTTTTTT"
        tseq = trim_adaptor(to_trim, adaptor, 2)
        assert tseq == to_trim

def run_tests(argv):
    test_suite = testing_suite()
    runner = unittest.TextTestRunner(sys.stdout, verbosity = 2)
    runner.run(test_suite)

def testing_suite():
    """Generate the suite of tests.
    """
    test_suite = unittest.TestSuite()
    test_loader = unittest.TestLoader()
    test_loader.testMethodPrefix = 't_'
    tests = [AdaptorAlignTrimTest]
    for test in tests:
        cur_suite = test_loader.loadTestsFromTestCase(test)
        test_suite.addTest(cur_suite)
    return test_suite

def main(in_file, out_file, adaptor_seq, num_errors):
    num_errors = int(num_errors)
   
    with open(in_file) as in_handle:
        with open(out_file, "w") as out_handle:
            for rec in SeqIO.parse(in_handle, "fastq"):
                trim = trim_adaptor(rec.seq, adaptor_seq, num_errors)
                if len(trim) > 0 and len(trim) < len(rec):
                    rec.letter_annotations = {}
                    rec.seq = trim
                    SeqIO.write([rec], out_handle, "fasta")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(run_tests(sys.argv))
    else:
        main(*sys.argv[1:])
        

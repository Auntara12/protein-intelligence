"""
Smith-Waterman Local Sequence Alignment
========================================
Implemented from scratch using dynamic programming.

Algorithm: Smith-Waterman (1981)
  - Local alignment: finds the highest-scoring aligned subsequence
  - Better than Needleman-Wunsch (global) for proteins with conserved domains
    surrounded by divergent regions

Scoring:
  - Substitution: BLOSUM62 matrix (log-odds scores from 62% identity blocks)
  - Gap open penalty: -11 (standard for protein alignment)
  - Gap extend penalty: -1 (affine gap penalty)

Complexity:
  - Time: O(m * n) where m, n are sequence lengths
  - Space: O(m * n) for full traceback matrix
            O(min(m,n)) if only the score is needed (not implemented here)

Affine gap penalty (gap_open + k * gap_extend for gap of length k):
  We use three matrices:
    H[i][j] = best score ending at (i, j) with any alignment
    E[i][j] = best score ending at (i, j) with gap in sequence 1
    F[i][j] = best score ending at (i, j) with gap in sequence 2

  Recurrence:
    E[i][j] = max(H[i][j-1] + gap_open + gap_extend,
                  E[i][j-1] + gap_extend)
    F[i][j] = max(H[i-1][j] + gap_open + gap_extend,
                  F[i-1][j] + gap_extend)
    H[i][j] = max(0,
                  H[i-1][j-1] + blosum62(s1[i], s2[j]),
                  E[i][j],
                  F[i][j])

Interview note: This is structurally identical to the LeetCode "Edit Distance"
problem (LC 72) with a domain-specific scoring function instead of uniform costs.
"""

import numpy as np
from typing import Tuple, Dict, Optional
from dataclasses import dataclass

# BLOSUM62 substitution matrix
# Source: NCBI BLAST BLOSUM62
# Scores represent log-odds of observing amino acid pair in aligned blocks
# at 62% identity vs random expectation
BLOSUM62: Dict[Tuple[str, str], int] = {}

_BLOSUM62_RAW = """
   A  R  N  D  C  Q  E  G  H  I  L  K  M  F  P  S  T  W  Y  V  B  Z  X  *
A  4 -1 -2 -2  0 -1 -1  0 -2 -1 -1 -1 -1 -2 -1  1  0 -3 -2  0 -2 -1  0 -4
R -1  5  0 -2 -3  1  0 -2  0 -3 -2  2 -1 -3 -2 -1 -1 -3 -2 -3 -1  0 -1 -4
N -2  0  6  1 -3  0  0  0  1 -3 -3  0 -2 -3 -2  1  0 -4 -2 -3  3  0 -1 -4
D -2 -2  1  6 -3  0  2 -1 -1 -3 -4 -1 -3 -3 -1  0 -1 -4 -3 -3  4  1 -1 -4
C  0 -3 -3 -3  9 -3 -4 -3 -3 -1 -1 -3 -1 -2 -3 -1 -1 -2 -2 -1 -3 -3 -2 -4
Q -1  1  0  0 -3  5  2 -2  0 -3 -2  1  0 -3 -1  0 -1 -2 -1 -2  0  3 -1 -4
E -1  0  0  2 -4  2  5 -2  0 -3 -3  1 -2 -3 -1  0 -1 -3 -2 -2  1  4 -1 -4
G  0 -2  0 -1 -3 -2 -2  6 -2 -4 -4 -2 -3 -3 -2  0 -2 -2 -3 -3 -1 -2 -1 -4
H -2  0  1 -1 -3  0  0 -2  8 -3 -3 -1 -2 -1 -2 -1 -2 -2  2 -3  0  0 -1 -4
I -1 -3 -3 -3 -1 -3 -3 -4 -3  4  2 -3  1  0 -3 -2 -1 -3 -1  3 -3 -3 -1 -4
L -1 -2 -3 -4 -1 -2 -3 -4 -3  2  4 -2  2  0 -3 -2 -1 -2 -1  1 -4 -3 -1 -4
K -1  2  0 -1 -3  1  1 -2 -1 -3 -2  5 -1 -3 -1  0 -1 -3 -2 -2  0  1 -1 -4
M -1 -1 -2 -3 -1  0 -2 -3 -2  1  2 -1  5  0 -2 -1 -1 -1 -1  1 -3 -1 -1 -4
F -2 -3 -3 -3 -2 -3 -3 -3 -1  0  0 -3  0  6 -4 -2 -2  1  3 -1 -3 -3 -1 -4
P -1 -2 -2 -1 -3 -1 -1 -2 -2 -3 -3 -1 -2 -4  7 -1 -1 -4 -3 -2 -2 -1 -2 -4
S  1 -1  1  0 -1  0  0  0 -1 -2 -2  0 -1 -2 -1  4  1 -3 -2 -2  0  0  0 -4
T  0 -1  0 -1 -1 -1 -1 -2 -2 -1 -1 -1 -1 -2 -1  1  5 -2 -2  0 -1 -1  0 -4
W -3 -3 -4 -4 -2 -2 -3 -2 -2 -3 -2 -3 -1  1 -4 -3 -2 11  2 -3 -4 -3 -2 -4
Y -2 -2 -2 -3 -2 -1 -2 -3  2 -1 -1 -2 -1  3 -3 -2 -2  2  7 -1 -3 -2 -1 -4
V  0 -3 -3 -3 -1 -2 -2 -3 -3  3  1 -2  1 -1 -2 -2  0 -3 -1  4 -3 -2 -1 -4
B -2 -1  3  4 -3  0  1 -1  0 -3 -4  0 -3 -3 -2  0 -1 -4 -3 -3  4  1 -1 -4
Z -1  0  0  1 -3  3  4 -2  0 -3 -3  1 -1 -3 -1  0 -1 -3 -2 -2  1  4 -1 -4
X  0 -1 -1 -1 -2 -1 -1 -1 -1 -1 -1 -1 -1 -1 -2  0  0 -2 -1 -1 -1 -1 -1 -4
* -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4  1
"""


def _build_blosum62() -> Dict[Tuple[str, str], int]:
    """Parse the BLOSUM62 matrix string into a lookup dict."""
    lines = [l for l in _BLOSUM62_RAW.strip().split("\n") if l.strip()]
    header = lines[0].split()
    matrix = {}
    for line in lines[1:]:
        parts = line.split()
        aa1 = parts[0]
        for j, aa2 in enumerate(header):
            matrix[(aa1, aa2)] = int(parts[j + 1])
    return matrix


BLOSUM62 = _build_blosum62()

GAP_OPEN = -11    # penalty for opening a new gap
GAP_EXTEND = -1   # penalty for extending an existing gap


@dataclass
class AlignmentResult:
    score: int
    identity_pct: float
    similarity_pct: float
    alignment_length: int
    gaps: int
    query_aligned: str      # seq1 with gap characters
    target_aligned: str     # seq2 with gap characters
    match_line: str         # | for match, : for similar, space for mismatch
    query_start: int
    query_end: int
    target_start: int
    target_end: int


def smith_waterman(
    seq1: str,
    seq2: str,
    max_length: int = 500,
) -> AlignmentResult:
    """
    Smith-Waterman local sequence alignment with affine gap penalties.

    Args:
        seq1: First amino acid sequence (query)
        seq2: Second amino acid sequence (target)
        max_length: Truncate sequences beyond this to keep O(mn) tractable
                    in a web request context. Full genome tools use heuristics
                    (BLAST seeds) for longer sequences.

    Returns:
        AlignmentResult with score, percent identity, aligned sequences
    """
    # Truncate for web request performance
    s1 = seq1[:max_length].upper()
    s2 = seq2[:max_length].upper()
    m, n = len(s1), len(s2)

    # Initialize DP matrices
    # Using int32 to save memory; scores won't overflow for typical proteins
    NEG_INF = -10000
    H = np.zeros((m + 1, n + 1), dtype=np.int32)
    E = np.full((m + 1, n + 1), NEG_INF, dtype=np.int32)  # gap in s1
    F = np.full((m + 1, n + 1), NEG_INF, dtype=np.int32)  # gap in s2

    best_score = 0
    best_i, best_j = 0, 0

    # Fill DP matrices
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            # Substitution score from BLOSUM62
            aa1, aa2 = s1[i - 1], s2[j - 1]
            sub = BLOSUM62.get((aa1, aa2), BLOSUM62.get(("X", "X"), -1))

            # Affine gap: extending existing gap is cheaper than opening new one
            E[i][j] = max(
                H[i][j - 1] + GAP_OPEN + GAP_EXTEND,
                E[i][j - 1] + GAP_EXTEND,
            )
            F[i][j] = max(
                H[i - 1][j] + GAP_OPEN + GAP_EXTEND,
                F[i - 1][j] + GAP_EXTEND,
            )
            H[i][j] = max(
                0,                          # local alignment: reset to 0
                H[i - 1][j - 1] + sub,     # match/mismatch
                E[i][j],                    # gap in seq1
                F[i][j],                    # gap in seq2
            )

            if H[i][j] > best_score:
                best_score = int(H[i][j])
                best_i, best_j = i, j

    # Traceback from best cell
    aligned1, aligned2 = [], []
    i, j = best_i, best_j
    end_i, end_j = i, j

    while i > 0 and j > 0 and H[i][j] > 0:
        score_here = int(H[i][j])
        aa1, aa2 = s1[i - 1], s2[j - 1]
        sub = BLOSUM62.get((aa1, aa2), BLOSUM62.get(("X", "X"), -1))

        if score_here == H[i - 1][j - 1] + sub:
            aligned1.append(aa1)
            aligned2.append(aa2)
            i -= 1
            j -= 1
        elif score_here == E[i][j]:
            aligned1.append("-")
            aligned2.append(aa2)
            j -= 1
        else:
            aligned1.append(aa1)
            aligned2.append("-")
            i -= 1

    aligned1 = "".join(reversed(aligned1))
    aligned2 = "".join(reversed(aligned2))
    start_i, start_j = i, j

    # Compute statistics
    alignment_length = len(aligned1)
    identical = sum(
        1 for a, b in zip(aligned1, aligned2)
        if a == b and a != "-"
    )
    similar = sum(
        1 for a, b in zip(aligned1, aligned2)
        if a != "-" and b != "-" and BLOSUM62.get((a, b), -99) > 0
    )
    gaps = sum(1 for a, b in zip(aligned1, aligned2) if a == "-" or b == "-")

    identity_pct = (identical / alignment_length * 100) if alignment_length > 0 else 0.0
    similarity_pct = (similar / alignment_length * 100) if alignment_length > 0 else 0.0

    # Build match line for display
    match_line = []
    for a, b in zip(aligned1, aligned2):
        if a == b and a != "-":
            match_line.append("|")
        elif a != "-" and b != "-" and BLOSUM62.get((a, b), -99) > 0:
            match_line.append(":")
        else:
            match_line.append(" ")
    match_line = "".join(match_line)

    return AlignmentResult(
        score=best_score,
        identity_pct=round(identity_pct, 2),
        similarity_pct=round(similarity_pct, 2),
        alignment_length=alignment_length,
        gaps=gaps,
        query_aligned=aligned1,
        target_aligned=aligned2,
        match_line=match_line,
        query_start=start_i + 1,     # 1-indexed for biologists
        query_end=end_i,
        target_start=start_j + 1,
        target_end=end_j,
    )

# Letroso word lists -- READ THIS BEFORE COMPARING WITH hello/ OR WITH THE GAME

`guess.txt` at each length is LETROSO'S OWN validation list (letroso.com's
`assets/all-en-<hash>.js`), cleaned to a-z.  A word we accept as a guess is a
word letroso accepts; a word letroso rejects, we reject.  This is the point of
the list -- it is NOT hello wordl's dictionary (that is `../hello/`, used by the
Wordle length-sweeps).

`mystery.txt` (the ANSWER list) IS OURS.  Letroso's real answer set is
server-side and unknown to us, so we model it from hello wordl's curated
`targets.json`, intersected with letroso's guess list.  Lengths 2 and 3 have no
hello answers and are built by our own frequency rule -- see each
`len<L>/mystery.txt.meta`.

source bundle: https://letroso.com/assets/all-en-CFYUaEb1.js
fetched: 2026-09-07

#!/usr/bin/env bash
# Build the preprint PDF. Plain-language header: run this after code/06 to code/09 have
# written the result files. Needs a TeX installation (pdflatex, bibtex). REVTeX 4.2 is
# bundled in revtex/ (LaTeX Project Public License), so nothing else is required.
set -euo pipefail
cd "$(dirname "$0")"
export TEXINPUTS=".:./revtex//:" BSTINPUTS=".:./revtex//:"
pdflatex -interaction=nonstopmode main.tex >/dev/null || true
bibtex main >/dev/null || true
pdflatex -interaction=nonstopmode main.tex >/dev/null || true
pdflatex -interaction=nonstopmode main.tex | grep -E "Warning|Error|Output written" | grep -v "Font shape" || true

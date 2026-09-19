#!/bin/sh
# Run from any directory; uses the repository venv and existing Pandoc/Typst.
set -eu
rfq_dir=$(CDPATH= cd "$(dirname "$0")/.." && pwd)
repo_dir=$(CDPATH= cd "$rfq_dir/../../.." && pwd)
cd "$repo_dir"
. venv/bin/activate
MPLBACKEND=Agg venv/bin/python "$rfq_dir/tools/render_figures.py"
cd "$rfq_dir"
pandoc TECHNICAL_DESCRIPTION.md --from=markdown --pdf-engine=typst \
    --template=tools/document.typst --lua-filter=tools/pagebreak.lua \
    --output=TECHNICAL_DESCRIPTION.pdf
cd internal
pandoc REVIEW.md --from=markdown --pdf-engine=typst \
    --template=../tools/document.typst --lua-filter=../tools/pagebreak.lua \
    --metadata=internal-review:true --output=REVIEW.pdf

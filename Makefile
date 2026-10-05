PY      ?= .venv/bin/python
PORT    ?= 8000

.PHONY: help setup refresh build drafts serve dev post note clean

help:            ## list targets
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-9s %s\n", $$1, $$2}'

setup:           ## create the virtualenv and install the two dependencies
	python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt

refresh:         ## full pipeline: pull GitHub data, merge, aggregate, check, render
	$(PY) -m pipeline.run

build:           ## render only, from the data already on disk (offline, fast)
	$(PY) -m pipeline.run --offline

drafts:          ## render including drafts and future-dated posts (local preview)
	$(PY) -m pipeline.run --offline --drafts

serve:           ## serve _site/ on http://localhost:8000 (PORT=... to change)
	$(PY) -m http.server $(PORT) --directory _site

dev: drafts serve  ## preview with drafts, then serve

post:            ## new article:  make post title="My title" [tags=spark,delta] [date=2026-10-05]
	$(PY) -m pipeline.new_post "$(title)" $(if $(tags),--tags "$(tags)") $(if $(date),--date $(date)) $(if $(note),--note)

note:            ## new daily note:  make note title="TIL ..." [tags=...]
	$(PY) -m pipeline.new_post "$(title)" --note $(if $(tags),--tags "$(tags)") $(if $(date),--date $(date))

clean:           ## remove build output and local bronze data
	rm -rf _site data/bronze

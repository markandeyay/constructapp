.PHONY: eval-capabilities eval-plasmid build-training-data demo derive-training-signal design e2e-test embed-corpus eval-all eval-check eval-generation eval-retrieval finetune-smoke generate-validation-gold ingest-addgene ingest-all ingest-curated ingest-genbank lint list-models parse-sample quality-report refresh-corpus register-model reprocess serve-api serve-local serve-web services-down setup shadow-eval spike-generation test validate-sample

PYTHON ?= python
MODE ?= dev
N ?=
ADDGENE_STALE_DAYS ?= 1
GENBANK_STALE_DAYS ?= 60
BATCH_SIZE ?= 100
FAKE ?= 0
TOP_K ?= 5
API_HOST ?= 127.0.0.1
API_PORT ?= 8000
CAPABILITY_GOLD ?= tests/gold
CAPABILITY_GOLD_OUT ?= data/eval/capabilities
CAPABILITY_GOLD_REQUIRE ?= 0
EVAL_GOLD ?= data/eval/retrieval_gold.jsonl
EVAL_OUT ?= data/eval/retrieval
TRAINING_OUT ?= data/training/phase2
TRAINING_SNAPSHOT ?=
GENERATION_GOLD ?= data/eval/generation_gold.jsonl
GENERATION_OUT ?= data/eval/generation
GENERATION_TOP_K ?= 1
VALIDATION_GOLD ?= data/eval/validation/validation_gold.jsonl
VALIDATION_OUT ?= data/eval/validation
GENERATION_GENERATOR ?= fake
CARBON_MAX_NEW_TOKENS ?= 4
FINETUNE_OUTPUT ?= packages/generation/models/finetune-smoke
MODEL_REGISTRY ?= data/models/registry.jsonl
MODEL_BASE_MODEL ?= HuggingFaceBio/Carbon-3B
MODEL_TRAINING_SNAPSHOT ?= $(TRAINING_SNAPSHOT)
MODEL_HYPERPARAMETERS_JSON ?= {}
MODEL_EVAL_SCORES_JSON ?= {}
MODEL_LICENSE_STATUS ?= unknown
MODEL_ROLLOUT_STATE ?= registered
MODEL_ARTIFACT_URI ?=
MODEL_TRAINING_COST ?=
PHASE5_TRAINING_OUT ?= data/training/phase5
EVAL_DASHBOARD_OUT ?= data/eval
EVAL_RETRIEVAL_TOP5_DROP ?= 0.05
EVAL_RETRIEVAL_MRR_DROP ?= 0.10
EVAL_VALIDATION_ACCURACY_DROP ?= 0.02
EVAL_COMPLETE_ANNOTATION_DROP ?= 10
EVAL_PARSE_ERROR_INCREASE ?= 0

setup:
	$(PYTHON) -m pip install -r requirements.txt
	powershell -NoProfile -ExecutionPolicy Bypass -Command "if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }"
	docker compose up -d

test:
	$(PYTHON) scripts/check_services.py
	$(PYTHON) -m pytest

e2e-test:
	npm --prefix apps/web run test:e2e -- --config=playwright.fullstack.config.ts

demo: e2e-test

lint:
	$(PYTHON) -m ruff check .

ingest-all:
	@echo "TODO: run all Phase 0 ingestion jobs"

ingest-addgene:
	$(PYTHON) -m packages.data_pipeline.ingest.addgene --mode $(MODE) $(if $(N),--limit $(N),) --stale-days $(ADDGENE_STALE_DAYS)

ingest-genbank:
	$(PYTHON) -m packages.data_pipeline.ingest.genbank --mode $(MODE) $(if $(N),--limit $(N),) --stale-days $(GENBANK_STALE_DAYS)

parse-sample:
	$(PYTHON) scripts/parse_sample.py $(if $(N),--limit $(N),) $(if $(SOURCE),--source $(SOURCE),)

ingest-curated:
	$(PYTHON) -m packages.data_pipeline.ingest.curated_seed

quality-report:
	$(PYTHON) -m packages.data_pipeline.quality_report

reprocess:
	$(PYTHON) -m packages.data_pipeline.reprocess --mode $(MODE) $(if $(BEFORE),--before $(BEFORE),) $(if $(SOURCE),--source $(SOURCE),) $(if $(PATTERN),--pattern $(PATTERN),) --batch-size $(BATCH_SIZE)

refresh-corpus:
	$(PYTHON) -m packages.data_pipeline.refresh_corpus --stale-days $(GENBANK_STALE_DAYS) $(if $(N),--limit $(N),) --batch-size $(BATCH_SIZE)

eval-retrieval:
	$(PYTHON) -m packages.retrieval.eval --gold-path $(EVAL_GOLD) --output-dir $(EVAL_OUT) --top-k $(TOP_K) $(if $(filter 1 true TRUE yes YES,$(FAKE)),--fake-embedder,) $(if $(filter offline OFFLINE,$(MODE)),--local-files-only,)

embed-corpus:
	$(PYTHON) -m packages.retrieval.embed_corpus --batch-size $(BATCH_SIZE) $(if $(N),--limit $(N),) $(if $(filter 1 true TRUE yes YES,$(FAKE)),--fake,) $(if $(filter offline OFFLINE,$(MODE)),--local-files-only,)

design:
	$(PYTHON) -m packages.retrieval.pipeline --text "$(TEXT)" --k $(TOP_K) $(if $(filter 1 true TRUE yes YES,$(FAKE)),--fake-embedder,) $(if $(filter offline OFFLINE,$(MODE)),--local-files-only,)

spike-generation:
	$(PYTHON) -m packages.generation.spike --text "$(TEXT)" $(if $(filter 1 true TRUE yes YES,$(FAKE)),--fake-embedder,) $(if $(filter offline OFFLINE,$(MODE)),--local-files-only,)

build-training-data:
	$(PYTHON) -m packages.generation.training_data --output-root $(TRAINING_OUT) $(if $(TRAINING_SNAPSHOT),--snapshot-id $(TRAINING_SNAPSHOT),)

eval-generation:
	$(PYTHON) -m packages.generation.eval --gold-path $(GENERATION_GOLD) --output-dir $(GENERATION_OUT) --top-k $(GENERATION_TOP_K) --generator $(GENERATION_GENERATOR) --carbon-max-new-tokens $(CARBON_MAX_NEW_TOKENS) $(if $(filter 1 true TRUE yes YES,$(FAKE)),--fake-embedder,) $(if $(filter offline OFFLINE,$(MODE)),--local-files-only,)

# Capability gold sets (section 9). Pure deterministic validators, no database,
# no network. Runs on its own so its verdict is never hidden by a corpus failure.
eval-capabilities:
	$(PYTHON) -m tests.gold.runner --gold-root $(CAPABILITY_GOLD) --output-dir $(CAPABILITY_GOLD_OUT) $(if $(filter 1 true TRUE yes YES,$(CAPABILITY_GOLD_REQUIRE)),--require-cases,)

# The plasmid pipeline evaluation. Needs a populated Postgres corpus
# (retrieval, generation) and fails loudly when the corpus is absent.
eval-plasmid:
	"$(MAKE)" eval-retrieval
	"$(MAKE)" eval-generation GENERATION_GENERATOR=fake
	"$(MAKE)" validate-sample MODE=gold
	"$(MAKE)" quality-report
	$(PYTHON) -m packages.eval.continuous dashboard --output-dir $(EVAL_DASHBOARD_OUT) --retrieval-top5-drop $(EVAL_RETRIEVAL_TOP5_DROP) --retrieval-mrr-drop $(EVAL_RETRIEVAL_MRR_DROP) --validation-accuracy-drop $(EVAL_VALIDATION_ACCURACY_DROP) --complete-annotation-drop $(EVAL_COMPLETE_ANNOTATION_DROP) --parse-error-increase $(EVAL_PARSE_ERROR_INCREASE)

# Every capability, every case. Both halves always run so each verdict is visible;
# the target fails if either half failed.
eval-all:
	@cap=0; pla=0; \
	"$(MAKE)" eval-capabilities || cap=1; \
	"$(MAKE)" eval-plasmid || pla=1; \
	echo ""; echo "eval-all summary:"; \
	if [ $$cap -eq 0 ]; then echo "  capability gold sets (no database): PASS"; else echo "  capability gold sets (no database): FAIL"; fi; \
	if [ $$pla -eq 0 ]; then echo "  plasmid pipeline (needs corpus):    PASS"; else echo "  plasmid pipeline (needs corpus):    FAIL (see output above)"; fi; \
	[ $$cap -eq 0 ] && [ $$pla -eq 0 ]

# Fails the build on any regression. The capability gold sets are checked
# independently of the corpus; a corpus failure is reported, never hidden, and
# the regression thresholds are not evaluated against missing results.
eval-check:
	@cap=0; pla=0; reg=0; \
	"$(MAKE)" eval-capabilities || cap=1; \
	"$(MAKE)" eval-plasmid || pla=1; \
	if [ $$pla -eq 0 ]; then \
	$(PYTHON) -m packages.eval.continuous check --output-dir $(EVAL_DASHBOARD_OUT) --retrieval-top5-drop $(EVAL_RETRIEVAL_TOP5_DROP) --retrieval-mrr-drop $(EVAL_RETRIEVAL_MRR_DROP) --validation-accuracy-drop $(EVAL_VALIDATION_ACCURACY_DROP) --complete-annotation-drop $(EVAL_COMPLETE_ANNOTATION_DROP) --parse-error-increase $(EVAL_PARSE_ERROR_INCREASE) || reg=1; \
	fi; \
	echo ""; echo "eval-check summary:"; \
	if [ $$cap -eq 0 ]; then echo "  capability gold sets (no database): PASS"; else echo "  capability gold sets (no database): FAIL"; fi; \
	if [ $$pla -eq 0 ]; then echo "  plasmid pipeline (needs corpus):    PASS"; else echo "  plasmid pipeline (needs corpus):    FAIL, regression check NOT run (see output above)"; fi; \
	if [ $$pla -eq 0 ]; then if [ $$reg -eq 0 ]; then echo "  regression thresholds:              PASS"; else echo "  regression thresholds:              FAIL"; fi; fi; \
	[ $$cap -eq 0 ] && [ $$pla -eq 0 ] && [ $$reg -eq 0 ]

shadow-eval:
	$(PYTHON) -m packages.generation.rollout_eval --gold data/eval/retrieval_gold.jsonl --limit $(or $(N),20) --output-dir data/eval/shadow

finetune-smoke:
	$(PYTHON) -m packages.generation.finetune --smoke --output-dir $(FINETUNE_OUTPUT) --max-train-examples 5 --max-eval-examples 2 --max-steps 1 --max-length 96

register-model:
	$(PYTHON) -m packages.generation.registry register --registry-path $(MODEL_REGISTRY) --version "$(VERSION)" --base-model "$(MODEL_BASE_MODEL)" --training-data-snapshot-id "$(MODEL_TRAINING_SNAPSHOT)" --hyperparameters-json "$(MODEL_HYPERPARAMETERS_JSON)" --eval-scores-json "$(MODEL_EVAL_SCORES_JSON)" --license-status "$(MODEL_LICENSE_STATUS)" --rollout-state "$(MODEL_ROLLOUT_STATE)" $(if $(MODEL_ARTIFACT_URI),--artifact-uri "$(MODEL_ARTIFACT_URI)",) $(if $(MODEL_TRAINING_COST),--training-cost $(MODEL_TRAINING_COST),)

list-models:
	$(PYTHON) -m packages.generation.registry list --registry-path $(MODEL_REGISTRY)

derive-training-signal:
	$(PYTHON) -m packages.feedback.training_signal --registry-path $(MODEL_REGISTRY) --output-dir $(PHASE5_TRAINING_OUT) $(if $(N),--limit $(N),)

validate-sample:
	$(if $(filter gold GOLD,$(MODE)),$(PYTHON) -m packages.validation.eval --curated --output-dir $(VALIDATION_OUT),$(PYTHON) -m packages.validation.engine $(if $(N),--limit $(N),))

generate-validation-gold:
	$(PYTHON) -m packages.validation.gold --gold-path $(VALIDATION_GOLD) --doc-path $(VALIDATION_OUT)/gold_set_construction.md

serve-api:
	$(PYTHON) -m uvicorn services.api.app:app --host $(API_HOST) --port $(API_PORT)

serve-local:
	$(PYTHON) -m uvicorn --factory services.api.local_app:build_local_app --host $(API_HOST) --port $(API_PORT)

serve-web:
	cd apps/web && npm run dev

services-down:
	docker compose down

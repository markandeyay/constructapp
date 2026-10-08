# Construct demo runbook

For a presenter following this cold. Everything below was walked in a real
browser against the local stack on 2026-10-08, and the numbers quoted are the
ones the app showed. Evidence screenshots are in `docs/demo_evidence/`.

The product has four capabilities that exist: plasmids, AAV vectors, assembly
and primers, and guide RNAs. Everything else is on the roadmap.

## READ THIS FIRST: the database port is 55432, not 5432

Postgres runs on host port **55432**. A native PostgreSQL 18 Windows service on
this machine owns 5432, so the container was moved. The setting lives in the
gitignored `.env` (`POSTGRES_PORT=55432` and a `DATABASE_URL` ending in
`localhost:55432/plasmid_design`).

If anyone regenerates `.env` from `.env.example`, they get 5432 again, and the
plasmid flow and the corpus fail with an authentication error because they are
talking to the wrong Postgres. Do not run `make setup` or copy `.env.example`
over `.env` before the demo. If you must, set the port back to 55432 afterwards.
`python scripts/check_services.py` catches this: it must print four `[OK]` lines.

## 1. Pre-flight, Saturday morning (spec section 15.2)

Run these in order from the repo root. Each line says what healthy looks like.

```powershell
docker compose up -d
```
Healthy: postgres, redis and minio containers show as started or running.

```powershell
python scripts/check_services.py
```
Healthy: four lines, `[OK] docker compose`, `[OK] postgres + pgvector`,
`[OK] minio`, `[OK] redis`, and exit code 0.

```powershell
make test
```
Healthy: it runs the service check and then the whole pytest suite, and ends
green with exit code 0. Do this before you leave the house.

```powershell
make serve-local
```
Leave it running in its own terminal. Healthy: uvicorn reports it is running on
`http://127.0.0.1:8000`. Use `serve-local`, not `serve-api`: the default
scaffold queues plasmid jobs without finishing them.

```powershell
make serve-web
```
Leave it running in a second terminal. Healthy: Next.js reports `Ready` on
`http://127.0.0.1:3000`.

Then open `http://127.0.0.1:3000` and run each of the four capabilities once
using the inputs in section 2. The status line at the bottom of the page may say
"Offline"; that refers to the outcome feedback service and does not affect the
four beats. Keep browser zoom at 100%.

Optional deterministic check, for confidence rather than for the stage:
`make demo` runs the full-stack Playwright flow against a fixture API. It starts
its own servers on ports 8000 and 3000, so stop `serve-local` and `serve-web`
first.

## 2. The script (spec section 15.3)

The order builds from legible to impressive. The four capability tabs sit at the
top of the right-hand Conversation panel: Plasmid, AAV vector, Assembly and
primers, Guide RNA.

### Beat 1. Plasmid, about 30 seconds

Stay on the Plasmid tab. Type into the Experimental goal box:

```text
a yeast shuttle vector with URA3 selection and centromere maintenance
```

Click Design. After a few seconds you get a retrieved template (pRS416, score
0.854), a circular map of 4,898 bp with 7 features, and a validation report.

Say: "This is the existing flow. It retrieves a real template instead of
inventing a backbone, and the checks run separately from generation."

Be ready for this: on 2026-10-08 the overall verdict for this prompt was FAIL,
not PASS. The report said a 100 bp window has extreme GC content (11 percent),
and that the lac promoter region is not compatible with the requested yeast
host. That is the engine doing its job on the retrieved record, and it is a fair
thing to say out loud: "It does not hide a failing check behind a fluent
answer." If you would rather open on a green result, try the backup prompts in
section 5 before the demo and keep whichever one you like.

### Beat 2. AAV, over the limit, then fixed. This is the moment.

Click the AAV vector tab. Fill the form with:

* Transgene name: `lacZ`
* Transgene coding sequence: paste the entire contents of
  `docs/demo_assets/transgene_lacZ_JF300162.1.txt` (3,075 bp, one line)
* Target tissue: Ubiquitous
* Promoter: CAG promoter (1,639 bp)
* PolyA signal: Bovine growth hormone polyadenylation signal
* Self-complementary: unchecked
* **Include WPRE if it fits: leave it UNCHECKED, or the numbers below change.**
  It is checked by default. With it checked the "fixed" cassette picks up a 589
  bp WPRE and lands at 4,391 bp, not 3,802 bp. Click the checkbox with the
  mouse so you can see it is empty.

The transgene must be pasted. No retrieval resolver for transgenes exists, so
the app cannot look up a gene by name. The generator raises rather than
inventing a sequence, which is the correct behavior.

Click Compose cassette. Expected, measured:

* Cassette **5,229 bp**, overall **FAIL**, Packaging limit FAIL.
* 529 bp over the 4,700 bp target, 329 bp over the 4,900 bp soft limit, and 29
  bp past the 5,200 bp hard ceiling.
* The message names the fix itself: replace CAG with EFS, saving 1,427 bp.
* The length budget table shows the running total going red at the transgene.

Say: "That is a real, expensive mistake, caught before anyone spent money, and the
fix is computed. Beta-galactosidase is the classic oversized AAV cargo."

Now change Promoter to `EFS, short EF-1 alpha core promoter (212 bp)` and click
Compose cassette again. Expected, measured:

* Cassette **3,802 bp**, Packaging limit **PASS**, overall **WARN**.
* Both ITRs matched, orientation correct, order correct, 14 checks reported.

The overall is WARN, not PASS, and you should say why before anyone asks. One
advisory remains, `Kozak initiation context`, Tier B. It is a property of the
real gene: lacZ begins ATGACC, so the base after the start codon is A where G is
preferred. The report gives the fix, which is to insert a GCCRCC prefix right
before the ATG.

One sentence to say: "It lands on a warning, not a pass, because the real lacZ
gene has a weak start context, and the report tells me exactly how to fix it,
which is the point: a warning with an explanation is the product."

Request bodies, if you ever drive the API directly (`POST /v1/aav/design`):
before `{"transgene_name": "lacZ", "transgene_sequence": "<file contents>",
"target_tissue": "ubiquitous", "promoter_preference": "promoter.cag",
"include_wpre": false, "polya_preference": "polya.bgh"}`, then the same body with
`"promoter_preference": "promoter.efs"` for the after state.

### Beat 3. Assembly, about 30 seconds

Click the Assembly and primers tab. Strategy: Gibson. Leave Target primer Tm
empty. There are two fragment cards; fill them in this order.

Be precise about what this beat is. There is no automatic hand-off from the AAV
result to this tab, so you paste fragments. And two arbitrary sequence slices do
not make a clean Gibson pair: an arbitrary pair of promoter slices returns
overall FAIL, which is correct behavior. The pair below was chosen and verified
to assemble cleanly. Both fragments are plus strand slices of real promoter
records.

Fragment 1: Name `frag_a`, Role Insert, Source
`GenBank KU341333.1, CBh promoter (part promoter.cbh), plus strand offset 100, 150 bp`,
Sequence:

```text
CAATGGGTGGAGTATTTACGGTAAACTGCCCACTTGGCAGTACATCAAGTGTATCATATGCCAAGTACGCCCCCTATTGACGTCAATGACGGTAAATGGCCCGCCTGGCATTGTGCCCAGTACATGACCTTATGGGACTTTCCTACTTGG
```

Fragment 2: Name `frag_b`, Role Insert, Source
`GenBank AF396260.1, CMV promoter (part promoter.cmv), plus strand offset 410, 180 bp`,
Sequence:

```text
ATAGCGGTTTGACTCACGGGGATTTCCAAGTCTCCACCCCATTGACGTCAATGGGAGTTTGTTTTGCACCAAAATCAACGGGACTTTCCAAAATGTCGTAACAACTCCGCCCCATTGACGCAAATGGGCGGTAGGCGTGTACGGTGGGAGGTCTATATAAGCAGAGCTCGTTTAGTGAAC
```

Click Design primers. Expected, measured: assembly junction map with a 20 bp
homology arm, `frag_a` as a 170 bp amplicon and `frag_b` as a 200 bp amplicon,
4 primers, overall **PASS**, **15 checks**, and an Order table CSV and Junction
map export.

Say: "And here is what to order, and what to do at the bench on Monday."

### Beat 4. Guide RNA, 20 seconds, only if time

Click the Guide RNA tab. Target name `PUC19_BLA`. Target sequence: paste
`docs/demo_assets/grna_target_bla_pUC19.txt` (950 bp, the beta-lactamase region
of pUC19, the same record used by gold case `grna.good.a1.spcas9_forward_bla_guide`).
Nuclease SpCas9, edit intent Knockout, off-target search space "The target and
delivery construct only". Click Rank guides.

Expected, measured: "10 of 216 enumerated guides shown", overall PASS with 10
checks, a Guide table TSV and an Oligo order TSV, and a banner reading:

> Off-target search covered the target sequence only, 950 bp in total across 1
> sequence. No delivery construct sequence was supplied, so self-targeting of the
> delivery construct was not searched. This is not a genome-wide search.

Say the limitation yourself, before being asked: "It searched only the target I
gave it, and it says so in the report. It is not genome-wide."

## 3. Questions to have answers ready for (spec section 15.4)

* **"Isn't this just ChatGPT with a biology prompt?"** The checking is a rules
  engine, not a model. The validation engine follows fixed rules: the same design
  produces the same verdict, and every verdict cites its threshold. Open the
  report and show the Observed and Threshold lines. The biology is not settled
  science, and we do not claim it is.
* **"Where does the packaging limit come from?"** It is a band, configurable and
  cited: a 4,700 bp target, a 4,900 bp soft limit and a 5,200 bp hard ceiling.
  Labs disagree about the practical ceiling, which is why it is a band.
* **"What is your off-target search covering?"** Only the sequence you supply,
  plus the delivery construct if you give one. Not genome-wide. Say it before
  being pushed, and point at the banner.
* **"What does 100 percent accuracy mean?" or "How accurate is it?"** Never say
  100 percent accurate. Give counts and say "curated": it gets 91 of 91 on the
  curated capability gold set, across three capability types, 46 known-good
  designs and 45 known-bad designs, assembled by us. The plasmid gold set is
  separate, 36 known-good and 52 known-bad, and is quoted on its own because an
  older harness measures it that does not assert the named check. A curated gold
  set is a regression test, not proof of real-world accuracy.
* **"Aren't you competing with Benchling?"** Benchling is where designs are
  recorded and managed. This generates and validates them.
* **"Where does the AAV transgene come from?"** You paste it. There is no gene
  lookup yet, and the generator refuses to invent a sequence. The demo payload is
  a real beta-galactosidase coding sequence, GenBank JF300162.1.
* **"Is the sequence safe to synthesize?"** For what is implemented on sequence
  screening, see `progress/WP-08.md`.
* **"Can it do CAR-T, antibodies, circuits, pathways?"** Not built yet. Here is
  what we have: plasmids, AAV vectors, assembly and primers, guide RNAs. The rest
  is on our roadmap.

## 4. If it breaks

* **Docker engine wedged.** Symptoms: `docker compose up -d` hangs or errors,
  `scripts/check_services.py` fails on every line, Docker Desktop looks stuck.
  This happened during the build. `docker desktop restart` fixed it and the corpus
  survived the restart. Then rerun `docker compose up -d` and
  `python scripts/check_services.py`.
* **Port 55432 trap.** Plasmid beat fails with an authentication error, or the
  corpus looks empty. `.env` was regenerated and Postgres is being reached on
  5432, which belongs to the native Windows PostgreSQL service. Set
  `POSTGRES_PORT=55432` and a `DATABASE_URL` ending `localhost:55432/plasmid_design`.
  Restart `make serve-local`.
* **The page loses your input.** Next.js dev mode can reload the page, and the
  form state is gone. This happened once in the browser walk. Re-enter the form.
  If it keeps happening, it is the dev server restarting: check the `serve-web`
  terminal.
* **Numbers differ from this script.** If the AAV after state shows 4,391 bp,
  the WPRE box was checked. Untick it and compose again.
* **Plasmid beat is slow or fails and you are out of time.** Skip it. The AAV
  beat does not touch the database. Beats 2 to 4 run without Postgres.
* **Last resort.** `make demo` is the deterministic verification path against the
  fixture API. It is a test, not a live demo of the real engine.

## 5. Backup prompts for the plasmid beat

Use these if the primary prompt does not retrieve cleanly.

```text
a bacterial expression vector for E. coli with ampicillin selection and GFP reporter readout
```

```text
a mammalian GFP reporter plasmid for expression analysis in cultured cells
```

```text
build a GFP reporter
```

## 6. Claims

Make these claims:

* "Four capabilities exist: plasmids, AAV vectors, assembly and primers, guide
  RNAs. The rest is on our roadmap."
* "The validation engine follows fixed rules. The same design produces the same
  verdict, and every verdict cites its threshold."
* "On the curated capability gold set it gets 91 of 91, 46 known-good and 45
  known-bad, across three capability types."
* "Retrieval is grounded in indexed plasmid records and templates."
* "Every guide RNA table states exactly what was searched for off-targets, and
  says it is not genome-wide."
* "The frontend supports the four capabilities with map or table views and
  exports: GenBank and FASTA for plasmid and AAV, order table and junction map
  for assembly, guide table and oligo order for guide RNA."

Avoid these claims:

* "100 percent accurate" or any accuracy figure without the word curated and the
  counts.
* "Provably correct", "guaranteed valid", or "guaranteed synthesis ready".
* "The system is production deployed." It runs locally.
* "The off-target search is genome-wide." It covers only the supplied sequence
  set.
* "We cover CAR-T, antibodies, circuits or pathways", or any list of capability
  types beyond the four. Say not built yet.
* "You can look up any transgene by name." You paste the sequence.
* "The AAV design flows automatically into assembly." You paste the fragments;
  there is no hand-off yet.
* "Synthesis-provider ordering is complete." The tool produces order tables and
  oligo order files; it does not place orders.
* "The model learns automatically from every reported outcome." Outcome capture
  exists for plasmid designs; automated retraining and promotion are not built.
* "Auth and deployed hosting are done." They are not.

## 7. Audience notes

Investors: lead with beat 2. A failure caught before money was spent, and the fix
computed, needs no biology background. Say the Kozak warning yourself.

Scientific collaborators: lead with auditability, the Observed and Threshold
lines, the cited constants, and the off-target statement. Ask which packaging
ceiling they use in practice.

Technical collaborators: the engine is rule based and deterministic, each
capability has its own validator package and a gold set, and the capability
endpoints are pure functions of the request body.

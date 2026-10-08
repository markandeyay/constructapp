import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import type { AavDesignResponse, AssemblyDesignResponse, GrnaDesignResponse } from "../lib/capabilities";

// The fixtures in ./fixtures are real responses captured from the AAV, assembly and
// guide RNA endpoints, so these checks run against the payload shapes the API
// produces. Every route is mocked, which keeps the suite deterministic.

function fixture<T>(name: string): T {
  return JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", name), "utf8")) as T;
}

const API = "http://127.0.0.1:8000";

async function mockCommon(page: Page) {
  await page.route(`${API}/v1/users/me/pending-outcome-prompts`, (route) => route.fulfill({ json: { prompts: [] } }));
  await page.route(`${API}/v1/aav/parts`, (route) => route.fulfill({ json: fixture<unknown>("aav_parts.json") }));
  await page.route(`${API}/v1/grna/reference`, (route) => route.fulfill({ json: fixture<unknown>("grna_ref.json") }));
}

const TARGET =
  "ACGTTGCAATTTCGGCACTAGGTACCAGGTTACGAACCGGTTAAGGCCTTAAGGCCGGTTAACCGGACGTACGTAGCTGACTGACGATCGGATCCTTAGGCATCAGCTAGCTAGGACTGACTGGCATCAGCATCAGGTACGTACGTAAGGCCTTAAGGACGTCTGACTGACGTACGTACGGTTACGTACGATCGATCG";

test("the capability selector offers the four capabilities and swaps the request form", async ({ page }) => {
  await mockCommon(page);
  await page.goto("/");

  const group = page.getByRole("radiogroup", { name: "Capability" });
  await expect(group.getByRole("radio")).toHaveText(["Plasmid", "AAV vector", "Assembly and primers", "Guide RNA"]);
  await expect(group.getByRole("radio", { name: "Plasmid" })).toHaveAttribute("aria-checked", "true");
  await expect(page.getByLabel("Experimental goal")).toBeVisible();

  await group.getByRole("radio", { name: "AAV vector" }).click();
  await expect(page.getByLabel("Transgene coding sequence")).toBeVisible();
  await expect(page.getByLabel("Experimental goal")).toBeHidden();
  await expect(page.getByRole("heading", { name: "AAV cassette map" })).toBeVisible();

  await group.getByRole("radio", { name: "Assembly and primers" }).click();
  await expect(page.getByLabel("Strategy")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Assembly junction map" })).toBeVisible();

  await group.getByRole("radio", { name: "Guide RNA" }).click();
  await expect(page.getByLabel("Target sequence")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Guide RNA targets" })).toBeVisible();

  await group.getByRole("radio", { name: "Plasmid" }).click();
  await expect(page.getByLabel("Experimental goal")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Plasmid map" })).toBeVisible();
});

test("an over-limit AAV cassette is drawn linear, with the length budget and a computed fix", async ({ page }) => {
  await mockCommon(page);
  const over = fixture<AavDesignResponse>("aav_over.json");
  const fixed = fixture<AavDesignResponse>("aav_fixed.json");
  const bodies: Record<string, unknown>[] = [];
  await page.route(`${API}/v1/aav/design`, async (route) => {
    const body = route.request().postDataJSON() as Record<string, unknown>;
    bodies.push(body);
    await route.fulfill({ json: bodies.length === 1 ? over : fixed });
  });

  await page.goto("/");
  await page.getByRole("radio", { name: "AAV vector" }).click();
  await page.getByLabel("Transgene name").fill("TG");
  await page.getByLabel("Transgene coding sequence").fill(">TG\nATGAAATAA");
  await page.getByLabel("Promoter").selectOption("promoter.cag");
  await page.getByRole("button", { name: "Compose cassette" }).click();

  expect(bodies[0]).toMatchObject({ transgene_name: "TG", transgene_sequence: "ATGAAATAA", promoter_preference: "promoter.cag" });

  // The map is linear, never the circular plasmid renderer.
  const map = page.getByTestId("aav-linear-map");
  await expect(map).toBeVisible();
  await expect(map).toHaveAttribute("data-topology", "linear");
  await expect(page.getByTestId("topology-badge")).toHaveText("Linear");
  await expect(page.getByTestId("seqviz-map")).toHaveCount(0);
  await expect(map.getByTestId("aav-element")).toHaveCount(over.length_budget.rows.length);
  await expect(map.getByTestId("aav-over-target")).toBeVisible();

  // Elements are drawn to scale: bar widths follow element lengths.
  const widths = await map.getByTestId("aav-element").evaluateAll((nodes) =>
    nodes.map((node) => (node as SVGPolygonElement).getBBox().width)
  );
  const lengths: number[] = over.length_budget.rows.map((row) => row.length_bp);
  const cds = lengths.indexOf(Math.max(...lengths));
  const promoter = lengths.indexOf(over.length_budget.rows.find((row) => row.role === "promoter")!.length_bp);
  expect(widths[cds] / widths[promoter]).toBeCloseTo(lengths[cds] / lengths[promoter], 1);

  // The length budget table: element, bp, running total, headroom.
  const table = page.getByTestId("length-budget");
  await expect(table.getByRole("heading", { name: "Length budget" })).toBeVisible();
  await expect(table.getByTestId("budget-row")).toHaveCount(over.length_budget.rows.length);
  await expect(table.getByTestId("budget-total")).toHaveText(over.length_budget.total_bp.toLocaleString());
  await expect(table.getByTestId("budget-headroom")).toHaveText(`${Math.abs(over.length_budget.headroom_bp).toLocaleString()} over`);

  // The validation report shows the failure with observed, threshold and citation.
  const packaging = page.getByTestId("validation-row").filter({ hasText: "Packaging limit" }).first();
  await expect(packaging).toHaveAttribute("data-severity", "FAIL");
  await expect(packaging.getByText("Observed:")).toBeVisible();
  await expect(packaging.getByText("Threshold:")).toBeVisible();
  await packaging.getByText("Citation").click();
  await expect(packaging.getByText(over.report.checks[0].citation ?? "")).toBeVisible();

  // The computed substitution can be applied, and the cassette is recomposed.
  await page.getByTestId("remediation-plan").first().getByRole("button", { name: "Apply this change and recompose" }).click();
  await expect(table.getByTestId("budget-total")).toHaveText(fixed.length_budget.total_bp.toLocaleString());
  expect(bodies[1]).toMatchObject({ promoter_preference: "promoter.efs" });

  // Exports reuse the artifacts the API produced.
  const genbank = page.waitForEvent("download");
  await page.getByRole("button", { name: "GenBank" }).click();
  expect((await genbank).suggestedFilename()).toBe(`${fixed.design_id}.gb`);

  // The AAV elements can seed the assembly request.
  await page.getByRole("button", { name: "Use these elements as assembly fragments" }).click();
  await expect(page.getByRole("radio", { name: "Assembly and primers" })).toHaveAttribute("aria-checked", "true");
  await expect(page.getByRole("listitem", { name: /^Fragment \d+$/ })).toHaveCount(fixed.design.elements.length);
});

test("assembly shows the junction map, a copyable order table and a CSV export", async ({ page }) => {
  await mockCommon(page);
  const design = fixture<AssemblyDesignResponse>("asm_design.json");
  let body: Record<string, unknown> | null = null;
  await page.route(`${API}/v1/assembly/design`, async (route) => {
    body = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ json: design });
  });

  await page.goto("/");
  await page.getByRole("radio", { name: "Assembly and primers" }).click();
  const fragments = page.getByRole("listitem", { name: /^Fragment \d+$/ });
  for (const [index, name] of ["frag_a", "frag_b"].entries()) {
    const fragment = fragments.nth(index);
    await fragment.getByLabel("Name").fill(name);
    await fragment.getByLabel("Source").fill(`test source ${name}`);
    await fragment.getByLabel("Sequence").fill("ACGT".repeat(30));
  }
  await page.getByRole("button", { name: "Design primers" }).click();

  expect(body).toMatchObject({ strategy: "gibson" });
  expect(body!.fragments as unknown[]).toHaveLength(2);

  await expect(page.getByTestId("junction-map")).toBeVisible();
  await expect(page.getByTestId("junction-link")).toHaveCount(design.outputs.junction_map.length - 1);
  await expect(page.getByTestId("junction-closing")).toBeVisible();
  await expect(page.getByTestId("junction-detail")).toHaveCount(design.outputs.junction_map.length);

  const rows = page.getByTestId("order-row");
  await expect(rows).toHaveCount(design.outputs.order_table.length);
  await expect(rows.first()).toContainText(design.outputs.order_table[0].sequence_5_to_3);
  await expect(page.getByRole("button", { name: "Copy table" })).toBeVisible();

  const csv = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV" }).click();
  const download = await csv;
  expect(download.suggestedFilename()).toBe(`${design.design_id}-order-table.csv`);
  const downloadPath = await download.path();
  expect(fs.readFileSync(downloadPath, "utf8")).toBe(design.outputs.order_table_csv);

  await expect(page.getByRole("region", { name: "Protocol" })).toContainText(String(design.outputs.protocol.annealing_temperature_c));
  await expect(page.getByRole("region", { name: "Validation report" }).first()).toBeVisible();
});

test("guide RNA states the searched space verbatim, marks both strands and keeps UNKNOWN apart from PASS", async ({ page }) => {
  await mockCommon(page);
  const design = fixture<GrnaDesignResponse>("grna_design.json");
  const statement: string = design.off_target_space_statement;
  let body: Record<string, unknown> | null = null;
  await page.route(`${API}/v1/grna/design`, async (route) => {
    body = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ json: design });
  });

  await page.goto("/");
  await page.getByRole("radio", { name: "Guide RNA" }).click();
  await page.getByLabel("Target name").fill("API_TARGET");
  await page.getByLabel("Target sequence").fill(TARGET);
  await page.getByRole("button", { name: "Rank guides" }).click();

  expect(body).toMatchObject({ target_name: "API_TARGET", nuclease: "SpCas9", off_target_space: { scope: "construct_only" } });

  // Section 10.4: the statement is rendered character for character as the API sent it.
  const statements = page.getByTestId("off-target-statement");
  await expect(statements.first()).toBeVisible();
  expect(await statements.first().textContent()).toBe(statement);
  // It is also in the chat thread, where the ranked guides are announced.
  await expect(page.getByText(statement, { exact: false }).first()).toBeVisible();

  // Guides are marked on both strands of the target sequence.
  const bars = page.getByTestId("guide-bar");
  const forward = design.result.guides_returned.filter((guide) => guide.strand === 1).length;
  const reverse = design.result.guides_returned.filter((guide) => guide.strand === -1).length;
  expect(forward).toBeGreaterThan(0);
  expect(reverse).toBeGreaterThan(0);
  // A guide that crosses a line break is drawn on both lines, so count distinct guides.
  const drawn = await bars.evaluateAll((nodes) =>
    nodes.map((node) => `${node.getAttribute("data-strand")}:${node.getAttribute("data-guide-id")}`)
  );
  expect(new Set(drawn.filter((item) => item.startsWith("forward:"))).size).toBe(forward);
  expect(new Set(drawn.filter((item) => item.startsWith("reverse:"))).size).toBe(reverse);

  // The ranked table names the model and says the score is a prediction.
  const guideRows = page.getByTestId("guide-row");
  await expect(guideRows).toHaveCount(design.result.guides_returned.length);
  const first = design.result.guides_returned[0];
  await expect(guideRows.first().getByTestId("on-target-cell")).toContainText(first.on_target.model_name);
  await expect(guideRows.first().getByTestId("on-target-cell")).toContainText("not a measurement");
  await expect(page.getByTestId("score-reference")).toContainText("Rule Set 1 sgRNA on-target activity model");

  // Per-guide reasoning expands, and repeats the statement verbatim.
  await guideRows.first().getByRole("button", { name: "Show reasoning" }).click();
  const detail = page.getByTestId("guide-detail");
  await expect(detail).toBeVisible();
  await expect(detail).toContainText(first.reasoning[0]);
  const all = await statements.allTextContents();
  expect(all.length).toBeGreaterThanOrEqual(2);
  for (const text of all) {
    expect(text).toBe(statement);
  }

  // UNKNOWN rows are visibly different from PASS rows.
  const unknown = detail.locator('[data-testid="validation-row"][data-severity="UNKNOWN"]').first();
  const pass = detail.locator('[data-testid="validation-row"][data-severity="PASS"]').first();
  await expect(unknown).toBeVisible();
  await expect(pass).toBeVisible();
  await expect(unknown).toContainText("Not evaluated");
  await expect(pass).not.toContainText("Not evaluated");
  await expect(unknown.locator('[data-status="UNKNOWN"]')).toHaveText(/Not evaluated/);
  await expect(pass.locator('[data-status="PASS"]')).toHaveText(/PASS/);
  const styles = await Promise.all(
    [unknown, pass].map((row) => row.evaluate((node) => ({ border: getComputedStyle(node).borderTopStyle, image: getComputedStyle(node).backgroundImage })))
  );
  expect(styles[0].border).toBe("dashed");
  expect(styles[1].border).toBe("solid");
  expect(styles[0].image).not.toBe("none");
  expect(styles[1].image).toBe("none");
  await expect(detail.getByTestId("unknown-count")).toBeVisible();

  // Exports are the API's own text, which begins with the statement.
  const tsv = page.waitForEvent("download");
  await page.getByRole("button", { name: "Guide table TSV" }).click();
  const download = await tsv;
  const content = fs.readFileSync((await download.path())!, "utf8");
  expect(content.startsWith(statement)).toBe(true);
  expect(content).toBe(design.exports["guide_table.tsv"]);
});

test("a rejected request shows the API message and keeps the form", async ({ page }) => {
  await mockCommon(page);
  await page.route(`${API}/v1/aav/design`, (route) =>
    route.fulfill({ status: 422, json: { detail: "no sequence was supplied for transgene 'GFP'. Supply transgene_sequence." } })
  );
  await page.goto("/");
  await page.getByRole("radio", { name: "AAV vector" }).click();
  await page.getByLabel("Transgene name").fill("GFP");
  await page.getByLabel("Transgene coding sequence").fill("ATGAAATAA");
  await page.getByRole("button", { name: "Compose cassette" }).click();
  await expect(page.getByRole("alert").first()).toContainText("Supply transgene_sequence");
  await expect(page.getByLabel("Transgene name")).toHaveValue("GFP");
});

/**
 * EN: SAMPLE ONLY — NOT EXECUTED. This spec is a pattern for Block 18 (package S6,
 *     Polarita-2.7). It has never been run: the application under test and the test
 *     environment do not exist yet (greenfield design, server `polarita-hq` is not
 *     built). All selectors, screen texts and the seed record are illustrative and
 *     must be adapted to the real application before the first run.
 * CZ: POUZE VZOR — NEBYL SPUŠTĚN. Tento test je vzorem pro Blok 18 (balíček S6,
 *     Polarita-2.7). Nikdy neběžel: testovaná aplikace ani testovací prostředí zatím
 *     neexistují (greenfield návrh, server `polarita-hq` není postaven). Všechny
 *     selektory, texty obrazovek a záznam ze seedu jsou ilustrační a před prvním
 *     během se musí přizpůsobit skutečné aplikaci.
 *
 * EN: Rules enforced by this pattern (see ../README.md, chapter 2):
 *     1. The target URL comes only from POLARITA_E2E_BASE_URL — no real address in the repo.
 *     2. Tests run only against a test environment with synthetic data (0 PII).
 *     3. Every step has a Czech caption that becomes the text of the living manual.
 * CZ: Pravidla vynucená tímto vzorem (viz ../README.md, kapitola 2):
 *     1. Cílová adresa pochází pouze z POLARITA_E2E_BASE_URL — v repozitáři není žádná skutečná adresa.
 *     2. Testy běží pouze proti testovacímu prostředí se syntetickými daty (0 PII).
 *     3. Každý krok má český popisek, který se stává textem živé příručky.
 */

import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

import { expect, test, type Page } from '@playwright/test';

// EN: Base URL of the TEST environment; injected by the CI job, never hard-coded.
// CZ: Základní adresa TESTOVACÍHO prostředí; dodává ji úloha CI, nikdy není v kódu.
const BASE_URL = process.env.POLARITA_E2E_BASE_URL;

// EN: Output directory for screenshots and manifests consumed by `manual-builder`.
// CZ: Výstupní složka pro snímky a manifesty, které čte `manual-builder`.
const MANUAL_DIR = process.env.POLARITA_E2E_MANUAL_DIR ?? 'manual-out';

// EN: Test account credentials are read from the environment (filled from OpenBao by CI).
// CZ: Přihlašovací údaje testovacího účtu se čtou z prostředí (v CI je plní OpenBao).
const TEST_USER = process.env.POLARITA_E2E_USER ?? '';
const TEST_PASSWORD = process.env.POLARITA_E2E_PASSWORD ?? '';

// EN: Synthetic file number from the test seed (year 2099 = obviously not a real file).
// CZ: Syntetické číslo spisu z testovacího seedu (rok 2099 = zjevně ne skutečný spis).
const SYNTHETIC_FILE_NO = 'POL-2099-00001';

// EN: Chapter metadata used by `manual-builder` as the chapter heading.
// CZ: Metadata kapitoly, která `manual-builder` použije jako nadpis kapitoly.
const CHAPTER = {
  id: 'karta-spisu',
  title: '360° Karta spisu — otevření spisu a práce s tlačítkem „Pracuj“',
};

interface ManifestStep {
  order: number; // EN: step order within the chapter / CZ: pořadí kroku v kapitole
  caption: string; // EN: Czech caption = manual text / CZ: český popisek = text příručky
  screenshot: string; // EN: file name relative to MANUAL_DIR / CZ: název souboru vůči MANUAL_DIR
  path: string; // EN: URL path only, never the host / CZ: pouze cesta URL, nikdy hostitel
}

interface Manifest {
  chapterId: string;
  chapterTitle: string;
  specFile: string;
  steps: ManifestStep[];
}

// EN: Per-test step counter (keyed by Playwright test id, so parallel workers do not collide).
// CZ: Počítadlo kroků pro každý test (klíčem je id testu, takže se paralelní běhy nepletou).
const stepCounters = new Map<string, number>();

/**
 * EN: Turns a Czech title into a safe ASCII file name part.
 * CZ: Převede český název na bezpečnou ASCII část názvu souboru.
 */
function slugify(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/**
 * EN: Documented step. Takes a captioned screenshot and appends one record to the
 *     chapter manifest (JSON). The Czech caption is also used as the Playwright
 *     step title, so the HTML report and the manual show the same sentence.
 * CZ: Dokumentovaný krok. Pořídí popsaný snímek obrazovky a připíše jeden záznam do
 *     manifestu kapitoly (JSON). Český popisek se použije i jako název kroku
 *     v Playwrightu, takže HTML report i příručka ukazují stejnou větu.
 */
export async function krok(page: Page, popisek: string): Promise<void> {
  const info = test.info();

  await test.step(popisek, async () => {
    const order = (stepCounters.get(info.testId) ?? 0) + 1;
    stepCounters.set(info.testId, order);

    const screenshotName = `${CHAPTER.id}-${String(order).padStart(2, '0')}-${slugify(popisek).slice(0, 48)}.png`;
    const screenshotDir = path.join(MANUAL_DIR, 'screenshots');
    const manifestDir = path.join(MANUAL_DIR, 'manifest');
    const manifestFile = path.join(manifestDir, `${CHAPTER.id}.json`);

    await mkdir(screenshotDir, { recursive: true });
    await mkdir(manifestDir, { recursive: true });

    // EN: Stable screenshots: no animations, no caret; elements marked with
    //     data-e2e-mask are masked as a second safety net against personal data.
    // CZ: Stabilní snímky: bez animací a bez kurzoru; prvky označené
    //     data-e2e-mask se začerní jako druhá pojistka proti osobním údajům.
    await page.screenshot({
      path: path.join(screenshotDir, screenshotName),
      animations: 'disabled',
      caret: 'hide',
      mask: [page.locator('[data-e2e-mask]')],
    });

    // EN: The first step starts a fresh manifest (also on a retry of the test).
    // CZ: První krok zakládá nový manifest (i při opakování testu).
    let manifest: Manifest = {
      chapterId: CHAPTER.id,
      chapterTitle: CHAPTER.title,
      specFile: path.basename(info.file),
      steps: [],
    };
    if (order > 1) {
      manifest = JSON.parse(await readFile(manifestFile, 'utf8')) as Manifest;
    }

    manifest.steps.push({
      order,
      caption: popisek,
      screenshot: path.posix.join('screenshots', screenshotName),
      path: new URL(page.url()).pathname,
    });

    await writeFile(manifestFile, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
  });
}

test.use({
  baseURL: BASE_URL,
  locale: 'cs-CZ',
  timezoneId: 'Europe/Prague',
  viewport: { width: 1280, height: 800 },
});

test.describe(CHAPTER.title, () => {
  test.beforeAll(() => {
    // EN: Fail loudly instead of skipping — a missing variable must not look like a green run.
    // CZ: Hlasité selhání místo přeskočení — chybějící proměnná nesmí vypadat jako zelený běh.
    if (!BASE_URL) {
      throw new Error('POLARITA_E2E_BASE_URL is not set / není nastavena proměnná POLARITA_E2E_BASE_URL');
    }
    if (!TEST_USER || !TEST_PASSWORD) {
      throw new Error('Test account is not provided / není dodán testovací účet (POLARITA_E2E_USER, POLARITA_E2E_PASSWORD)');
    }
  });

  test('Otevření spisu a příprava konceptu tlačítkem „Pracuj“', async ({ page }) => {
    await page.goto('/');

    // EN: FAIL_CLOSED guard — continue only if the page declares itself a test environment.
    // CZ: Pojistka FAIL_CLOSED — pokračuj jen tehdy, když se stránka hlásí jako testovací prostředí.
    await expect(page.getByTestId('env-banner')).toContainText('TESTOVACÍ PROSTŘEDÍ');

    // EN: Sign in with the synthetic test account (single sign-on form).
    // CZ: Přihlášení syntetickým testovacím účtem (formulář jednotného přihlášení).
    await page.getByLabel('Uživatelské jméno').fill(TEST_USER);
    await page.getByLabel('Heslo').fill(TEST_PASSWORD);
    await page.getByRole('button', { name: 'Přihlásit se' }).click();
    await expect(page.getByRole('heading', { name: 'Přehled spisů' })).toBeVisible();
    await krok(page, 'Po přihlášení firemním účtem uvidíte přehled spisů, ke kterým máte přístup.');

    // EN: Find the file by its number POL-RRRR-NNNNN.
    // CZ: Vyhledání spisu podle čísla POL-RRRR-NNNNN.
    await page.getByRole('searchbox', { name: 'Hledat spis' }).fill(SYNTHETIC_FILE_NO);
    await expect(page.getByRole('link', { name: SYNTHETIC_FILE_NO })).toBeVisible();
    await krok(page, 'Do vyhledávání zadejte číslo spisu ve tvaru POL-RRRR-NNNNN; spis se nabídne v seznamu výsledků.');

    // EN: Open the 360° file card.
    // CZ: Otevření 360° Karty spisu.
    await page.getByRole('link', { name: SYNTHETIC_FILE_NO }).click();
    await expect(page.getByRole('heading', { name: new RegExp(SYNTHETIC_FILE_NO) })).toBeVisible();
    await krok(page, 'Otevře se 360° Karta spisu: nahoře je zákazník, objekt a stav zakázky, pod nimi dokumenty, komunikace a úkoly.');

    // EN: Deadlines tab with the traffic-light overview.
    // CZ: Záložka Lhůty se semaforem termínů.
    await page.getByRole('tab', { name: 'Lhůty' }).click();
    await expect(page.getByRole('tabpanel', { name: 'Lhůty' })).toBeVisible();
    await krok(page, 'Na záložce Lhůty ukazuje semafor, které termíny spisu jsou v pořádku, které se blíží a které jsou po lhůtě.');

    // EN: Context button "Pracuj" — the ai prepares a DRAFT only.
    // CZ: Kontextové tlačítko „Pracuj“ — ai připraví pouze koncept (DRAFT).
    await page.getByRole('button', { name: 'Pracuj' }).click();
    await expect(page.getByRole('menu', { name: 'Pracuj' })).toBeVisible();
    await krok(page, 'Tlačítko „Pracuj“ nabídne úkony, které dávají pro tento spis smysl; vyberte ten, který potřebujete.');

    await page.getByRole('menuitem', { name: 'Připravit koncept odpovědi zákazníkovi' }).click();
    await expect(page.getByTestId('draft-status')).toHaveText('DRAFT');
    await krok(page, 'Vznikne pouze koncept označený DRAFT. Nic se neodesílá — koncept zkontrolujte a případně upravte.');

    // EN: The draft waits for approval in Decisions; nothing is sent by the test.
    // CZ: Koncept čeká na schválení v Decisions; test nic neodesílá.
    await page.getByRole('button', { name: 'Předat ke schválení' }).click();
    await expect(page.getByTestId('draft-status')).toHaveText('ČEKÁ NA SCHVÁLENÍ');
    await krok(page, 'Po předání ke schválení čeká koncept ve frontě Decisions; odeslán bude až po potvrzení odpovědnou osobou.');
  });
});

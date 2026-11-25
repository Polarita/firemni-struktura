/**
 * EN: SAMPLE ONLY — NOT EXECUTED. Shared helper of the living manual (Block 18, package S6,
 *     Polarita-3.23). Every spec file imports it and binds it to ITS OWN chapter, so the
 *     helper is written once and no chapter can write into another chapter's manifest.
 * CZ: POUZE VZOR — NEBYL SPUŠTĚN. Sdílená pomocná funkce živé příručky (Blok 18, balíček S6,
 *     Polarita-3.23). Každý soubor testu ji importuje a naváže na SVOU kapitolu, takže je
 *     napsána jednou a žádná kapitola nemůže zapisovat do manifestu jiné kapitoly.
 *
 * EN: Usage in a spec file:
 *       const krok = vytvorKrok({ id: 'karta-spisu', title: '…' });
 *       await krok(page, 'Celá česká věta pro montéra nebo skladníka.');
 * CZ: Použití v souboru testu: viz výše.
 */

import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

import { test, type Page } from '@playwright/test';

// EN: Output directory for screenshots and manifests consumed by `manual-builder`.
// CZ: Výstupní složka pro snímky a manifesty, které čte `manual-builder`.
const MANUAL_DIR = process.env.POLARITA_E2E_MANUAL_DIR ?? 'manual-out';

/**
 * EN: Chapter metadata used by `manual-builder` as the chapter heading.
 *     `id` is ASCII (a-z, 0-9, hyphen) and unique across all spec files.
 * CZ: Metadata kapitoly, která `manual-builder` použije jako nadpis kapitoly.
 *     `id` je ASCII (a-z, 0-9, spojovník) a jedinečné napříč všemi soubory testů.
 */
export interface Kapitola {
  id: string;
  title: string;
}

export type Krok = (page: Page, popisek: string) => Promise<void>;

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

// EN: Per-test + per-retry step counter so retries start cleanly from step 1.
// CZ: Počítadlo kroků na test a pokus (retry), takže opakovaný pokus vždy začíná od kroku 1.
const stepCounters = new Map<string, number>();

/**
 * EN: Turns a Czech title into a safe ASCII file name part.
 * CZ: Převede český název na bezpečnou ASCII část názvu souboru.
 */
function slugify(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/**
 * EN: Returns the documented step bound to one chapter. The step takes a captioned screenshot and appends one record to the
 *     per-test chapter manifest (JSON). Note: [data-e2e-mask] covers annotated DOM
 *     nodes only — all test fixtures must strictly use synthetic 0-PII seeds.
 * CZ: Vrátí dokumentovaný krok navázaný na jednu kapitolu. Krok pořídí popsaný snímek obrazovky a připíše jeden záznam do
 *     manifestu testu (JSON). Upozornění: maskování [data-e2e-mask] zakryje jen
 *     označené prvky DOM — testovací prostředí smí obsahovat výhradně syntetická data (0 PII).
 */
export function vytvorKrok(kapitola: Kapitola): Krok {
  if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(kapitola.id)) {
    throw new Error(`Invalid chapter id / neplatné id kapitoly: ${kapitola.id}`);
  }
  return async function krok(page: Page, popisek: string): Promise<void> {
    const info = test.info();

    await test.step(popisek, async () => {
      const counterKey = `${info.testId}#retry-${info.retry}`;
      const order = (stepCounters.get(counterKey) ?? 0) + 1;
      stepCounters.set(counterKey, order);

      const safeTestKey = createHash('sha256').update(info.testId).digest('hex').slice(0, 32);
      const screenshotName = `${kapitola.id}-${safeTestKey}-${String(order).padStart(2, '0')}-${slugify(popisek).slice(0, 48)}.png`;
      const screenshotDir = path.join(MANUAL_DIR, 'screenshots');
      const manifestDir = path.join(MANUAL_DIR, 'manifest');
      const manifestFile = path.join(manifestDir, `${kapitola.id}-${safeTestKey}.json`);

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
        chapterId: kapitola.id,
        chapterTitle: kapitola.title,
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
  };
}

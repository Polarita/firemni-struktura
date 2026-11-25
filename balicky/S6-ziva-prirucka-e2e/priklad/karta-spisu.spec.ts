/**
 * EN: Unexecuted sample for Block 18 (package S6, Polarita-3.22). Once the
 *     case-file application runs in the polarita-hq VM on Ejpovice, adapt the
 *     selectors, labels and synthetic seed record to that deployment before
 *     running this test.
 * CZ: Nespouštěný vzor pro Blok 18 (balíček S6, Polarita-3.22). Po nasazení
 *     Karty spisu uvnitř VM polarita-hq na Ejpovicích uprav selektory, popisky
 *     obrazovek a syntetický záznam podle aplikace. Potom spusť test.
 *
 * EN: Rules enforced by this pattern (see ../README.md, chapter 2):
 *     1. The target URL comes only from POLARITA_E2E_BASE_URL — no real address in the repo.
 *     2. Tests run only against a test environment with synthetic data (0 PII).
 *     3. Every step has a Czech caption that becomes the text of the living manual.
 *     4. The step helper is shared (./krok.ts) and bound to the chapter of this file.
 * CZ: Pravidla vynucená tímto vzorem (viz ../README.md, kapitola 2):
 *     1. Cílová adresa pochází pouze z POLARITA_E2E_BASE_URL — v repozitáři není žádná skutečná adresa.
 *     2. Testy běží pouze proti testovacímu prostředí se syntetickými daty (0 PII).
 *     3. Každý krok má český popisek, který se stává textem živé příručky.
 *     4. Pomocná funkce kroku je sdílená (./krok.ts) a navázaná na kapitolu tohoto souboru.
 */

import { expect, test } from '@playwright/test';

import { vytvorKrok } from './krok';

// EN: Base URL of the TEST environment; injected by the CI job, never hard-coded.
// CZ: Základní adresa TESTOVACÍHO prostředí; dodává ji úloha CI, nikdy není v kódu.
const BASE_URL = process.env.POLARITA_E2E_BASE_URL;

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

// EN: Documented step bound to this chapter; the shared helper lives in ./krok.ts.
// CZ: Dokumentovaný krok navázaný na tuto kapitolu; sdílená pomocná funkce je v ./krok.ts.
const krok = vytvorKrok(CHAPTER);

function requireBaseUrl(): string {
  if (!BASE_URL) {
    throw new Error('POLARITA_E2E_BASE_URL is not set / není nastavena proměnná POLARITA_E2E_BASE_URL');
  }
  const parsed = new URL(BASE_URL);
  const localHttp = parsed.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(parsed.hostname);
  if (parsed.protocol !== 'https:' && !localHttp) {
    throw new Error(`Unsafe POLARITA_E2E_BASE_URL protocol: ${parsed.protocol}`);
  }
  return BASE_URL;
}

test.use({
  baseURL: BASE_URL ?? 'about:blank',
  locale: 'cs-CZ',
  timezoneId: 'Europe/Prague',
  viewport: { width: 1280, height: 800 },
});

test.describe(CHAPTER.title, () => {
  test.beforeAll(() => {
    // EN: Fail loudly instead of skipping — missing URL or credentials must fail before goto('/').
    // CZ: Hlasité selhání místo přeskočení — chybějící URL či údaje musí selhat před voláním goto('/').
    requireBaseUrl();
    if (!TEST_USER || !TEST_PASSWORD) {
      throw new Error('Test account is not provided / není dodán testovací účet (POLARITA_E2E_USER, POLARITA_E2E_PASSWORD)');
    }
  });

  test('Otevření spisu a příprava konceptu tlačítkem „Pracuj“', async ({ page }) => {
    const validatedUrl = requireBaseUrl();
    await page.goto(new URL('/', validatedUrl).toString());

    // EN: FAIL_CLOSED guard — continue only if the page declares itself a test environment.
    // CZ: Pojistka FAIL_CLOSED — pokračuj jen tehdy, když se stránka hlásí jako testovací prostředí.
    await expect(page.getByTestId('env-banner')).toContainText('TESTOVACÍ PROSTŘEDÍ');

    // EN: Sign in with the synthetic test account; for real Keycloak OIDC / MFA suites,
    //     prefer a shared setup project using Playwright storageState instead of repeating login.
    // CZ: Přihlášení syntetickým účtem; u ostrých OIDC testů za Keycloakem (příp. MFA) použij
    //     sdílený setup projekt a storageState, aby se přihlášení neopakovalo v každé kapitole.
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

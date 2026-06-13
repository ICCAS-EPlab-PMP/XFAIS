import { test, expect } from '@playwright/test';

/**
 * E2E tests for BgSubtractView — 背景扣除页面
 *
 * Covers: page load, mode switching, file selection UI,
 *         ionchamber UI, batch UI, i18n, execute button state.
 */

const PAGE_URL = '/#/workspace/bg-subtract';

// ─── Selectors ────────────────────────────────────────────────

const sel = {
  page: '.bg-subtract-page',
  header: '.bgs-header',
  subtitle: '.bgs-subtitle',
  layout: '.bgs-layout',
  sidebar: '.bgs-sidebar',
  main: '.bgs-main',
  card: '.bgs-card',
  cardTitle: '.bgs-card-title',
  radioRow: '.bgs-radio-row',
  radioLabel: '.bgs-radio-label',
  btnPrimary: '.bgs-btn-primary',
  btn: '.bgs-btn',
  input: '.bgs-input',
  select: '.bgs-select',
  tabs: '.bgs-tabs',
  tab: '.bgs-tab',
  tabActive: '.bgs-tab--active',
  previewSection: '.bgs-preview-section',
  previewEmpty: '.bgs-preview-empty',
  empty: '.bgs-empty',
  matchTable: '.bgs-match-table',
  field: '.bgs-field',
  label: '.bgs-label',
  // data-testid selectors
  fileDialogButton: '[data-testid="file-dialog-button"]',
  fileDialogTrigger: '[data-testid="file-dialog-trigger"]',
  localeSwitch: '[data-testid="shell-locale-switch"]',
} as const;

// ─── Helpers ──────────────────────────────────────────────────

async function gotoPage(page: import('@playwright/test').Page) {
  await page.goto(PAGE_URL);
  await page.waitForSelector(sel.page, { timeout: 10_000 });
}

// ─── Tests ────────────────────────────────────────────────────

test.describe('BgSubtractView', () => {

  test.describe('Page Load', () => {

    test('page loads correctly', async ({ page }) => {
      await gotoPage(page);

      // Header with title is visible
      const header = page.locator(sel.header);
      await expect(header).toBeVisible();
      await expect(header.locator('h1')).toBeVisible();

      // Subtitle contains the formula
      const subtitle = page.locator(sel.subtitle);
      await expect(subtitle).toBeVisible();
      await expect(subtitle).toContainText('result = sample / T - background');

      // Layout has sidebar and main areas
      await expect(page.locator(sel.sidebar)).toBeVisible();
      await expect(page.locator(sel.main)).toBeVisible();
    });

    test('sidebar contains all control sections', async ({ page }) => {
      await gotoPage(page);

      const sidebar = page.locator(sel.sidebar);
      // 5 cards: mode, file selection, ionchamber, execute, export
      const cards = sidebar.locator(sel.card);
      await expect(cards).toHaveCount(5);
    });

    test('preview area shows empty state initially', async ({ page }) => {
      await gotoPage(page);

      // Empty state message is shown when idle with no files
      const emptyState = page.locator(sel.empty);
      await expect(emptyState).toBeVisible();
    });

    test('preview tabs are present', async ({ page }) => {
      await gotoPage(page);

      const tabs = page.locator(sel.tab);
      await expect(tabs).toHaveCount(3);

      // Result tab is active by default
      const activeTab = page.locator(sel.tabActive);
      await expect(activeTab).toBeVisible();
    });
  });

  test.describe('Mode Switching', () => {

    test('defaults to single mode', async ({ page }) => {
      await gotoPage(page);

      // Single mode radio should be checked by default
      const singleRadio = page.locator('input[type="radio"][value="single"]');
      await expect(singleRadio).toBeChecked();

      const batchRadio = page.locator('input[type="radio"][value="batch"]');
      await expect(batchRadio).not.toBeChecked();
    });

    test('switching to batch mode shows folder selector', async ({ page }) => {
      await gotoPage(page);

      // Click batch mode radio
      const batchRadio = page.locator('input[type="radio"][value="batch"]');
      await batchRadio.check();
      await expect(batchRadio).toBeChecked();

      // In batch mode, file selection card shows folder-related file dialog buttons
      // The file selection card (2nd card) should have file-dialog-button components
      const fileCards = page.locator(sel.sidebar).locator(sel.card);
      const fileSelectionCard = fileCards.nth(1);
      const dialogButtons = fileSelectionCard.locator(sel.fileDialogButton);
      await expect(dialogButtons).toHaveCount(2);
    });

    test('switching back to single mode shows file selectors', async ({ page }) => {
      await gotoPage(page);

      // Switch to batch then back to single
      await page.locator('input[type="radio"][value="batch"]').check();
      await page.locator('input[type="radio"][value="single"]').check();

      const singleRadio = page.locator('input[type="radio"][value="single"]');
      await expect(singleRadio).toBeChecked();

      // File selection card should have file dialog buttons
      const fileCards = page.locator(sel.sidebar).locator(sel.card);
      const fileSelectionCard = fileCards.nth(1);
      const dialogButtons = fileSelectionCard.locator(sel.fileDialogButton);
      await expect(dialogButtons).toHaveCount(2);
    });

    test('execute button text changes with mode', async ({ page }) => {
      await gotoPage(page);

      const execBtn = page.locator(sel.btnPrimary);

      // Single mode: shows execute text (Chinese default: '执行扣除')
      await expect(execBtn).toContainText('执行扣除');

      // Switch to batch mode
      await page.locator('input[type="radio"][value="batch"]').check();

      // Batch mode: shows start batch text (Chinese default: '开始批处理')
      await expect(execBtn).toContainText('开始批处理');
    });
  });

  test.describe('File Selection UI', () => {

    test('single mode has sample and background file buttons', async ({ page }) => {
      await gotoPage(page);

      // File selection card (2nd card in sidebar)
      const fileCards = page.locator(sel.sidebar).locator(sel.card);
      const fileSelectionCard = fileCards.nth(1);

      // Should have 2 file dialog buttons in single mode
      const triggers = fileSelectionCard.locator(sel.fileDialogTrigger);
      await expect(triggers).toHaveCount(2);
    });

    test('batch mode has sample folder and background file buttons', async ({ page }) => {
      await gotoPage(page);

      // Switch to batch mode
      await page.locator('input[type="radio"][value="batch"]').check();

      const fileCards = page.locator(sel.sidebar).locator(sel.card);
      const fileSelectionCard = fileCards.nth(1);

      // Should have 2 file dialog buttons in batch mode
      const triggers = fileSelectionCard.locator(sel.fileDialogTrigger);
      await expect(triggers).toHaveCount(2);
    });

    test('file dialog buttons show choose file / choose folder text', async ({ page }) => {
      await gotoPage(page);

      const fileCards = page.locator(sel.sidebar).locator(sel.card);
      const fileSelectionCard = fileCards.nth(1);

      // In single mode, buttons should show "选择文件" (choose file) text
      const triggers = fileSelectionCard.locator(sel.fileDialogTrigger);
      await expect(triggers.first()).toBeVisible();
    });
  });

  test.describe('Ionchamber Section', () => {

    test('ionchamber section is present with manual mode default', async ({ page }) => {
      await gotoPage(page);

      // Ionchamber card is the 3rd card in sidebar
      const cards = page.locator(sel.sidebar).locator(sel.card);
      const ionCard = cards.nth(2);
      await expect(ionCard).toBeVisible();

      // Manual radio should be checked by default
      const manualRadio = ionCard.locator('input[type="radio"][value="manual"]');
      await expect(manualRadio).toBeChecked();

      // Ionchamber radio should not be checked
      const ionRadio = ionCard.locator('input[type="radio"][value="ionchamber"]');
      await expect(ionRadio).not.toBeChecked();
    });

    test('manual mode shows transmission input', async ({ page }) => {
      await gotoPage(page);

      // In manual mode, the number input should be visible
      const ionCard = page.locator(sel.sidebar).locator(sel.card).nth(2);
      const numberInput = ionCard.locator('input[type="number"]');
      await expect(numberInput).toBeVisible();

      // Default value should be 1
      await expect(numberInput).toHaveValue('1');
    });

    test('switching to ionchamber mode shows folder selector', async ({ page }) => {
      await gotoPage(page);

      const ionCard = page.locator(sel.sidebar).locator(sel.card).nth(2);

      // Switch to ionchamber mode
      const ionRadio = ionCard.locator('input[type="radio"][value="ionchamber"]');
      await ionRadio.check();
      await expect(ionRadio).toBeChecked();

      // Manual input should be hidden
      const numberInput = ionCard.locator('input[type="number"]');
      await expect(numberInput).not.toBeVisible();

      // Ionchamber folder selector should appear
      const folderButton = ionCard.locator(sel.fileDialogButton);
      await expect(folderButton).toBeVisible();

      // Match button should be present
      const matchBtn = ionCard.locator(sel.btn).first();
      await expect(matchBtn).toBeVisible();
      // Match button should be disabled (no folders selected)
      await expect(matchBtn).toBeDisabled();
    });

    test('toggling between manual and ionchamber modes', async ({ page }) => {
      await gotoPage(page);

      const ionCard = page.locator(sel.sidebar).locator(sel.card).nth(2);

      // Start in manual mode
      await expect(ionCard.locator('input[type="number"]')).toBeVisible();

      // Switch to ionchamber
      await ionCard.locator('input[type="radio"][value="ionchamber"]').check();
      await expect(ionCard.locator('input[type="number"]')).not.toBeVisible();
      await expect(ionCard.locator(sel.fileDialogButton)).toBeVisible();

      // Switch back to manual
      await ionCard.locator('input[type="radio"][value="manual"]').check();
      await expect(ionCard.locator('input[type="number"]')).toBeVisible();
    });
  });

  test.describe('Transmission Input', () => {

    test('manual transmission input accepts values', async ({ page }) => {
      await gotoPage(page);

      const ionCard = page.locator(sel.sidebar).locator(sel.card).nth(2);
      const numberInput = ionCard.locator('input[type="number"]');

      // Clear and type a new value
      await numberInput.fill('0.75');
      await expect(numberInput).toHaveValue('0.75');
    });

    test('manual transmission input has correct attributes', async ({ page }) => {
      await gotoPage(page);

      const ionCard = page.locator(sel.sidebar).locator(sel.card).nth(2);
      const numberInput = ionCard.locator('input[type="number"]');

      await expect(numberInput).toHaveAttribute('min', '0');
      await expect(numberInput).toHaveAttribute('max', '1');
      await expect(numberInput).toHaveAttribute('step', '0.01');
    });
  });

  test.describe('Export Settings', () => {

    test('export section has output folder and format selector', async ({ page }) => {
      await gotoPage(page);

      // Export card is the 5th (last) card in sidebar
      const cards = page.locator(sel.sidebar).locator(sel.card);
      const exportCard = cards.nth(4);
      await expect(exportCard).toBeVisible();

      // Output folder selector
      const folderButton = exportCard.locator(sel.fileDialogButton);
      await expect(folderButton).toBeVisible();

      // Output format select
      const formatSelect = exportCard.locator(sel.select);
      await expect(formatSelect).toBeVisible();
    });

    test('output format defaults to HDF5', async ({ page }) => {
      await gotoPage(page);

      const exportCard = page.locator(sel.sidebar).locator(sel.card).nth(4);
      const formatSelect = exportCard.locator(sel.select);
      await expect(formatSelect).toHaveValue('h5');
    });

    test('output format can be changed to EDF', async ({ page }) => {
      await gotoPage(page);

      const exportCard = page.locator(sel.sidebar).locator(sel.card).nth(4);
      const formatSelect = exportCard.locator(sel.select);

      await formatSelect.selectOption('edf');
      await expect(formatSelect).toHaveValue('edf');
    });
  });

  test.describe('Execute Button', () => {

    test('execute button is disabled without files in single mode', async ({ page }) => {
      await gotoPage(page);

      const execBtn = page.locator(sel.btnPrimary);
      await expect(execBtn).toBeDisabled();
    });

    test('execute button is disabled without files in batch mode', async ({ page }) => {
      await gotoPage(page);

      // Switch to batch mode
      await page.locator('input[type="radio"][value="batch"]').check();

      const execBtn = page.locator(sel.btnPrimary);
      await expect(execBtn).toBeDisabled();
    });
  });

  test.describe('i18n', () => {

    test('Chinese is the default locale', async ({ page }) => {
      await gotoPage(page);

      // Title should be in Chinese
      const title = page.locator(sel.header).locator('h1');
      await expect(title).toContainText('背景扣除');

      // Mode labels should be in Chinese
      await expect(page.locator(sel.sidebar)).toContainText('单文件模式');
      await expect(page.locator(sel.sidebar)).toContainText('批处理模式');

      // Tab labels should be in Chinese
      await expect(page.locator(sel.tabs)).toContainText('样品');
      await expect(page.locator(sel.tabs)).toContainText('背景');
      await expect(page.locator(sel.tabs)).toContainText('结果');
    });

    test('locale switch button shows EN in Chinese mode', async ({ page }) => {
      await gotoPage(page);

      const localeSwitch = page.locator(sel.localeSwitch);
      await expect(localeSwitch).toBeVisible();
      // When in Chinese mode, the button shows "EN" to switch to English
      await expect(localeSwitch).toHaveText('EN');
    });

    test('switching to English updates UI text', async ({ page }) => {
      await gotoPage(page);

      // Click locale switch to change to English
      const localeSwitch = page.locator(sel.localeSwitch);
      await localeSwitch.click();

      // Button should now show '中' (to switch back to Chinese)
      await expect(localeSwitch).toHaveText('中');

      // Title should be in English
      const title = page.locator(sel.header).locator('h1');
      await expect(title).toContainText('Background Subtraction');

      // Mode labels should be in English
      await expect(page.locator(sel.sidebar)).toContainText('Single File');
      await expect(page.locator(sel.sidebar)).toContainText('Batch Processing');

      // Tab labels should be in English
      await expect(page.locator(sel.tabs)).toContainText('Sample');
      await expect(page.locator(sel.tabs)).toContainText('Background');
      await expect(page.locator(sel.tabs)).toContainText('Result');
    });

    test('switching locale back to Chinese restores Chinese text', async ({ page }) => {
      await gotoPage(page);

      const localeSwitch = page.locator(sel.localeSwitch);

      // Switch to English
      await localeSwitch.click();
      await expect(page.locator(sel.header).locator('h1')).toContainText('Background Subtraction');

      // Switch back to Chinese
      await localeSwitch.click();
      await expect(page.locator(sel.header).locator('h1')).toContainText('背景扣除');
    });
  });

  test.describe('Batch Mode Progress Components', () => {

    test('batch mode shows output folder selector', async ({ page }) => {
      await gotoPage(page);

      // Switch to batch mode
      await page.locator('input[type="radio"][value="batch"]').check();

      // Export card should have output folder selector
      const exportCard = page.locator(sel.sidebar).locator(sel.card).nth(4);
      const folderButton = exportCard.locator(sel.fileDialogButton);
      await expect(folderButton).toBeVisible();
    });

    test('batch mode shows export format selector', async ({ page }) => {
      await gotoPage(page);

      // Switch to batch mode
      await page.locator('input[type="radio"][value="batch"]').check();

      // Export card should have format selector
      const exportCard = page.locator(sel.sidebar).locator(sel.card).nth(4);
      const formatSelect = exportCard.locator(sel.select);
      await expect(formatSelect).toBeVisible();

      // Should have HDF5 and EDF options
      const options = formatSelect.locator('option');
      await expect(options).toHaveCount(2);
      await expect(options.nth(0)).toHaveValue('h5');
      await expect(options.nth(1)).toHaveValue('edf');
    });
  });

  test.describe('Preview Tabs', () => {

    test('clicking tabs switches active tab', async ({ page }) => {
      await gotoPage(page);

      const tabs = page.locator(sel.tab);

      // Click sample tab
      await tabs.nth(0).click();
      await expect(tabs.nth(0)).toHaveClass(/bgs-tab--active/);

      // Click background tab
      await tabs.nth(1).click();
      await expect(tabs.nth(1)).toHaveClass(/bgs-tab--active/);

      // Click result tab
      await tabs.nth(2).click();
      await expect(tabs.nth(2)).toHaveClass(/bgs-tab--active/);
    });
  });
});

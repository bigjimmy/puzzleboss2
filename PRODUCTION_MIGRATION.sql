-- =============================================================================
-- PRODUCTION MIGRATION: Apps Script Puzzle Tools Integration
-- =============================================================================
-- Run this on production to enable configurable puzzle tools deployment
--
-- Usage:
--   mysql -u puzzleboss -p puzzleboss < PRODUCTION_MIGRATION.sql
--
-- What this does:
--   1. Expands config.val column to support large Apps Script code (16MB limit)
--   2. Inserts puzzle tools add-on code into APPS_SCRIPT_ADDON_CODE config
--   3. Inserts manifest into APPS_SCRIPT_ADDON_MANIFEST config
-- =============================================================================

-- Step 1: Expand config.val column to MEDIUMTEXT
-- (Safe to run multiple times - idempotent)
ALTER TABLE `config` MODIFY COLUMN `val` MEDIUMTEXT DEFAULT NULL;

-- Step 2: Insert Apps Script add-on code
-- (Uses ON DUPLICATE KEY UPDATE so it's safe to re-run)
INSERT INTO `config` (`key`, val) VALUES ('APPS_SCRIPT_ADDON_CODE', '/** @OnlyCurrentDoc */
/**
 * Puzzle Tools Add-on (Latest Version)
 *
 * Combined puzzle-solving utilities and activity tracking for Google Sheets.
 * Based on dannybd/sheets-puzzleboss-tools (https://github.com/dannybd/sheets-puzzleboss-tools)
 *
 * Features:
 * - Puzzle grid tools (symmetry, crossword formatting, hex grids)
 * - Hidden sheet-based activity tracking for Puzzleboss integration
 * - Quick tab creation from puzzle lists
 *
 * This version should be deployed to puzzle sheets via Apps Script API.
 */

// Colors from the standard Sheets color picker.
const BLACK = ''#000000'';
const DARK_GRAY_1 = ''#b7b7b7'';

function onInstall(e) {
  onOpen(e);
}

function onOpen(e) {
  if (e?.authMode == ''NONE'') {
    let menu = SpreadsheetApp.getUi().createMenu(''❗️ Puzzle Tools (click me!)'')
      .addItem(''Enable for this spreadsheet'', ''populateMenus'');
    menu = _maybeAddDebug(menu);
    menu.addToUi();
  } else {
    populateMenus();
  }
}

/**
 * Helper function used to add all the menu options for this script.
 */
function populateMenus() {
  const ui = SpreadsheetApp.getUi();
  let menu = ui.createMenu(''🧩 Puzzle Tools'')
    .addItem(''🔠 Resize Cells into Squares'', ''resizeCellsIntoSquares'')
    .addSubMenu(ui.createMenu(''🪞 Symmetrify Grid'')
      .addItem(''🔁 Rotationally (e.g. crossword)'', ''doRotationalSymmetrification'')
      .addItem(''↔️ Bilaterally (left-right)'', ''doBilateralSymmetrification''))
    .addItem(''🗂️ Quick-Add Named Tabs'', ''doAddNamedTabs'')
    .addItem(''📰 Format as Crossword Grid (/ = ◼️)'', ''doCrosswordFormatting'')
    .addItem(''🐝 Add Hexagonal Grid Sheet'', ''addHexGridSheet'')
    .addItem(''🫥 Delete Blank Rows In Selection'', ''deleteBlankRows'')
  menu.addToUi();
}

/**
 * Ask the user for a set of comma-delimited names and make tabs with the names.
 */
function doAddNamedTabs() {
  const range = SpreadsheetApp.getActiveRange();
  let names = [];
  let answerRefs = [];
  if (range.getWidth() === 1 && range.getHeight() > 1) {
    names = range.getDisplayValues().map(row => row[0]);
  } else if (range.getWidth() === 2 && range.getHeight() >= 1) {
    names = range.getDisplayValues().map(row => row[1]);
    const sourceSheet = range.getSheet();
    answerRefs = names.map((_, i) =>
      `=''${sourceSheet.getName()}''!${range.getCell(i + 1, 1).getA1Notation()}`,
    );
  } else {
    const ui = SpreadsheetApp.getUi();
    const result = ui.prompt(
      ''Adding Tabs'',
      ''Enter a comma-delimited list of tab names.'',
      ui.ButtonSet.OK_CANCEL,
    );
    if (!_shouldContinueFromDialog(result)) {
      return;
    }
    names = result.getResponseText().split('','');
  }
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const tabColors = [
    ''red'',
    ''orange'',
    ''yellow'',
    ''green'',
    ''cyan'',
    ''blue'',
    ''purple'',
    ''magenta'',
    ''black'',
  ];
  const tabColor = tabColors[Math.floor(Math.random() * tabColors.length)];
  names.forEach((rawTabName, i) => {
    let tabName = rawTabName.trim();
    if (tabName === '''') {
      return;
    }
    let sheet = null;
    while (sheet === null) {
      try {
        sheet = spreadsheet.insertSheet(tabName);
      } catch (_) {
        tabName = `Copy of ${tabName}`;
      }
    }
    sheet.appendRow([''TITLE:'', rawTabName]);
    if (answerRefs[i]) {
      sheet.appendRow([''ANSWER:'', answerRefs[i]]);
      sheet.setFrozenRows(2);
      sheet.getRange(''1:2'').setFontWeight(''bold'');
      sheet.getRange(''B2'').setBackground(''yellow'');
    } else {
      sheet.setFrozenRows(1);
      sheet.getRange(''1:1'').setFontWeight(''bold'');
    }
    sheet.setTabColor(tabColor);
  });
}

/**
 * Copy in a hex grid sheet
 */
function addHexGridSheet() {
  const HEX_GRID_TEMPLATE_ID = ''1xQSN0mAhn-0LJzuEM2KIxPXFjcNz6o5VWFFwFCtSovA'';
  const hexGrid = SpreadsheetApp.openById(HEX_GRID_TEMPLATE_ID)
    .getSheets()[0];
  if (!hexGrid) {
    SpreadsheetApp.getUi().alert(`Could not load template from ${HEX_GRID_TEMPLATE_ID}!`);
    return;
  }
  hexGrid.copyTo(SpreadsheetApp.getActiveSpreadsheet()).activate();
}

/**
 * Given a set of cells, ensure that cells are reflected at the 180-degree point.
 * In other words, a cell in the upper left will get the same color in the lower right.
 */
function doRotationalSymmetrification() {
  const cells = SpreadsheetApp.getActiveRange();
  _doSymmetrification(
    Math.ceil(cells.getNumRows() / 2),
    cells.getNumColumns(),
    (seedRow, seedColumn, selectedCells) => selectedCells.getCell(
      selectedCells.getNumRows() - (seedRow - 1),
      selectedCells.getNumColumns() - (seedColumn - 1),
    ),
  );
}

/**
 * Given a set of cells, ensure that cells to the right of the central column mirror the ones on the left side.
 */
function doBilateralSymmetrification() {
  const cells = SpreadsheetApp.getActiveRange();
  _doSymmetrification(
    cells.getNumRows(),
    Math.ceil(cells.getNumColumns() / 2),
    (seedRow, seedColumn, selectedCells) => selectedCells.getCell(
      seedRow,
      selectedCells.getNumColumns() - (seedColumn - 1),
    ),
  );
}

/**
 * Symmetrify the grid based on the passed-in parameters.
 *
 * @param {Number} the max row to look at (relative to the range upper-left)
 * @param {Number} the max column to look at (relative to the range upper-left)
 * @param {Function} a callback function that takes row, column of a given cell, and selectedCells and returns the _mirroring_ cell to affect
 */
function _doSymmetrification(maxRow, maxColumn, callback) {
  const cells = SpreadsheetApp.getActiveRange();
  for (let curRelativeRow = 1; curRelativeRow <= maxRow; curRelativeRow++) {
    for (let curRelativeColumn = 1; curRelativeColumn <= maxColumn; curRelativeColumn++) {
      let currentCell = cells.getCell(curRelativeRow, curRelativeColumn);

      let mirrorCell = callback(curRelativeRow, curRelativeColumn, cells);
      if (currentCell.getBackgroundColor() != mirrorCell.getBackgroundColor()) {
        mirrorCell.setBackgroundColor(currentCell.getBackgroundColor());
      }
    }
  }
}

/**
 * Set conditional formatting rules commonly used for crossword grids.
 */
function doCrosswordFormatting() {
  const sheet = SpreadsheetApp.getActiveSheet();
  let range = SpreadsheetApp.getActiveRange();
  if (range.getWidth() == 1 && range.getHeight() == 1) {
    range = sheet.getRange(
      1,
      range.getColumn(),
      sheet.getMaxRows(),
      _getGridWidthFromUser(),
    );
  }
  range.setHorizontalAlignment(''center'');
  _addConditionalFormatRules(
    SpreadsheetApp.newConditionalFormatRule()
      .setRanges([range])
      .whenTextEqualTo(''/'')
      .setBackground(BLACK)
      .build(),
    SpreadsheetApp.newConditionalFormatRule()
      .setRanges([range])
      .whenNumberGreaterThan(0)
      .setFontColor(DARK_GRAY_1)
      .build(),
  );
  const height = sheet.getRowHeight(range.getRow());
  sheet.setColumnWidths(range.getColumn(), range.getNumColumns(), height);
}

/**
 * @param {!Array<ConditionalFormatRule>} newRules The rules to add.
 */
function _addConditionalFormatRules(...newRules) {
  const sheet = SpreadsheetApp.getActiveSheet();
  const rules = sheet.getConditionalFormatRules();
  rules.push(...newRules);
  sheet.setConditionalFormatRules(rules);
}

function deleteBlankRows() {
  const range = SpreadsheetApp.getActiveRange();

  if (range.getNumRows() < 2) {
    throw new Error(''Please select more than 1 row'');
  }

  for (let rowN = range.getNumRows() - 1; rowN >= 0; rowN--) {
    let rowRange = range.offset(rowN, 0, 1);
    if (rowRange.isBlank()) {
      rowRange.deleteCells(SpreadsheetApp.Dimension.ROWS);
    }
  }
}

/**
 * Gets a cell size from the user
 * @return {Integer} the size the user requested
 */
function _getGridWidthFromUser() {
  const ui = SpreadsheetApp.getUi();
  const dialogResult = ui.prompt(
    ''How many columns?'',
    ''Enter a number of columns. '' +
      ''Consider leaving a couple columns of buffer room '' +
      ''(i.e., for a 15x15 puzzle, make 17 columns)'',
    ui.ButtonSet.OK_CANCEL,
  );
  if (!_shouldContinueFromDialog(dialogResult)) {
    return 0;
  }
  return parseInt(dialogResult.getResponseText(), 10) || 0;
}

/**
 * Given a set of cells, set their columns and rows to the same size. Useful for a grid of
 * square cells for use with crosswords and so on.
 */
function resizeCellsIntoSquares() {
  const cells = SpreadsheetApp.getActiveRange();
  const sheet = SpreadsheetApp.getActiveSpreadsheet();
  const startingColumn = cells.getColumn();
  const startingRow = cells.getRow();
  const ui = SpreadsheetApp.getUi();
  const dialogResult = ui.prompt(
    ''Setting Cell Size'',
    `Enter a cell size in pixels\n[default=21]`,
    ui.ButtonSet.OK_CANCEL,
  );
  if (dialogResult.getSelectedButton() == ui.Button.CANCEL) {
    return;
  }
  const newCellSize = parseInt(dialogResult.getResponseText(), 10) || 21;
  for (let col = startingColumn; col < startingColumn + cells.getNumColumns(); col++) {
    sheet.setColumnWidth(col, newCellSize);
  }
  for (let row = startingRow; row < startingRow + cells.getNumRows(); row++) {
    sheet.setRowHeight(row, newCellSize);
  }
}

/**
 * Determine if the dialog result suggests that the user should continue.
 * @param {Object} the dialog result object
 * @return true if the dialog result suggests something that should continue, false if not.
 */
function _shouldContinueFromDialog(dialogResult) {
  const button = dialogResult.getSelectedButton();
  if (button == SpreadsheetApp.getUi().Button.CANCEL) {
    return false;
  }
  const response = dialogResult.getResponseText();
  if (response == null || response.trim() == '''') {
    return false;
  }
  return true;
}

/**
 * Activity tracking via hidden _pb_activity sheet.
 * Simple trigger — fires on every manual edit.
 * Records the editor''s email and Unix timestamp.
 */

const ACTIVITY_SHEET_NAME = ''_pb_activity'';

function onEdit(e) {
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let actSheet = ss.getSheetByName(ACTIVITY_SHEET_NAME);

    // Fallback: create the sheet if it doesn''t exist
    if (!actSheet) {
      actSheet = ss.insertSheet(ACTIVITY_SHEET_NAME);
      actSheet.getRange(''A1'').setValue(''editor'');
      actSheet.getRange(''B1'').setValue(''timestamp'');
      actSheet.getRange(''C1'').setValue(''num_sheets'');
    }

    // Get editor info
    let editor = '''';
    if (e && e.user) {
      editor = e.user.getEmail();
    }
    if (!editor) {
      try {
        editor = Session.getActiveUser().getEmail();
      } catch(ex) {
        editor = ''unknown'';
      }
    }

    const now = Math.floor(Date.now() / 1000);
    // Count sheets, excluding the activity sheet itself
    const numSheets = ss.getSheets().length - 1;

    // Update or insert editor row
    const data = actSheet.getDataRange().getValues();
    let found = false;
    for (let i = 1; i < data.length; i++) {
      if (String(data[i][0]).trim() === String(editor).trim()) {
        actSheet.getRange(i + 1, 2).setValue(now);
        actSheet.getRange(i + 1, 3).setValue(numSheets);
        found = true;
        break;
      }
    }
    if (!found) {
      const lastRow = actSheet.getLastRow() + 1;
      actSheet.getRange(lastRow, 1).setValue(editor);
      actSheet.getRange(lastRow, 2).setValue(now);
      actSheet.getRange(lastRow, 3).setValue(numSheets);
    }
  } catch(err) {
    // Simple triggers can''t easily log errors — silently fail
  }
}
')
ON DUPLICATE KEY UPDATE val = VALUES(val);

-- Step 3: Insert Apps Script manifest
INSERT INTO `config` (`key`, val) VALUES ('APPS_SCRIPT_ADDON_MANIFEST', '{
  "timeZone": "America/New_York",
  "dependencies": {},
  "exceptionLogging": "STACKDRIVER",
  "runtimeVersion": "V8"
}')
ON DUPLICATE KEY UPDATE val = VALUES(val);

-- Done!
SELECT CONCAT('✅ Migration complete! Added ', LENGTH(val), ' chars of Apps Script code') AS status
FROM config WHERE `key` = 'APPS_SCRIPT_ADDON_CODE';

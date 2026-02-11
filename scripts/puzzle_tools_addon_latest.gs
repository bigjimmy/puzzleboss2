/** @OnlyCurrentDoc */
/**
 * Puzzle Tools Add-on (Latest Version)
 *
 * Combined puzzle-solving utilities and activity tracking for Google Sheets.
 * Based on dannybd/sheets-puzzleboss-tools (https://github.com/dannybd/sheets-puzzleboss-tools)
 *
 * Features:
 * - Puzzle grid tools (symmetry, crossword formatting, hex grids)
 * - DeveloperMetadata-based activity tracking for Puzzleboss integration
 * - Quick tab creation from puzzle lists
 *
 * This version should be deployed to puzzle sheets via Apps Script API.
 */

// Colors from the standard Sheets color picker.
const BLACK = '#000000';
const DARK_GRAY_1 = '#b7b7b7';

function onInstall(e) {
  onOpen(e);
}

function onOpen(e) {
  if (e?.authMode == 'NONE') {
    let menu = SpreadsheetApp.getUi().createMenu('❗️ Puzzle Tools (click me!)')
      .addItem('Enable for this spreadsheet', 'populateMenus');
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
  let menu = ui.createMenu('🧩 Puzzle Tools')
    .addItem('🔠 Resize Cells into Squares', 'resizeCellsIntoSquares')
    .addSubMenu(ui.createMenu('🪞 Symmetrify Grid')
      .addItem('🔁 Rotationally (e.g. crossword)', 'doRotationalSymmetrification')
      .addItem('↔️ Bilaterally (left-right)', 'doBilateralSymmetrification'))
    .addItem('🗂️ Quick-Add Named Tabs', 'doAddNamedTabs')
    .addItem('📰 Format as Crossword Grid (/ = ◼️)', 'doCrosswordFormatting')
    .addItem('🐝 Add Hexagonal Grid Sheet', 'addHexGridSheet')
    .addItem('🫥 Delete Blank Rows In Selection', 'deleteBlankRows')
  menu = _maybeAddDebug(menu);
  menu.addToUi();
  updateSpreadsheetStats();
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
      `='${sourceSheet.getName()}'!${range.getCell(i + 1, 1).getA1Notation()}`,
    );
  } else {
    const ui = SpreadsheetApp.getUi();
    const result = ui.prompt(
      'Adding Tabs',
      'Enter a comma-delimited list of tab names.',
      ui.ButtonSet.OK_CANCEL,
    );
    if (!_shouldContinueFromDialog(result)) {
      return;
    }
    names = result.getResponseText().split(',');
  }
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const tabColors = [
    'red',
    'orange',
    'yellow',
    'green',
    'cyan',
    'blue',
    'purple',
    'magenta',
    'black',
  ];
  const tabColor = tabColors[Math.floor(Math.random() * tabColors.length)];
  names.forEach((rawTabName, i) => {
    let tabName = rawTabName.trim();
    if (tabName === '') {
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
    sheet.appendRow(['TITLE:', rawTabName]);
    if (answerRefs[i]) {
      sheet.appendRow(['ANSWER:', answerRefs[i]]);
      sheet.setFrozenRows(2);
      sheet.getRange('1:2').setFontWeight('bold');
      sheet.getRange('B2').setBackground('yellow');
    } else {
      sheet.setFrozenRows(1);
      sheet.getRange('1:1').setFontWeight('bold');
    }
    sheet.setTabColor(tabColor);
  });
}

/**
 * Copy in a hex grid sheet
 */
function addHexGridSheet() {
  const HEX_GRID_TEMPLATE_ID = '1xQSN0mAhn-0LJzuEM2KIxPXFjcNz6o5VWFFwFCtSovA';
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
  range.setHorizontalAlignment('center');
  _addConditionalFormatRules(
    SpreadsheetApp.newConditionalFormatRule()
      .setRanges([range])
      .whenTextEqualTo('/')
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
    throw new Error('Please select more than 1 row');
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
    'How many columns?',
    'Enter a number of columns. ' +
      'Consider leaving a couple columns of buffer room ' +
      '(i.e., for a 15x15 puzzle, make 17 columns)',
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
    'Setting Cell Size',
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
  if (response == null || response.trim() == '') {
    return false;
  }
  return true;
}

function showMetadataAsNote() {
  SpreadsheetApp.getActiveRange()?.setNote(_getMetadataNote());
  populateMenus();
}

function onEdit(e) {
  const user = _getUser();
  if (user == null) {
    return;
  }
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const time_value = JSON.stringify({'t': _unixtime()});
  _upsertMetadata(spreadsheet, `PB_ACTIVITY:${user}`, time_value);
  _upsertMetadata(SpreadsheetApp.getActiveSheet(), `PB_SHEET`, time_value);
  if (_isAdmin() && spreadsheet.getName().includes('[DEBUG]')) {
    e?.range?.setNote(_getMetadataNote());
  }
}

function _upsertMetadata(target, key, value) {
  if (!target) {
    return;
  }
  const metadata = target.getDeveloperMetadata().find(m => m.getKey() === key);
  if (metadata) {
    metadata.setValue(value);
  } else {
    target.addDeveloperMetadata(key, value);
  }
}

/**
 * Triggers
 * * From spreadsheet - On change
 * * Time-based: every minute
 */
function updateSpreadsheetStats() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const value = JSON.stringify({
    't': _unixtime(),
    'num_sheets': spreadsheet.getNumSheets(),
  });
  _upsertMetadata(spreadsheet, `PB_SPREADSHEET`, value);
}

function _getUser() {
  return Session.getActiveUser().getEmail().split('@')?.[0] || null;
}

function _isAdmin() {
  return ['dannybd', 'bigjimmy', 'benoc', 'juang'].includes(_getUser());
}

function _unixtime() {
  return Math.floor(Date.now() / 1000);
}

function _getMetadataNote() {
  let note = `Last modified: ${new Date()}\n` +
    `Timestamp = ${_unixtime()}\n` +
    `user = ${_getUser()}\n\n` +
    `Spreadsheet metadata:\n`;
  note += SpreadsheetApp.getActiveSpreadsheet().getDeveloperMetadata()
    .map((m, i) => ` #${i}: ${m.getKey()} => ${m.getValue()}`)
    .join('\n');
  note += `\n\nSheet metadata:\n`;
  note += SpreadsheetApp.getActiveSheet()?.getDeveloperMetadata()
    ?.map((m, i) => ` #${i}: ${m.getKey()} => ${m.getValue()}`)
    ?.join('\n') || '[none]';
  return note;
}

function _maybeAddDebug(menu) {
  if (!_isAdmin()) {
    return menu;
  }
  return menu
    .addSeparator()
    .addItem('🐞 [DEBUG] Show metadata', 'showMetadataAsNote');
}

/** @OnlyCurrentDoc */
/**
 * Puzzle Tools Add-on
 *
 * Puzzle-solving utilities for Google Sheets, created by Jason Juang.
 * This file is stored in the repository for reference and can be deployed
 * to puzzle sheets via the Apps Script API.
 *
 * Configuration:
 * - Store this code in the GOOGLE_APPS_SCRIPT_CODE config value
 * - The pbgooglelib.py activate_puzzle_sheet_via_api() function will deploy it
 */

// Colors from the standard Sheets color picker.
const BLACK = "#000000";
const DARK_GRAY_1 = "#b7b7b7";

function onInstall(e) {
  onOpen(e);
}

function onOpen(e) {
  if (e && e.authMode == "NONE") {
    // If this is an add-on, it may not have been enabled for this sheet yet, so we add
    // just a single option to the menu, which will kickstart the add-on and add the rest
    // of the menu options when selected.
    _getSpreadsheetUI().createMenu('Puzzle Tools')
    .addItem('Enable for this sheet', '_updateMenus')
    .addToUi();
  } else {
    _updateMenus();
  }
}

/**
 * Helper function used to add all the menu options for this script.
 */
function _updateMenus() {
  _getSpreadsheetUI().createMenu('Puzzle Tools')
  .addItem('Square Cells', 'squareCells')
  .addSubMenu(_getSpreadsheetUI().createMenu('Symmetrify Grid')
              .addItem('Rotationally', 'doRotationalSymmetrification')
              .addItem('Bilaterally', 'doBilateralSymmetrification'))
  .addItem('Quick-Add Named Tabs', 'doAddNamedTabs')
  .addSubMenu(_getSpreadsheetUI().createMenu('Formatting Shortcuts')
              .addItem('Crossword grid', 'doCrosswordFormatting'))
  .addItem('Delete Blank Rows In Selection', 'deleteBlankRows')
  .addToUi();
}

/**
 * Ask the user for a set of comma-delimited names and make tabs with the names.
 */
function doAddNamedTabs() {
  var ui = _getSpreadsheetUI();
  var result = ui.prompt("Adding Tabs","Enter a comma-delimited list of tab names.", ui.ButtonSet.OK_CANCEL);
  if (_shouldContinueFromDialog(result)) {
    var names = result.getResponseText();
    if (names == null || names == "") {
      return;
    }
    var spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    var tabNames = names.split(",");
    tabNames.forEach( function(tabName) {spreadsheet.insertSheet(tabName.trim());} );
  }
}

/**
 * Given a set of cells, ensure that cells are reflected at the 180-degree point.
 * In other words, a cell in the upper left will get the same color in the lower right.
 */
function doRotationalSymmetrification() {
  var cells = _getActiveRange();
  _doSymmetrification(Math.ceil(cells.getNumRows()/2), cells.getNumColumns(),
                      function(seedRow, seedColumn, selectedCells) {
                        // find rotationally symmetric cell. Which is the total number of rows minus the current row minus 1
                        // if we're in row 1 above in a 5-row grid, we want the mirror row to be 5 - (1 - 1) = 5
                        // if we're in row 2, we want the mirror row to be 5 - (2 - 1) = 4
                        // and if we're in row 3, we want the mirror row to be (5 - (3 - 1)) = 3
                        // the same logic applies to the columns
                        return selectedCells.getCell(selectedCells.getNumRows() - (seedRow - 1),
                                                     selectedCells.getNumColumns() - (seedColumn - 1));
                      });
}

/**
 * Given a set of cells, ensure that cells to the right of the central column mirror the ones on the left side.
 */
function doBilateralSymmetrification() {
  var cells = _getActiveRange();
  _doSymmetrification(cells.getNumRows(), Math.ceil(cells.getNumColumns()/2),
                      function(seedRow, seedColumn, selectedCells) {
                        return selectedCells.getCell(seedRow,
                                                     selectedCells.getNumColumns() - (seedColumn - 1));
                      });

}

/**
 * Symmetrify the grid based on the passed-in parameters.
 *
 * @param {Number} the max row to look at (relative to the range upper-left)
 * @param {Number} the max column to look at (relative to the range upper-left)
 * @param {Function} a callback function that takes row, column of a given cell, and selectedCells and returns the _mirroring_ cell to affect
 */
function _doSymmetrification(maxRow, maxColumn, callback) {
  var cells = _getActiveRange();
  var topRow = cells.getRow();
  var leftColumn = cells.getColumn();
  for (var curRelativeRow = 1; curRelativeRow <= maxRow; curRelativeRow++) {
    for (var curRelativeColumn = 1; curRelativeColumn <= maxColumn; curRelativeColumn++) {
      var currentCell = cells.getCell(curRelativeRow, curRelativeColumn);

      var mirrorCell = callback(curRelativeRow, curRelativeColumn, cells);
      // this gives a substantial (4x in quick tests) speedup, since setting the background color causes a refresh
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
  let sheet = SpreadsheetApp.getActiveSheet();
  let range = _getActiveRange();
  // If just a single cell is selected, ask the user how many columns they
  // want, and then select that many whole columns.
  if (range.getWidth() == 1 && range.getHeight() == 1) {
    let numColumns = _getGridWidthFromUser();
    range = sheet.getRange(1, range.getColumn(), sheet.getMaxRows(), numColumns);
  }
  range.setHorizontalAlignment("center");
  _addConditionalFormatRules(
      // An easy way to insert a block.
      SpreadsheetApp.newConditionalFormatRule()
          .setRanges([range])
          .whenTextEqualTo("/")
          .setBackground(BLACK)
          .build(),
      // Make it easier to distinguish clue numbers from letters.
      SpreadsheetApp.newConditionalFormatRule()
          .setRanges([range])
          .whenNumberGreaterThan(0)
          .setFontColor(DARK_GRAY_1)
          .build(),
  );
  // Make cells square
  let height = sheet.getRowHeight(range.getRow());
  sheet.setColumnWidths(range.getColumn(), range.getNumColumns(), height);
}

/**
 * @param {!Array<ConditionalFormatRule>} newRules The rules to add.
 */
function _addConditionalFormatRules(...newRules) {
  let sheet = SpreadsheetApp.getActiveSheet();
  let rules = sheet.getConditionalFormatRules();
  rules.push(...newRules);
  sheet.setConditionalFormatRules(rules);
}

function deleteBlankRows() {
  let range = SpreadsheetApp.getActiveRange();

  if (range.getNumRows() < 2) {
    throw new Error("Please select more than 1 row");
  }

  // Delete from the bottom up, because deleting a row causes the cells below it to shift up.
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
  let ui = _getSpreadsheetUI();
  let dialogResult = ui.prompt(
    "How many columns?",
    "Enter a number of columns. Consider leaving a couple columns of buffer room (i.e., for a 15x15 puzzle, make 17 columns)",
    ui.ButtonSet.OK_CANCEL);
  return _shouldContinueFromDialog(dialogResult) ?
      parseInt(dialogResult.getResponseText()) :
      0;
}

/**
 * Given a set of cells, set their columns and rows to the same size. Useful for a grid of
 * square cells for use with crosswords and so on.
 */
function squareCells() {
  var cells = _getActiveRange();
  var sheet = SpreadsheetApp.getActiveSpreadsheet();
  var startingColumn = cells.getColumn();
  var startingRow = cells.getRow();
  var dialogResult = _getCellSizeResultFromUser();
  if (_shouldContinueFromDialog(dialogResult)) {
     var newCellSize = parseInt(dialogResult.getResponseText());
     // because we need to manipulate the columns within the global context
     // of the sheet, we start at startingColumn and then proceed to
     // startingColumn + the number of columns
     // so starting at 2 for 3 columns would give 2,3,4
     for (var col = startingColumn; col < startingColumn + cells.getNumColumns(); col++) {
        sheet.setColumnWidth(col, newCellSize);
     }
     // see above comment about column counts
     for (var row = startingRow; row < startingRow + cells.getNumRows(); row++) {
       sheet.setRowHeight(row, newCellSize);
     }
  }

}

/**
 * Lays out a series of cells, starting with the active cell to use with a simple substitution key.
 *
 */
function doSetupSimpleSubstitutionKey() {
  var range = _getActiveRange();
  var startRow = range.getRow();
  var startColumn = range.getColumn();
  for (var curRow = startRow; curRow <= startRow + 26; curRow++) {
  }
}

function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}

/**
 * Given a range of cells, rotate the square 90-degrees. Note that this will alert if you don't select a square.
 */
function doRotateGrid() {
  var range = _getActiveRange();
  if (range.getNumRows() != range.getNumColumns()) {
    var ui = _getSpreadsheetUI();
    ui.alert("Selected area must be square.");
    return;
  }
}

/**
 * Gets a cell size from the user
 * @return {Integer} the size the user requested
 */
function _getCellSizeResultFromUser() {
  var ui = _getSpreadsheetUI();
  return ui.prompt("Setting Cell Size","Enter a cell size in pixels", ui.ButtonSet.OK_CANCEL);
}

/**
 * Determines if the dialog result was a cancel.
 * @param {Object} a dialog result.
 * @return true if the user pressed cancel, false if not
 */
function _didPressCancel(dialogResult) {
  var ui = _getSpreadsheetUI();
  return dialogResult.getSelectedButton() == ui.Button.CANCEL;
}

/**
 * Determines if the dialog text is empty.
 * @param {Object} a dialog result
 * @return true if the entered text is empty.
 */
function _isDialogPromptTextEmpty(dialogResult) {
  return dialogResult.getResponseText() == null || dialogResult.getResponseText() == "";
}

/**
 * Determine if the dialog result suggests that the user should continue.
 * @param {Object} the dialog result object
 * @return true if the dialog result suggests something that should continue, false if not.
 */
function _shouldContinueFromDialog(dialogResult) {
  return !(_didPressCancel(dialogResult) || _isDialogPromptTextEmpty(dialogResult));
}

/**
 * Refactored logic for getting the spreadsheet UI.
 * @return SpreadsheetApp UI object
 */
function _getSpreadsheetUI() {
  return SpreadsheetApp.getUi();
}

/**
 * Return the active range of cells.
 * Refactored code.
 */
function _getActiveRange() {
  return  SpreadsheetApp.getActiveRange();
}

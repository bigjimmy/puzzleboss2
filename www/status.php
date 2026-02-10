<?php
require('puzzlebosslib.php');
$uid = getauthenticateduser();
$solver = getauthenticatedsolver();
?>
<!DOCTYPE html>
<html>
<head>
    <title>Hunt Status Overview</title>
    <link rel="stylesheet" href="./pb-ui.css">
</head>
<body class="status-page">
    <div id="app">
        <div class="status-header">
            <h1>Hunt Status Overview</h1>
            <div :class="updateState"></div>
        </div>

        <?= render_navbar('status') ?>

        <div class="stats-grid">
            <div class="info-box stats-card">
                <div class="info-box-header" @click="showHuntProgress = !showHuntProgress">
                    <span class="collapse-icon" :class="{ collapsed: !showHuntProgress }">▼</span>
                    <h3>Hunt Progress</h3>
                </div>
                <div class="info-box-content" v-show="showHuntProgress">
                    <table>
                        <tr>
                            <th></th>
                            <th>Opened</th>
                            <th>Solved</th>
                            <th>Unsolved</th>
                        </tr>
                        <tr>
                            <th>Rounds</th>
                            <td>{{ stats.totalRounds }}</td>
                            <td>{{ stats.solvedRounds }}</td>
                            <td>{{ stats.totalRounds - stats.solvedRounds }}</td>
                        </tr>
                        <tr>
                            <th>Puzzles</th>
                            <td>{{ stats.totalPuzzles }}</td>
                            <td>{{ stats.solvedPuzzles }}</td>
                            <td>{{ stats.totalPuzzles - stats.solvedPuzzles }}</td>
                        </tr>
                    </table>
                </div>
            </div>

            <div class="info-box stats-card">
                <div class="info-box-header" @click="showStatusBreakdown = !showStatusBreakdown">
                    <span class="collapse-icon" :class="{ collapsed: !showStatusBreakdown }">▼</span>
                    <h3>Status Breakdown</h3>
                </div>
                <div class="info-box-content" v-show="showStatusBreakdown">
                    <table>
                        <tr>
                            <th>Status</th>
                            <th>Count</th>
                        </tr>
                        <tr v-for="status in displayStatuses" :key="status.name || status">
                            <td>{{ (status.emoji || '') + ' ' + (status.name || status) }}</td>
                            <td>{{ statusCounts[status.name || status] || 0 }}</td>
                        </tr>
                    </table>
                </div>
            </div>
        </div>

        <!-- Hint Queue Section -->
        <div class="info-box hint-queue-section" v-if="hints.length > 0">
            <div class="info-box-header" @click="showHintQueue = !showHintQueue">
                <span class="collapse-icon" :class="{ collapsed: !showHintQueue }">▼</span>
                <h3>Hint Queue</h3>
                <span class="badge">{{ hints.length }} pending</span>
            </div>
            <div class="info-box-content" v-show="showHintQueue">
                <table class="hint-table">
                    <tr>
                        <th>#</th>
                        <th>Status</th>
                        <th>Puzzle</th>
                        <th>Requested By</th>
                        <th>Request</th>
                        <th>Submitted</th>
                        <th>Actions</th>
                    </tr>
                    <tr v-for="hint in hints" :key="hint.id"
                        :class="{ 'hint-top': hint.queue_position === 1 }">
                        <td>{{ hint.queue_position }}</td>
                        <td>
                            <span v-if="hint.queue_position === 1">📨 Submitted</span>
                            <span v-else>⏳ Queued</span>
                        </td>
                        <td>
                            <a v-if="getPuzzleUri(hint.puzzle_id)"
                               :href="getPuzzleUri(hint.puzzle_id)" target="_blank">
                                {{ hint.puzzle_name || 'Puzzle #' + hint.puzzle_id }}
                            </a>
                            <span v-else>{{ hint.puzzle_name || 'Puzzle #' + hint.puzzle_id }}</span>
                        </td>
                        <td>{{ hint.solver }}</td>
                        <td class="hint-text-cell">
                            <span class="hint-preview" @click="showHintDetail(hint)">
                                {{ hint.request_text.length > 80 ? hint.request_text.substring(0, 80) + '...' : hint.request_text }}
                            </span>
                        </td>
                        <td>{{ formatHintTime(hint.created_at) }}</td>
                        <td class="hint-actions">
                            <button v-if="hint.queue_position === 1"
                                    class="btn-hint-answer" @click="answerHint(hint.id)"
                                    title="Mark as answered">✅ Answered</button>
                            <button v-if="hint.queue_position === 1 && hints.length > 1"
                                    class="btn-hint-demote" @click="demoteHint(hint.id)"
                                    title="Move down in queue">⬇ Demote</button>
                            <button class="btn-hint-delete" @click="deleteHint(hint.id)"
                                    title="Remove from queue">✕</button>
                        </td>
                    </tr>
                </table>

            </div>
        </div>

        <!-- Hint detail dialog (view existing hint) -->
        <dialog ref="hintDialog" class="hint-detail-dialog" @click.self="$refs.hintDialog.close()">
            <div v-if="selectedHint">
                <h3>Hint Request Details</h3>
                <p><strong>Puzzle:</strong> {{ selectedHint.puzzle_name }}</p>
                <p><strong>Requested by:</strong> {{ selectedHint.solver }}</p>
                <p><strong>Submitted:</strong> {{ formatHintTime(selectedHint.created_at) }}</p>
                <div class="hint-full-text">{{ selectedHint.request_text }}</div>
                <div class="modal-actions">
                    <button class="btn-secondary" @click="$refs.hintDialog.close()">Close</button>
                </div>
            </div>
        </dialog>

        <!-- Hint submit dialog (new hint from puzzle row) -->
        <dialog ref="hintSubmitDialog" class="hint-submit-dialog" @click.self="closeHintModal()">
            <div v-if="hintModalPuzzle">
                <h3>Request Hint for {{ hintModalPuzzle.name }}</h3>
                <p class="hint-modal-info">This will add a hint request to the queue. Describe what you've tried and where you're stuck.</p>
                <textarea v-model="newHintText" ref="hintTextarea"
                          placeholder="We have tried... and are stuck on..."
                          rows="4" class="hint-textarea"></textarea>
                <div class="modal-actions">
                    <button class="btn-secondary" @click="closeHintModal()">Cancel</button>
                    <button class="btn-hint-submit" @click="submitHintFromModal()" :disabled="!newHintText.trim()">Add to Queue</button>
                </div>
            </div>
        </dialog>

        <div class="info-box column-visibility">
            <div class="info-box-header" @click="showColumnVisibility = !showColumnVisibility">
                <span class="collapse-icon" :class="{ collapsed: !showColumnVisibility }">▼</span>
                <h3>Column Visibility</h3>
            </div>
            <div class="info-box-content" v-show="showColumnVisibility">
                <div class="controls-section" style="flex-wrap: wrap;">
                    <div class="filter" :class="{ active: visibleColumns.round }" @click="visibleColumns.round = !visibleColumns.round">Round <input type="checkbox" :checked="visibleColumns.round" @change="visibleColumns.round = !visibleColumns.round" @click.stop /></div>
                    <div class="filter" :class="{ active: visibleColumns.status }" @click="visibleColumns.status = !visibleColumns.status">Status <input type="checkbox" :checked="visibleColumns.status" @change="visibleColumns.status = !visibleColumns.status" @click.stop /></div>
                    <div class="filter" :class="{ active: visibleColumns.doc }" @click="visibleColumns.doc = !visibleColumns.doc">Doc (📊) <input type="checkbox" :checked="visibleColumns.doc" @change="visibleColumns.doc = !visibleColumns.doc" @click.stop /></div>
                    <div class="filter" :class="{ active: visibleColumns.sheetcount }" @click="visibleColumns.sheetcount = !visibleColumns.sheetcount">Sheet # <input type="checkbox" :checked="visibleColumns.sheetcount" @change="visibleColumns.sheetcount = !visibleColumns.sheetcount" @click.stop /></div>
                    <div class="filter" :class="{ active: visibleColumns.chat }" @click="visibleColumns.chat = !visibleColumns.chat">Chat (🗣️) <input type="checkbox" :checked="visibleColumns.chat" @change="visibleColumns.chat = !visibleColumns.chat" @click.stop /></div>
                    <div class="filter" :class="{ active: visibleColumns.cursolvers }" @click="visibleColumns.cursolvers = !visibleColumns.cursolvers">Solvers (cur) <input type="checkbox" :checked="visibleColumns.cursolvers" @change="visibleColumns.cursolvers = !visibleColumns.cursolvers" @click.stop /></div>
                    <div class="filter" :class="{ active: visibleColumns.solvers }" @click="visibleColumns.solvers = !visibleColumns.solvers">Solvers (all) <input type="checkbox" :checked="visibleColumns.solvers" @change="visibleColumns.solvers = !visibleColumns.solvers" @click.stop /></div>
                    <div class="filter" :class="{ active: visibleColumns.location }" @click="visibleColumns.location = !visibleColumns.location">Location <input type="checkbox" :checked="visibleColumns.location" @change="visibleColumns.location = !visibleColumns.location" @click.stop /></div>
                    <div class="filter" :class="{ active: visibleColumns.tags }" @click="visibleColumns.tags = !visibleColumns.tags">Tags <input type="checkbox" :checked="visibleColumns.tags" @change="visibleColumns.tags = !visibleColumns.tags" @click.stop /></div>
                    <div class="filter" :class="{ active: visibleColumns.comment }" @click="visibleColumns.comment = !visibleColumns.comment">Comment <input type="checkbox" :checked="visibleColumns.comment" @change="visibleColumns.comment = !visibleColumns.comment" @click.stop /></div>
                    <div class="toggle-row">
                        <button class="btn-secondary" @click="showAllColumns">Show All</button>
                    </div>
                </div>
            </div>
        </div>

        <div class="puzzle-table">
            <div class="info-box-header section-header" @click="showNoLoc = !showNoLoc">
                <span class="collapse-icon" :class="{ collapsed: !showNoLoc }">▼</span>
                <h2>Unsolved Puzzles Missing Location</h2>
                <span class="badge">{{ noLocPuzzles.length }} puzzles</span>
            </div>
            <table v-show="showNoLoc">
                <tr>
                    <th data-tooltip="Edit">⚙️</th>
                    <th @click="toggleSort('noLoc', 'round')" :class="{ 'hidden-column': !visibleColumns.round }">Round <span class="sort-icon">{{ getSortIcon('noLoc', 'round') }}</span></th>
                    <th @click="toggleSort('noLoc', 'name')">Name <span class="sort-icon">{{ getSortIcon('noLoc', 'name') }}</span></th>
                    <th @click="toggleSort('noLoc', 'status')" :class="{ 'hidden-column': !visibleColumns.status }">Status <span class="sort-icon">{{ getSortIcon('noLoc', 'status') }}</span></th>
                    <th data-tooltip="Spreadsheet" :class="{ 'hidden-column': !visibleColumns.doc }">📊</th>
                    <th @click="toggleSort('noLoc', 'sheetcount')" data-tooltip="Sheet pages" :class="{ 'hidden-column': !visibleColumns.sheetcount }"># <span class="sort-icon">{{ getSortIcon('noLoc', 'sheetcount') }}</span></th>
                    <th data-tooltip="Discord" :class="{ 'hidden-column': !visibleColumns.chat }">🗣️</th>
                    <th @click="toggleSort('noLoc', 'cursolvers')" :class="{ 'hidden-column': !visibleColumns.cursolvers }">Solvers (cur) <span class="sort-icon">{{ getSortIcon('noLoc', 'cursolvers') }}</span></th>
                    <th @click="toggleSort('noLoc', 'solvers')" :class="{ 'hidden-column': !visibleColumns.solvers }">Solvers (all) <span class="sort-icon">{{ getSortIcon('noLoc', 'solvers') }}</span></th>
                    <th @click="toggleSort('noLoc', 'location')" :class="{ 'hidden-column': !visibleColumns.location }">Location <span class="sort-icon">{{ getSortIcon('noLoc', 'location') }}</span></th>
                    <th @click="toggleSort('noLoc', 'tags')" :class="{ 'hidden-column': !visibleColumns.tags }">Tags <span class="sort-icon">{{ getSortIcon('noLoc', 'tags') }}</span></th>
                    <th @click="toggleSort('noLoc', 'comment')" :class="{ 'hidden-column': !visibleColumns.comment }">Comment <span class="sort-icon">{{ getSortIcon('noLoc', 'comment') }}</span></th>
                    <th data-tooltip="Request hint">Hint</th>
                </tr>
                <tr v-for="puzzle in noLocPuzzles"
                    :key="puzzle.id"
                    :class="getPuzzleRowClass(puzzle)"
                    :id="'puzzle-noloc-' + puzzle.id">
                    <td>
                        <a :href="'editpuzzle.php?pid=' + puzzle.id" target="_blank" class="gear-icon" data-tooltip="Edit puzzle">⚙️</a>
                    </td>
                    <td :class="{ 'hidden-column': !visibleColumns.round }">{{ getRoundName(puzzle.id) }}</td>
                    <td><a :href="puzzle.puzzle_uri" target="_blank">{{ puzzle.name }}</a></td>
                    <td :data-tooltip="'Status: ' + statusEdits[puzzle.id]" :class="{ 'hidden-column': !visibleColumns.status }">
                        <select v-model="statusEdits[puzzle.id]" @change="updateStatus(puzzle.id)">
                            <option v-for="status in selectableStatuses" :key="status.name || status" :value="status.name || status" :title="status.name || status">
                                {{ status.emoji || (status.name || status) }}
                            </option>
                        </select>
                    </td>
                    <td :class="{ 'hidden-column': !visibleColumns.doc }"><a :href="puzzle.drive_uri" target="_blank" data-tooltip="Spreadsheet">📊</a></td>
                    <td :class="{ 'hidden-column': !visibleColumns.sheetcount }">{{ puzzle.sheetcount || 0 }}</td>
                    <td :class="{ 'hidden-column': !visibleColumns.chat }"><a :href="puzzle.chat_channel_link" target="_blank" data-tooltip="Discord">🗣️</a></td>
                    <td class="solver-col" :class="{ 'hidden-column': !visibleColumns.cursolvers }">
                        <div v-for="solver in formatSolvers(puzzle.cursolvers)" :key="solver">{{ solver }}</div>
                    </td>
                    <td class="solver-col" :class="{ 'hidden-column': !visibleColumns.solvers }">
                        <div v-for="solver in formatSolvers(puzzle.solvers)" :key="solver">{{ solver }}</div>
                    </td>
                    <td class="location-col" :class="{ 'hidden-column': !visibleColumns.location }">
                        <div v-if="puzzle.xyzloc" class="cell-display">{{ puzzle.xyzloc }}</div>
                        <div class="inline-group">
                            <input type="text"
                                   v-model="locationEdits[puzzle.id]"
                                   placeholder="Set location..."
                                   @keyup.enter="updateLocation(puzzle.id)">
                            <button @click="updateLocation(puzzle.id)" :disabled="saving[puzzle.id]">
                                {{ saving[puzzle.id] ? '...' : 'Save' }}
                            </button>
                        </div>
                    </td>
                    <td class="tags-col" :class="{ 'hidden-column': !visibleColumns.tags }">{{ formatTags(puzzle.tags) }}</td>
                    <td class="comment-col" :class="{ 'hidden-column': !visibleColumns.comment }">
                        <div v-if="puzzle.comments" class="cell-display comment-display">{{ puzzle.comments }}</div>
                        <div class="inline-group">
                            <input type="text"
                                   v-model="commentEdits[puzzle.id]"
                                   placeholder="Update comment..."
                                   @keyup.enter="updateComment(puzzle.id)">
                            <button @click="updateComment(puzzle.id)" :disabled="saving[puzzle.id]">
                                {{ saving[puzzle.id] ? '...' : 'Save' }}
                            </button>
                        </div>
                    </td>
                    <td><button class="btn-hint-inline" @click="openHintModal(puzzle)" data-tooltip="Request hint">💡</button></td>
                </tr>
            </table>
        </div>

        <div class="puzzle-table" v-if="sheetDisabledPuzzles.length > 0">
            <div class="info-box-header section-header" @click="showSheetDisabled = !showSheetDisabled">
                <span class="collapse-icon" :class="{ collapsed: !showSheetDisabled }">▼</span>
                <h2>Puzzles Without Sheet Tracking Enabled</h2>
                <span class="badge">{{ sheetDisabledPuzzles.length }} puzzles</span>
            </div>
            <table v-show="showSheetDisabled">
                <tr>
                    <th data-tooltip="Edit">⚙️</th>
                    <th @click="toggleSort('sheetDisabled', 'round')" :class="{ 'hidden-column': !visibleColumns.round }">Round <span class="sort-icon">{{ getSortIcon('sheetDisabled', 'round') }}</span></th>
                    <th @click="toggleSort('sheetDisabled', 'name')">Name <span class="sort-icon">{{ getSortIcon('sheetDisabled', 'name') }}</span></th>
                    <th @click="toggleSort('sheetDisabled', 'status')" :class="{ 'hidden-column': !visibleColumns.status }">Status <span class="sort-icon">{{ getSortIcon('sheetDisabled', 'status') }}</span></th>
                    <th data-tooltip="Spreadsheet" :class="{ 'hidden-column': !visibleColumns.doc }">📊</th>
                    <th @click="toggleSort('sheetDisabled', 'sheetcount')" data-tooltip="Sheet pages" :class="{ 'hidden-column': !visibleColumns.sheetcount }"># <span class="sort-icon">{{ getSortIcon('sheetDisabled', 'sheetcount') }}</span></th>
                    <th data-tooltip="Discord" :class="{ 'hidden-column': !visibleColumns.chat }">🗣️</th>
                    <th @click="toggleSort('sheetDisabled', 'cursolvers')" :class="{ 'hidden-column': !visibleColumns.cursolvers }">Solvers (cur) <span class="sort-icon">{{ getSortIcon('sheetDisabled', 'cursolvers') }}</span></th>
                    <th @click="toggleSort('sheetDisabled', 'solvers')" :class="{ 'hidden-column': !visibleColumns.solvers }">Solvers (all) <span class="sort-icon">{{ getSortIcon('sheetDisabled', 'solvers') }}</span></th>
                    <th @click="toggleSort('sheetDisabled', 'location')" :class="{ 'hidden-column': !visibleColumns.location }">Location <span class="sort-icon">{{ getSortIcon('sheetDisabled', 'location') }}</span></th>
                    <th @click="toggleSort('sheetDisabled', 'tags')" :class="{ 'hidden-column': !visibleColumns.tags }">Tags <span class="sort-icon">{{ getSortIcon('sheetDisabled', 'tags') }}</span></th>
                    <th @click="toggleSort('sheetDisabled', 'comment')" :class="{ 'hidden-column': !visibleColumns.comment }">Comment <span class="sort-icon">{{ getSortIcon('sheetDisabled', 'comment') }}</span></th>
                    <th data-tooltip="Request hint">Hint</th>
                </tr>
                <tr v-for="puzzle in sheetDisabledPuzzles"
                    :key="puzzle.id"
                    :class="getPuzzleRowClass(puzzle)"
                    :id="'puzzle-sheet-' + puzzle.id">
                    <td>
                        <a :href="'editpuzzle.php?pid=' + puzzle.id" target="_blank" class="gear-icon" data-tooltip="Edit puzzle">⚙️</a>
                    </td>
                    <td :class="{ 'hidden-column': !visibleColumns.round }">{{ getRoundName(puzzle.id) }}</td>
                    <td><a :href="puzzle.puzzle_uri" target="_blank">{{ puzzle.name }}</a></td>
                    <td :data-tooltip="'Status: ' + statusEdits[puzzle.id]" :class="{ 'hidden-column': !visibleColumns.status }">
                        <select v-model="statusEdits[puzzle.id]" @change="updateStatus(puzzle.id)">
                            <option v-for="status in selectableStatuses" :key="status.name || status" :value="status.name || status" :title="status.name || status">
                                {{ status.emoji || (status.name || status) }}
                            </option>
                        </select>
                    </td>
                    <td :class="{ 'hidden-column': !visibleColumns.doc }"><a :href="puzzle.drive_uri" target="_blank" data-tooltip="Spreadsheet">📊</a></td>
                    <td :class="{ 'hidden-column': !visibleColumns.sheetcount }">{{ puzzle.sheetcount || 0 }}</td>
                    <td :class="{ 'hidden-column': !visibleColumns.chat }"><a :href="puzzle.chat_channel_link" target="_blank" data-tooltip="Discord">🗣️</a></td>
                    <td class="solver-col" :class="{ 'hidden-column': !visibleColumns.cursolvers }">
                        <div v-for="solver in formatSolvers(puzzle.cursolvers)" :key="solver">{{ solver }}</div>
                    </td>
                    <td class="solver-col" :class="{ 'hidden-column': !visibleColumns.solvers }">
                        <div v-for="solver in formatSolvers(puzzle.solvers)" :key="solver">{{ solver }}</div>
                    </td>
                    <td class="location-col" :class="{ 'hidden-column': !visibleColumns.location }">
                        <div v-if="puzzle.xyzloc" class="cell-display">{{ puzzle.xyzloc }}</div>
                        <div class="inline-group">
                            <input type="text"
                                   v-model="locationEdits[puzzle.id]"
                                   placeholder="Set location..."
                                   @keyup.enter="updateLocation(puzzle.id)">
                            <button @click="updateLocation(puzzle.id)" :disabled="saving[puzzle.id]">
                                {{ saving[puzzle.id] ? '...' : 'Save' }}
                            </button>
                        </div>
                    </td>
                    <td class="tags-col" :class="{ 'hidden-column': !visibleColumns.tags }">{{ formatTags(puzzle.tags) }}</td>
                    <td class="comment-col" :class="{ 'hidden-column': !visibleColumns.comment }">
                        <div v-if="puzzle.comments" class="cell-display comment-display">{{ puzzle.comments }}</div>
                        <div class="inline-group">
                            <input type="text"
                                   v-model="commentEdits[puzzle.id]"
                                   placeholder="Update comment..."
                                   @keyup.enter="updateComment(puzzle.id)">
                            <button @click="updateComment(puzzle.id)" :disabled="saving[puzzle.id]">
                                {{ saving[puzzle.id] ? '...' : 'Save' }}
                            </button>
                        </div>
                    </td>
                    <td><button class="btn-hint-inline" @click="openHintModal(puzzle)" data-tooltip="Request hint">💡</button></td>
                </tr>
            </table>
        </div>

        <div class="puzzle-table">
            <div class="info-box-header section-header" @click="showOverview = !showOverview">
                <span class="collapse-icon" :class="{ collapsed: !showOverview }">▼</span>
                <h2>Total Hunt Overview</h2>
                <span class="badge">{{ workOnPuzzles.length }} puzzles</span>
            </div>
            <table v-show="showOverview">
                <tr>
                    <th data-tooltip="Edit">⚙️</th>
                    <th @click="toggleSort('overview', 'round')" :class="{ 'hidden-column': !visibleColumns.round }">Round <span class="sort-icon">{{ getSortIcon('overview', 'round') }}</span></th>
                    <th @click="toggleSort('overview', 'name')">Name <span class="sort-icon">{{ getSortIcon('overview', 'name') }}</span></th>
                    <th @click="toggleSort('overview', 'status')" :class="{ 'hidden-column': !visibleColumns.status }">Status <span class="sort-icon">{{ getSortIcon('overview', 'status') }}</span></th>
                    <th data-tooltip="Spreadsheet" :class="{ 'hidden-column': !visibleColumns.doc }">📊</th>
                    <th @click="toggleSort('overview', 'sheetcount')" data-tooltip="Sheet pages" :class="{ 'hidden-column': !visibleColumns.sheetcount }"># <span class="sort-icon">{{ getSortIcon('overview', 'sheetcount') }}</span></th>
                    <th data-tooltip="Discord" :class="{ 'hidden-column': !visibleColumns.chat }">🗣️</th>
                    <th @click="toggleSort('overview', 'cursolvers')" :class="{ 'hidden-column': !visibleColumns.cursolvers }">Solvers (cur) <span class="sort-icon">{{ getSortIcon('overview', 'cursolvers') }}</span></th>
                    <th @click="toggleSort('overview', 'solvers')" :class="{ 'hidden-column': !visibleColumns.solvers }">Solvers (all) <span class="sort-icon">{{ getSortIcon('overview', 'solvers') }}</span></th>
                    <th @click="toggleSort('overview', 'location')" :class="{ 'hidden-column': !visibleColumns.location }">Location <span class="sort-icon">{{ getSortIcon('overview', 'location') }}</span></th>
                    <th @click="toggleSort('overview', 'tags')" :class="{ 'hidden-column': !visibleColumns.tags }">Tags <span class="sort-icon">{{ getSortIcon('overview', 'tags') }}</span></th>
                    <th @click="toggleSort('overview', 'comment')" :class="{ 'hidden-column': !visibleColumns.comment }">Comment <span class="sort-icon">{{ getSortIcon('overview', 'comment') }}</span></th>
                    <th data-tooltip="Request hint">Hint</th>
                </tr>
                <tr v-for="puzzle in workOnPuzzles"
                    :key="puzzle.id"
                    :class="getPuzzleRowClass(puzzle)"
                    :id="'puzzle-overview-' + puzzle.id">
                    <td>
                        <a :href="'editpuzzle.php?pid=' + puzzle.id" target="_blank" class="gear-icon" data-tooltip="Edit puzzle">⚙️</a>
                    </td>
                    <td :class="{ 'hidden-column': !visibleColumns.round }">{{ getRoundName(puzzle.id) }}</td>
                    <td><a :href="puzzle.puzzle_uri" target="_blank">{{ puzzle.name }}</a></td>
                    <td :data-tooltip="'Status: ' + statusEdits[puzzle.id]" :class="{ 'hidden-column': !visibleColumns.status }">
                        <select v-model="statusEdits[puzzle.id]" @change="updateStatus(puzzle.id)">
                            <option v-for="status in selectableStatuses" :key="status.name || status" :value="status.name || status" :title="status.name || status">
                                {{ status.emoji || (status.name || status) }}
                            </option>
                        </select>
                    </td>
                    <td :class="{ 'hidden-column': !visibleColumns.doc }"><a :href="puzzle.drive_uri" target="_blank" data-tooltip="Spreadsheet">📊</a></td>
                    <td :class="{ 'hidden-column': !visibleColumns.sheetcount }">{{ puzzle.sheetcount || 0 }}</td>
                    <td :class="{ 'hidden-column': !visibleColumns.chat }"><a :href="puzzle.chat_channel_link" target="_blank" data-tooltip="Discord">🗣️</a></td>
                    <td class="solver-col" :class="{ 'hidden-column': !visibleColumns.cursolvers }">
                        <div v-for="solver in formatSolvers(puzzle.cursolvers)" :key="solver">{{ solver }}</div>
                    </td>
                    <td class="solver-col" :class="{ 'hidden-column': !visibleColumns.solvers }">
                        <div v-for="solver in formatSolvers(puzzle.solvers)" :key="solver">{{ solver }}</div>
                    </td>
                    <td class="location-col" :class="{ 'hidden-column': !visibleColumns.location }">
                        <div v-if="puzzle.xyzloc" class="cell-display">{{ puzzle.xyzloc }}</div>
                        <div class="inline-group">
                            <input type="text"
                                   v-model="locationEdits[puzzle.id]"
                                   placeholder="Set location..."
                                   @keyup.enter="updateLocation(puzzle.id)">
                            <button @click="updateLocation(puzzle.id)" :disabled="saving[puzzle.id]">
                                {{ saving[puzzle.id] ? '...' : 'Save' }}
                            </button>
                        </div>
                    </td>
                    <td class="tags-col" :class="{ 'hidden-column': !visibleColumns.tags }">{{ formatTags(puzzle.tags) }}</td>
                    <td class="comment-col" :class="{ 'hidden-column': !visibleColumns.comment }">
                        <div v-if="puzzle.comments" class="cell-display comment-display">{{ puzzle.comments }}</div>
                        <div class="inline-group">
                            <input type="text"
                                   v-model="commentEdits[puzzle.id]"
                                   placeholder="Update comment..."
                                   @keyup.enter="updateComment(puzzle.id)">
                            <button @click="updateComment(puzzle.id)" :disabled="saving[puzzle.id]">
                                {{ saving[puzzle.id] ? '...' : 'Save' }}
                            </button>
                        </div>
                    </td>
                    <td><button class="btn-hint-inline" @click="openHintModal(puzzle)" data-tooltip="Request hint">💡</button></td>
                </tr>
            </table>
        </div>

        <footer>
            Last updated: {{ lastUpdate }}
        </footer>
    </div>

    <script type="module">
        import { createApp, ref, computed, onMounted, watch } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js'
        import Consts from './consts.js'
        import { onFetchSuccess, onFetchFailure } from './pb-utils.js'

        <?php
            echo "const currentUid = " . json_encode($uid) . ";";
            echo "const currentUsername = " . json_encode($solver->name) . ";";
        ?>

        createApp({
            setup() {
                const data = ref({ rounds: [] })
                const statuses = ref([])
                const updateState = ref('circle stale')
                const lastUpdate = ref('')
                const staleTimer = ref(null)
                
                const showNoLoc = ref(true)
                const showSheetDisabled = ref(true)
                const showOverview = ref(true)
                const showHuntProgress = ref(true)
                const showStatusBreakdown = ref(true)
                const showColumnVisibility = ref(true)

                // Hint queue state
                const hints = ref([])
                const showHintQueue = ref(true)
                const newHintText = ref('')
                const selectedHint = ref(null)
                const hintDialog = ref(null)
                const hintModalPuzzle = ref(null)
                const hintSubmitDialog = ref(null)
                const hintTextarea = ref(null)

                const commentEdits = ref({})
                const locationEdits = ref({})
                const statusEdits = ref({})
                const saving = ref({})

                const sortColumn = ref({
                    noLoc: null,
                    sheetDisabled: null,
                    overview: null
                })
                const sortDirection = ref({
                    noLoc: 'asc',
                    sheetDisabled: 'asc',
                    overview: 'asc'
                })

                // Column visibility with localStorage persistence
                const defaultVisibleColumns = {
                    round: true,
                    status: true,
                    doc: true,
                    sheetcount: true,
                    chat: true,
                    cursolvers: true,
                    solvers: true,
                    location: true,
                    tags: true,
                    comment: true
                }

                const visibleColumns = ref({...defaultVisibleColumns})
                
                // Statuses excluded from count table
                const excludedFromCount = ['[hidden]', 'Solved']
                // Statuses excluded from work-on list
                const excludedFromWorkOn = ['[hidden]', 'Unnecessary', 'Solved']
                // Statuses excluded from dropdown
                const excludedFromDropdown = ['Solved', '[hidden]']
                
                const stats = computed(() => {
                    let totalRounds = 0
                    let solvedRounds = 0
                    let totalPuzzles = 0
                    let solvedPuzzles = 0
                    
                    data.value.rounds.forEach(round => {
                        totalRounds++
                        let roundMetas = 0
                        let roundMetasSolved = 0
                        
                        round.puzzles.forEach(puzzle => {
                            if (puzzle.status === '[hidden]') return
                            totalPuzzles++
                            if (puzzle.status === 'Solved') {
                                solvedPuzzles++
                                if (puzzle.ismeta) roundMetasSolved++
                            }
                            if (puzzle.ismeta) roundMetas++
                        })
                        
                        if (roundMetas > 0 && roundMetas === roundMetasSolved) {
                            solvedRounds++
                        }
                    })
                    
                    return { totalRounds, solvedRounds, totalPuzzles, solvedPuzzles }
                })
                
                const statusCounts = computed(() => {
                    const counts = {}
                    data.value.rounds.forEach(round => {
                        round.puzzles.forEach(puzzle => {
                            if (puzzle.status === '[hidden]') return
                            counts[puzzle.status] = (counts[puzzle.status] || 0) + 1
                        })
                    })
                    return counts
                })
                
                const displayStatuses = computed(() => {
                    return statuses.value.filter(s => !excludedFromCount.includes(s.name || s))
                })

                const selectableStatuses = computed(() => {
                    return statuses.value.filter(s => !excludedFromDropdown.includes(s.name || s))
                })

                function getStatusEmoji(statusName) {
                    const status = statuses.value.find(s => (s.name || s) === statusName)
                    return status?.emoji || ''
                }

                function toggleSort(section, column) {
                    if (sortColumn.value[section] === column) {
                        // Toggle direction
                        sortDirection.value[section] = sortDirection.value[section] === 'asc' ? 'desc' : 'asc'
                    } else {
                        // New column, default to ascending
                        sortColumn.value[section] = column
                        sortDirection.value[section] = 'asc'
                    }
                }

                function getSortIcon(section, column) {
                    if (sortColumn.value[section] !== column) return ''
                    return sortDirection.value[section] === 'asc' ? '▲' : '▼'
                }

                function loadColumnVisibility() {
                    try {
                        const saved = localStorage.getItem('statusPageColumnVisibility')
                        if (saved) {
                            const parsed = JSON.parse(saved)
                            Object.assign(visibleColumns.value, parsed)
                        }
                    } catch (e) {
                        console.error('Failed to load column visibility:', e)
                    }
                }

                function saveColumnVisibility() {
                    try {
                        localStorage.setItem('statusPageColumnVisibility', JSON.stringify(visibleColumns.value))
                    } catch (e) {
                        console.error('Failed to save column visibility:', e)
                    }
                }

                function showAllColumns() {
                    Object.keys(visibleColumns.value).forEach(key => {
                        visibleColumns.value[key] = true
                    })
                }
                
                const allPuzzles = computed(() => {
                    const puzzles = []
                    data.value.rounds.forEach(round => {
                        round.puzzles.forEach(puzzle => {
                            if (puzzle.status !== '[hidden]') {
                                puzzles.push({ ...puzzle, roundName: round.name })
                            }
                        })
                    })
                    return puzzles
                })
                
                function countSolvers(solverString) {
                    if (!solverString) return 0
                    return solverString.split(',').filter(s => s.trim()).length
                }

                function sortPuzzles(puzzles, section) {
                    const col = sortColumn.value[section]
                    const dir = sortDirection.value[section]
                    if (!col) return puzzles

                    return [...puzzles].sort((a, b) => {
                        let aVal, bVal

                        switch(col) {
                            case 'round':
                                aVal = getRoundName(a.id)
                                bVal = getRoundName(b.id)
                                break
                            case 'name':
                                aVal = a.name
                                bVal = b.name
                                break
                            case 'status':
                                aVal = a.status
                                bVal = b.status
                                break
                            case 'sheetcount':
                                aVal = a.sheetcount || 0
                                bVal = b.sheetcount || 0
                                break
                            case 'cursolvers':
                                aVal = countSolvers(a.cursolvers)
                                bVal = countSolvers(b.cursolvers)
                                break
                            case 'solvers':
                                aVal = countSolvers(a.solvers)
                                bVal = countSolvers(b.solvers)
                                break
                            case 'location':
                                aVal = a.xyzloc || ''
                                bVal = b.xyzloc || ''
                                break
                            case 'tags':
                                aVal = a.tags || ''
                                bVal = b.tags || ''
                                break
                            case 'comment':
                                aVal = a.comments || ''
                                bVal = b.comments || ''
                                break
                            default:
                                return 0
                        }

                        // Handle numeric sorting
                        if (typeof aVal === 'number' && typeof bVal === 'number') {
                            return dir === 'asc' ? aVal - bVal : bVal - aVal
                        }

                        // Handle string sorting
                        aVal = String(aVal).toLowerCase()
                        bVal = String(bVal).toLowerCase()
                        if (aVal < bVal) return dir === 'asc' ? -1 : 1
                        if (aVal > bVal) return dir === 'asc' ? 1 : -1
                        return 0
                    })
                }

                const noLocPuzzles = computed(() => {
                    const filtered = allPuzzles.value.filter(p =>
                        !p.xyzloc && p.status !== 'Solved' && p.status !== 'Unnecessary'
                    )
                    return sortPuzzles(filtered, 'noLoc')
                })

                const workOnPuzzles = computed(() => {
                    const filtered = allPuzzles.value.filter(p =>
                        !excludedFromWorkOn.includes(p.status)
                    )
                    return sortPuzzles(filtered, 'overview')
                })

                const sheetDisabledPuzzles = computed(() => {
                    const filtered = allPuzzles.value.filter(p =>
                        (p.sheetenabled === 0 || p.sheetenabled === '0') &&
                        p.status !== 'Solved'
                    )
                    return sortPuzzles(filtered, 'sheetDisabled')
                })
                
                // Hint queue helpers
                function getPuzzleUri(puzzleId) {
                    for (const round of data.value.rounds) {
                        for (const puzzle of round.puzzles) {
                            if (puzzle.id === puzzleId) return puzzle.puzzle_uri
                        }
                    }
                    return null
                }

                function formatHintTime(isoStr) {
                    if (!isoStr) return ''
                    return new Date(isoStr).toLocaleTimeString('en-US', {
                        timeZone: 'America/New_York',
                        hour: '2-digit',
                        minute: '2-digit'
                    })
                }

                function showHintDetail(hint) {
                    selectedHint.value = hint
                    hintDialog.value?.showModal()
                }

                function openHintModal(puzzle) {
                    hintModalPuzzle.value = puzzle
                    newHintText.value = ''
                    hintSubmitDialog.value?.showModal()
                    // Focus textarea after dialog opens
                    setTimeout(() => hintTextarea.value?.focus(), 50)
                }

                function closeHintModal() {
                    hintSubmitDialog.value?.close()
                    hintModalPuzzle.value = null
                    newHintText.value = ''
                }

                async function submitHintFromModal() {
                    if (!hintModalPuzzle.value || !newHintText.value.trim()) return
                    try {
                        await fetch('./apicall.php?apicall=hints', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                puzzle_id: hintModalPuzzle.value.id,
                                solver: currentUsername,
                                request_text: newHintText.value.trim()
                            })
                        })
                        closeHintModal()
                        await fetchData()
                    } catch (e) {
                        console.error('Failed to submit hint:', e)
                        alert('Failed to submit hint request')
                    }
                }

                async function answerHint(hintId) {
                    if (!confirm('Mark this hint as answered? It will be removed from the queue.')) return
                    try {
                        await fetch(`./apicall.php?apicall=hint&apiparam1=${hintId}&apiparam2=answer`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({})
                        })
                        await fetchData()
                    } catch (e) {
                        console.error('Failed to answer hint:', e)
                        alert('Failed to mark hint as answered')
                    }
                }

                async function demoteHint(hintId) {
                    try {
                        await fetch(`./apicall.php?apicall=hint&apiparam1=${hintId}&apiparam2=demote`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({})
                        })
                        await fetchData()
                    } catch (e) {
                        console.error('Failed to demote hint:', e)
                        alert('Failed to demote hint')
                    }
                }

                async function deleteHint(hintId) {
                    if (!confirm('Remove this hint from the queue?')) return
                    try {
                        await fetch(`./apicall.php?apicall=hint&apiparam1=${hintId}`, {
                            method: 'DELETE'
                        })
                        await fetchData()
                    } catch (e) {
                        console.error('Failed to delete hint:', e)
                        alert('Failed to delete hint')
                    }
                }

                function getRoundName(puzzleId) {
                    for (const round of data.value.rounds) {
                        for (const puzzle of round.puzzles) {
                            if (puzzle.id === puzzleId) return round.name
                        }
                    }
                    return ''
                }
                
                function getPuzzleRowClass(puzzle) {
                    if (puzzle.status === 'Critical') return 'critical-row'
                    if (puzzle.ismeta && puzzle.status !== 'Critical') return 'meta-row'
                    if (puzzle.status === 'New' && !puzzle.ismeta) return 'new-row'
                    return ''
                }
                
                function formatTags(tags) {
                    // tags comes as a comma-separated string from puzzle_view
                    if (!tags) return ''
                    return tags
                }

                function formatSolvers(solvers) {
                    // solvers comes as a comma-separated string from puzzle_view
                    if (!solvers) return []
                    return solvers.split(',').map(s => s.trim()).filter(s => s)
                }
                
                async function fetchData() {
                    try {
                        const response = await fetch('./apicall.php?apicall=all', { cache: 'no-store' })
                        const newData = await response.json()
                        data.value = newData
                        hints.value = newData.hints || []

                        // Initialize status edits for new puzzles
                        newData.rounds.forEach(round => {
                            round.puzzles.forEach(puzzle => {
                                if (statusEdits.value[puzzle.id] === undefined) {
                                    statusEdits.value[puzzle.id] = puzzle.status
                                }
                            })
                        })
                        
                        // Update status indicator
                        if (staleTimer.value) clearTimeout(staleTimer.value)
                        updateState.value = 'circle active pulse'
                        setTimeout(() => updateState.value = 'circle active', 1000)
                        staleTimer.value = setTimeout(() => updateState.value = 'circle stale', 6000)
                        
                        lastUpdate.value = new Date().toLocaleTimeString('en-US', {
                            timeZone: 'America/New_York',
                            hour: '2-digit',
                            minute: '2-digit',
                            second: '2-digit'
                        })
                        onFetchSuccess()
                    } catch (e) {
                        console.error('Fetch error:', e)
                        if (onFetchFailure()) return
                        updateState.value = 'circle error pulse'
                    }
                }
                
                async function fetchStatuses() {
                    try {
                        const response = await fetch('./apicall.php?apicall=huntinfo')
                        const data = await response.json()
                        // Get statuses from huntinfo with emoji
                        if (data.statuses) {
                            statuses.value = data.statuses
                        } else {
                            // Fallback to names only
                            statuses.value = Consts.statuses.map(name => ({ name, emoji: '' }))
                        }
                    } catch (e) {
                        statuses.value = Consts.statuses.map(name => ({ name, emoji: '' }))
                    }
                }
                
                async function updateComment(puzzleId) {
                    const comment = commentEdits.value[puzzleId]
                    if (comment === undefined || comment === '') return

                    saving.value[puzzleId] = true
                    try {
                        await fetch(`./apicall.php?apicall=puzzle&apiparam1=${puzzleId}&apiparam2=comments`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ comments: comment })
                        })

                        // Flash the row
                        const row = document.getElementById('puzzle-noloc-' + puzzleId) ||
                                    document.getElementById('puzzle-sheet-' + puzzleId) ||
                                    document.getElementById('puzzle-overview-' + puzzleId)
                        if (row) {
                            row.classList.add('flash')
                            setTimeout(() => row.classList.remove('flash'), 500)
                        }

                        // Clear the input and refresh
                        commentEdits.value[puzzleId] = ''
                        await fetchData()
                    } catch (e) {
                        console.error('Update error:', e)
                        alert('Failed to update comment')
                    }
                    saving.value[puzzleId] = false
                }

                async function updateLocation(puzzleId) {
                    const location = locationEdits.value[puzzleId]
                    if (location === undefined || location === '') return

                    saving.value[puzzleId] = true
                    try {
                        await fetch(`./apicall.php?apicall=puzzle&apiparam1=${puzzleId}&apiparam2=xyzloc`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ xyzloc: location })
                        })

                        // Flash the row
                        const row = document.getElementById('puzzle-noloc-' + puzzleId) ||
                                    document.getElementById('puzzle-sheet-' + puzzleId) ||
                                    document.getElementById('puzzle-overview-' + puzzleId)
                        if (row) {
                            row.classList.add('flash')
                            setTimeout(() => row.classList.remove('flash'), 500)
                        }

                        // Clear the input and refresh
                        locationEdits.value[puzzleId] = ''
                        await fetchData()
                    } catch (e) {
                        console.error('Update error:', e)
                        alert('Failed to update location')
                    }
                    saving.value[puzzleId] = false
                }
                
                async function updateStatus(puzzleId) {
                    const status = statusEdits.value[puzzleId]

                    saving.value[puzzleId] = true
                    try {
                        await fetch(`./apicall.php?apicall=puzzle&apiparam1=${puzzleId}&apiparam2=status`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ status: status })
                        })

                        // Flash the row
                        const row = document.getElementById('puzzle-noloc-' + puzzleId) ||
                                    document.getElementById('puzzle-sheet-' + puzzleId) ||
                                    document.getElementById('puzzle-overview-' + puzzleId)
                        if (row) {
                            row.classList.add('flash')
                            setTimeout(() => row.classList.remove('flash'), 500)
                        }

                        await fetchData()
                    } catch (e) {
                        console.error('Update error:', e)
                        alert('Failed to update status')
                    }
                    saving.value[puzzleId] = false
                }
                
                onMounted(async () => {
                    loadColumnVisibility()
                    await fetchStatuses()
                    await fetchData()
                    setInterval(fetchData, 5000)
                })

                watch(visibleColumns, () => {
                    saveColumnVisibility()
                }, { deep: true })
                
                return {
                    data,
                    stats,
                    statusCounts,
                    displayStatuses,
                    selectableStatuses,
                    noLocPuzzles,
                    sheetDisabledPuzzles,
                    workOnPuzzles,
                    updateState,
                    lastUpdate,
                    showNoLoc,
                    showSheetDisabled,
                    showOverview,
                    showHuntProgress,
                    showStatusBreakdown,
                    showColumnVisibility,
                    commentEdits,
                    locationEdits,
                    statusEdits,
                    saving,
                    sortColumn,
                    sortDirection,
                    visibleColumns,
                    getRoundName,
                    getPuzzleRowClass,
                    formatTags,
                    formatSolvers,
                    getStatusEmoji,
                    toggleSort,
                    getSortIcon,
                    showAllColumns,
                    updateComment,
                    updateLocation,
                    updateStatus,
                    // Hint queue
                    hints,
                    showHintQueue,
                    newHintText,
                    selectedHint,
                    hintDialog,
                    hintModalPuzzle,
                    hintSubmitDialog,
                    hintTextarea,
                    getPuzzleUri,
                    formatHintTime,
                    showHintDetail,
                    openHintModal,
                    closeHintModal,
                    submitHintFromModal,
                    answerHint,
                    demoteHint,
                    deleteHint
                }
            }
        }).mount('#app')
    </script>
</body>
</html>

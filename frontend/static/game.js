// This JavaScript file will keep track of Selection,
// Communication, and Rendering.

// Global state for the frontend
let gameState = {
  phase: 'PLACEMENT',
  selectedCell: null
};

document.addEventListener('DOMContentLoaded', () => {
  console.log("Online.");

  const opponentBoard = document.getElementById('opponentBoard');
  const playerBoard = document.getElementById('player-board');
  const actionBtn = document.getElementById('btn-action');

  // Click Handler
  opponentBoard.addEventListener('click', (e) => {
    if (e.target.classList.contains('cell')) {
      // Remove previous selection visual
      document.querySelectorAll('.cell').forEach(c => c.style.outline = 'none');

      // Highligh current selection
      e.target.style.outline = '2px solid var(--ui-cyan)';

      const row = e.target.dataset.row;
      const col = e.target.dataset.col;
      gameState.selectedCell = { row, col };

      addLogEntry('Target Selected: ${String.fromCharCode(65 + parseInt(row))}${parseInt(col) + 1}');
    }
  });

  // Action Button
  actionBtn.addEventListener('click', () => {
    if (!gameState.selectedCell) {
      addLogEntry("ERROR: No target selected.");
      return;
    }

    sendFireRequest(gameState.selectedCell.row, gameState.selectedCell.col);
  });
});

// API Communication


// UI Rendering
function updateUI(snapshot) {
  // Update HUD
  document.getElementById('state-phase').innterText = snapshot.phase;
  document.getElementById('state-turn').innerText = snapshot.turn_count;

  // Loop through grid and update colors.
  // Need to look at how the snapshot grid is structured.
}

// Log Helper
function addLogEntry(msg) {
  const log = document.getElementById('combat-log');
  const entry = document.createElement('div');
  entry.className = 'log-entry';
  entry.innerText = '> ${msg}';
  log.prepend(entry); // Newest on top
}

// This JavaScript file will keep track of Selection,
// Communication, and Rendering.

// Global state for the frontend
let currentSnapshot = null;
let selectedCell = null;

document.addEventListener('DOMContentLoaded', () => {
  console.log("Online.");

  initializeGame();

  const opponentBoard = document.getElementById('opponent-board');
  const playerBoard = document.getElementById('player-board');

  // Click Handler for enemy board
  opponentBoard.addEventListener('click', (e) => {
    if (e.target.classList.contains('cell')) {
      // Remove previous selection visual
      document.querySelectorAll('.cell').forEach(c => c.style.outline = 'none');

      // Highligh current selection
      e.target.style.outline = '2px solid var(--ui-cyan)';

      const row = e.target.dataset.row;
      const col = e.target.dataset.col;
      gameState.selectedCell = { row, col };

      addLogEntry(`Target Selected: ${String.fromCharCode(65 + parseInt(row))}${parseInt(col) + 1}`);
    }
  });

  // Action Button (Fire)
  actionBtn.addEventListener('click', () => {
    if (selectedCell) {
      addLogEntry("ERROR: No target selected.");
      return;
    }

    sendFireRequest(selectedCell.row, selectedCell.col);
  });
});

// API Communication
async function initializeGame() {
  try {
    const response = await fetch('/api/game/new', { method: 'POST' });
    const data = await response.json();
    currentSnapshot = data.snapshot;
    updateUI(currentSnapshot);
    addLogEntry("Game Initialized.");
  } catch (err) {
    addLogEntry("CONNECTION ERROR");
  }
}

async function sendFireRequest(row, col) {
  const payload = {
    snapshot: currentSnapshot,
    player: 1,
    row: parseInt(row),
    col: parseInt(col),
    ai_player: 2,
    autoResolveAiTurn: true
  };

  try {
    const response = await fetch('/api/game/fire', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await response.json();

    // Save new state returned by the server
    currentSnapshot = data.snapshot;
    updateUI(currentSnapshot);

    addLogEntry(`Fired at ${String.fromCharCode(65 + parseInt(row))}${parseInt(col) + 1}`);
  } catch (err) {
    addLogEntry("SYSTEM ERROR: Failed to fire.");
  }
}

// UI Rendering
function updateUI(snapshot) {
  if (!snapshot) return;

  // Update HUD
  document.getElementById('state-phase').innerText = snapshot.phase;
  document.getElementById('state-turn').innerText = snapshot.turn_count;

  // Update Player's Board (Ships and AI shots)
  const playerBoardData = snapshot.boards["1"];

  playerBoardData.grid.forEach((row, rIdx) => {
    row.forEach((cellValue, cIdx) => {
      const cell = document.querySelector(`#player-board #cell-${rIdx}-${cIdx}`);
      // Check if there is a ship
      if (cellValue === 1) {
        cell.classList.add('cell-ship');
      }
    });
  });

  // Update Enemy Board (Player Shots)
  playerBoardData.shot_tracker.forEach(shot => {
    // Based on engine output: [row, col, result_code]
    const [r, c, result] = shot;
    const cell = document.querySelector(`#opponent-board #cell-${r}-${c}`);

    // Result codes: 1=hit (red), 2=miss (white)
    if (result === 1) {
      cell.classList.add('cell-hit');
    } else {
      cell.classList.add('cell-miss');
    }
  });
}

// Logs
function addLogEntry(msg, type = "system") {
  const log = document.getElementById('combat-log');
  const entry = document.createElement('div');
  entry.className = `log-entry ${type}`;
  entry.innerText = `> ${msg}`;
  log.prepend(entry); // Newest on top
}

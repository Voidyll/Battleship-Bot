// This JavaScript file will keep track of Selection,
// Communication, and Rendering.

// Global state for the frontend
let currentSnapshot = null;
let selectedCell = null;
let activeShip = {name: null, size: null};
let placementOrientation = 1; // 1 = Horizontal, 0 = Vertical

document.addEventListener('DOMContentLoaded', () => {
  console.log("Interface Online.");

  initializeGame();

  const opponentBoard = document.getElementById('opponent-board');
  const playerBoard = document.getElementById('player-board');
  const actionBtn = document.getElementById('btn-action');
  const orientationBtn = document.getElementById('btn-orientation');
  const resetBtn = document.getElementById('btn-reset');

  resetBtn.addEventListener('click', () => {
    if (confirm("Are you sure you want to reset?")) {
      resetGame();
    }
  });
  
  // Ship Selection
  document.querySelectorAll('.btn-ship').forEach(btn => {
    btn.addEventListener('click', () => {
      activeShip.name = btn.dataset.name;
      activeShip.size = parseInt(btn.dataset.size);

      // Visual feedback for selection
      document.querySelectorAll('.btn-ship').forEach(b => b.classList.remove('activeShip'));
      btn.classList.add('activeShip');

      addLogEntry(`Selected ${activeShip.name} (Size: ${activeShip.size}). Click the board to place.`);
    });
  });

  // Orientation Toggle
  if (orientationBtn) {
    orientationBtn.addEventListener('click', () => {
      placementOrientation = placementOrientation === 1 ? 0 : 1;
      orientationBtn.innerText = placementOrientation === 1 ? "HORIZONTAL" : "VERTICAL";
    });
  }

  // Player Board Click (Manual Placement)
  playerBoard.addEventListener('click', (e) => {
    if (e.target.classList.contains('cell') && activeShip.name) {
      const row = e.target.dataset.row;
      const col = e.target.dataset.col;
      manualPlaceShip(row, col);
    } else if (!activeShip.name) {
      addLogEntry("ERROR: Select a ship type first.", "warning");
    }
  });

  // Opponent Board Click (Targeting) 
  opponentBoard.addEventListener('click', (e) => {
    if (e.target.classList.contains('cell')) {
      // Remove previous selection visual
      document.querySelectorAll('#opponent-board .cell').forEach(c => c.style.outline = 'none');

      // Highligh current selection
      e.target.style.outline = '2px solid var(--ui-cyan)';

      const row = e.target.dataset.row;
      const col = e.target.dataset.col;
      selectedCell = { row, col };

      addLogEntry(`Target Selected: ${String.fromCharCode(65 + parseInt(row))}${parseInt(col) + 1}`);
    }
  });

  // Action Button (Fire)
  actionBtn.addEventListener('click', () => {
    if (!selectedCell) {
      addLogEntry("ERROR: No target selected.", "warning");
      return;
    }
    sendFireRequest(selectedCell.row, selectedCell.col);
  });
});

// API Communication
async function resetGame() {
  // Clear Logs
  const log = document.getElementById('combat-log');
  log.innerHTML = '<div class="log-entry">Restarting. Please Wait...</div>';

  // Clear all visual classes from board cells
  document.querySelectorAll('.cell').forEach(cell => {
    cell.classList.remove('cell-ship', 'cell-hit', 'cell-miss');
    cell.style.outline = 'none';
  });

  // Reset Selection State
  selectedCell = null;
  activeShip = {name: null, size: null};
  document.querySelectorAll('.btn-ship').forEach(b => b.classList.remove('activeShip'));

  // Request a new game through initializeGame()
  await initializeGame();

  addLogEntry("Reset complete. Awaiting Placement.", "success");
}

async function manualPlaceShip(row, col) {
  const payload = {
    snapshot: currentSnapshot,
    player: 1,
    ship: activeShip.name,
    row: parseInt(row),
    col: parseInt(col),
    orientation: placementOrientation
  };

  try {
    const response = await fetch('/api/game/place-ship', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });

    const data = await response.json();

    if (data.error) {
      addLogEntry(`PLACEMENT FAILED: ${data.error}`, "warning");
    } else {
      currentSnapshot = data.snapshot;
      updateUI(currentSnapshot);
      addLogEntry(`Deployed ${activeShip.name} at ${String.fromCharCode(65 + parseInt(row))}${parseInt(col) + 1}`);

      // Reset selection after placement to prevent double-placing
      activeShip = {name: null, size: null};
      document.querySelectorAll('.btn-ship').forEach(b => b.classList.remove('activeShip'));
    }
  } catch (err) {
    addLogEntry("CONNECTION ERROR: Deployment failed.");
  }
}

async function initializeGame() {
  try {
    const response = await fetch('/api/game/new', { method: 'POST' });
    //const data = await response.json();
   
    // Check if server actually sent 200
    if (!response.ok) {
      const errorText = await response.text();
      console.error("Server Error Text: ", errorText);
      throw new Error(`HTTP error. Status: ${response.status}`);
    }

    const data = await response.json();
    console.log("Data received: ", data); // See if this prints

    currentSnapshot = data.snapshot;
    updateUI(currentSnapshot);
    addLogEntry("Game Initialized.");
  } catch (err) {
    console.error("Error: ", err);
    addLogEntry(`ERROR: ${err.message}`);
    // addLogEntry("CONNECTION ERROR: Failed to start session.");
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

  // Toggle UI Visibility Based on Phase
  const actionBtn = document.getElementById('btn-action');
  const placementUI = document.querySelector('.placement-controls');

  if (snapshot.phase === 'placement') {
    actionBtn.style.display = 'none';
    placementUI.style.display = 'block';
  } else {
    actionBtn.style.display = 'block';
    placementUI.style.display = 'none';
  }

  // Fade out used Ships
  const placedShips = snapshot.boards["1"].placed; //Array of names like ["Carrier", "Cruiser", etc.]
  document.querySelectorAll('.btn-ship').forEach(btn => {
    if (placedShips.includes(btn.dataset.name)) {
      btn.style.opacity = "0.3";
      btn.style.pointerEvents = "none"; // Prevent clicking it again
      btn.classList.remove('activeShip');
    } else {
      btn.style.opacity = "1";
      btn.style.pointerEvents = "auto";
    }
  });

  // Update Player's Board (Ships and AI shots)
  const playerBoardData = snapshot.boards["1"];

  playerBoardData.grid.forEach((row, rIdx) => {
    row.forEach((val, cIdx) => {
      const cell = document.getElementById(`player-cell-${rIdx}-${cIdx}`);
      if (!cell) return;

      // Wipe old state
      cell.classList.remove('cell-ship', 'cell-hit', 'cell-miss');

      if (val === 1) cell.classList.add('cell-ship');
      if (val === 2) cell.classList.add('cell-ship', 'cell-hit');
      if (val === 3) cell.classList.add('cell-miss');
    });
  });

  // Update Enemy Board (Player Shots)
  const enemyBoardData = snapshot.boards["1"];

  enemyBoardData.shot_tracker.forEach((row, rIdx) => {
    row.forEach((val, cIdx) => {
      const cell = document.getElementById(`opp-cell-${rIdx}-${cIdx}`);
      if (!cell) return;

      // Wipe old state 
      cell.classList.remove('cell-hit', 'cell-miss', 'cell-sunk');

      if (val === -1) cell.classList.add('cell-miss');
      if (val === 1) cell.classList.add('cell-hit');
      if (val === 2) cell.classList.add('cell-hit', 'cell-sunk');
    });
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

// ========================================
// Assignment Page JavaScript
// ========================================

let tabSwitches = 0;
let startTime = null;
let timerInterval = null;
let suspiciousActions = [];
let autoSaveEnabled = true;
let autoSaveTimer = null;

// DOM Elements
const codeEditor = document.getElementById('codeEditor');
const timeElapsedEl = document.getElementById('timeElapsed');
const tabSwitchesDisplay = document.getElementById('tabSwitchesDisplay');
const tabSwitchesCount = document.getElementById('tabSwitchesCount');
const warningAlert = document.getElementById('warningAlert');
const submitBtn = document.getElementById('submitBtn');
const submitModal = document.getElementById('submitModal');
const modalClose = document.getElementById('modalClose');
const cancelSubmit = document.getElementById('cancelSubmit');
const confirmSubmit = document.getElementById('confirmSubmit');
const summaryTime = document.getElementById('summaryTime');
const summarySwitches = document.getElementById('summarySwitches');
const autoSaveBtn = document.getElementById('autoSaveBtn');
const toast = document.getElementById('toast');
const toastMessage = document.getElementById('toastMessage');

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    startTimer();
    setupEventListeners();
    loadSavedState();
});

// Start Timer
function startTimer() {
    startTime = new Date();
    timerInterval = setInterval(updateTimer, 1000);
}

// Update Timer Display
function updateTimer() {
    const now = new Date();
    const diff = Math.floor((now - startTime) / 1000);
    const minutes = Math.floor(diff / 60);
    const seconds = diff % 60;
    timeElapsedEl.textContent = 
        `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
}

// Get Elapsed Time in Seconds
function getElapsedTime() {
    if (!startTime) return 0;
    const now = new Date();
    return Math.floor((now - startTime) / 1000);
}

// Setup Event Listeners
function setupEventListeners() {
    // Tab visibility change detection
    document.addEventListener('visibilitychange', function() {
        if (document.hidden) {
            tabSwitches++;
            const action = {
                type: 'tab_switch',
                timestamp: new Date().toISOString(),
                totalSwitches: tabSwitches
            };
            suspiciousActions.push(action);
            
            // Show warning after first switch
            if (tabSwitches === 1) {
                warningAlert.style.display = 'flex';
                setTimeout(() => {
                    warningAlert.style.display = 'none';
                }, 5000);
            }
            
            // Show tab switches counter after 3 switches
            if (tabSwitches >= 3) {
                tabSwitchesDisplay.style.display = 'flex';
                tabSwitchesCount.textContent = tabSwitches;
            }
            
            // Log to server
            logActivity('tab_switch', { totalSwitches: tabSwitches });
        }
    });

    // Window blur detection (for when user switches to another app)
    window.addEventListener('blur', function() {
        const action = {
            type: 'window_blur',
            timestamp: new Date().toISOString()
        };
        suspiciousActions.push(action);
        logActivity('window_blur', {});
    });

    // Submit button
    submitBtn.addEventListener('click', showSubmitModal);

    // Modal controls
    modalClose.addEventListener('click', hideSubmitModal);
    cancelSubmit.addEventListener('click', hideSubmitModal);
    confirmSubmit.addEventListener('click', submitAssignment);

    // Close modal on outside click
    submitModal.addEventListener('click', function(e) {
        if (e.target === submitModal) {
            hideSubmitModal();
        }
    });

    // Auto-save on code change
    codeEditor.addEventListener('input', function() {
        if (autoSaveEnabled) {
            clearTimeout(autoSaveTimer);
            autoSaveTimer = setTimeout(autoSave, 2000);
        }
    });

    // Auto-save button toggle
    autoSaveBtn.addEventListener('click', toggleAutoSave);

    // Prevent common cheating attempts
    setupAntiCheating();
}

// Anti-cheating measures
function setupAntiCheating() {
    // Disable right-click context menu
    document.addEventListener('contextmenu', function(e) {
        // Allow context menu only in the code editor
        if (!e.target.closest('.code-editor')) {
            e.preventDefault();
        }
    });

    // Disable certain keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Disable Ctrl+C, Ctrl+V outside editor
        if ((e.ctrlKey || e.metaKey) && 
            (e.key === 'c' || e.key === 'v' || e.key === 'x') &&
            !e.target.closest('.code-editor')) {
            // Don't prevent default, but log it
            const action = {
                type: 'keyboard_shortcut',
                key: e.key,
                timestamp: new Date().toISOString()
            };
            suspiciousActions.push(action);
        }
        
        // Disable F12 (DevTools)
        if (e.key === 'F12') {
            e.preventDefault();
            const action = {
                type: 'devtools_attempt',
                timestamp: new Date().toISOString()
            };
            suspiciousActions.push(action);
            showToast('Использование инструментов разработчика запрещено');
        }
        
        // Disable Ctrl+Shift+I and Ctrl+Shift+J (DevTools)
        if ((e.ctrlKey || e.metaKey) && e.shiftKey && 
            (e.key === 'I' || e.key === 'J' || e.key === 'C')) {
            e.preventDefault();
        }
    });
}

// Load saved state from localStorage
function loadSavedState() {
    const savedCode = localStorage.getItem(`assignment_${ASSIGNMENT_ID}_code`);
    const savedTabSwitches = localStorage.getItem(`assignment_${ASSIGNMENT_ID}_switches`);
    
    if (savedCode) {
        codeEditor.value = savedCode;
    }
    
    if (savedTabSwitches) {
        tabSwitches = parseInt(savedTabSwitches, 10);
        if (tabSwitches >= 3) {
            tabSwitchesDisplay.style.display = 'flex';
            tabSwitchesCount.textContent = tabSwitches;
        }
    }
}

// Save state to localStorage
function saveState() {
    localStorage.setItem(`assignment_${ASSIGNMENT_ID}_code`, codeEditor.value);
    localStorage.setItem(`assignment_${ASSIGNMENT_ID}_switches`, tabSwitches.toString());
}

// Auto-save function
function autoSave() {
    saveState();
    showToast('Автосохранение выполнено');
}

// Toggle auto-save
function toggleAutoSave() {
    autoSaveEnabled = !autoSaveEnabled;
    autoSaveBtn.innerHTML = autoSaveEnabled ? 
        `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
            <polyline points="17 21 17 13 7 13 7 21"/>
            <polyline points="7 3 7 8 15 8"/>
        </svg>
        Автосохранение: вкл` :
        `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="15" y1="9" x2="9" y2="15"/>
            <line x1="9" y1="9" x2="15" y2="15"/>
        </svg>
        Автосохранение: выкл`;
}

// Show submit modal
function showSubmitModal() {
    summaryTime.textContent = timeElapsedEl.textContent;
    summarySwitches.textContent = tabSwitches;
    submitModal.style.display = 'flex';
}

// Hide submit modal
function hideSubmitModal() {
    submitModal.style.display = 'none';
}

// Log activity to server
async function logActivity(actionType, details) {
    try {
        await fetch('/student/activity-log', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                action_type: actionType,
                details: details,
                assignment_id: ASSIGNMENT_ID
            })
        });
    } catch (error) {
        console.error('Error logging activity:', error);
    }
}

// Submit assignment
async function submitAssignment() {
    const code = codeEditor.value;
    
    if (!code.trim()) {
        showToast('Код не может быть пустым');
        return;
    }
    
    const elapsedTime = getElapsedTime();
    
    try {
        const response = await fetch(`/student/submit/${ASSIGNMENT_ID}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                code: code,
                tab_switches: tabSwitches,
                time_spent: elapsedTime,
                suspicious_actions: suspiciousActions
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('Работа успешно сохранена!');
            hideSubmitModal();
            
            // Clear localStorage after successful submission
            localStorage.removeItem(`assignment_${ASSIGNMENT_ID}_code`);
            localStorage.removeItem(`assignment_${ASSIGNMENT_ID}_switches`);
            
            // Redirect after short delay
            setTimeout(() => {
                window.location.href = '/student/dashboard';
            }, 1500);
        } else {
            showToast('Ошибка: ' + result.error);
        }
    } catch (error) {
        console.error('Error submitting assignment:', error);
        showToast('Ошибка при отправке работы');
    }
}

// Show toast notification
function showToast(message) {
    toastMessage.textContent = message;
    toast.style.display = 'block';
    setTimeout(() => {
        toast.style.display = 'none';
    }, 3000);
}

// Save state before page unload
window.addEventListener('beforeunload', function() {
    saveState();
});

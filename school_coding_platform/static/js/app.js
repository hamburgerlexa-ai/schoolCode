/**
 * School Coding Platform - Core JavaScript
 * Anti-cheat monitoring, autosave, timer, and UI interactions
 */

// ==================== Toast Notifications ====================
class ToastManager {
    constructor() {
        this.container = null;
        this.init();
    }

    init() {
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        this.container = container;
    }

    show(message, type = 'info', duration = 5000) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };

        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || icons.info}</span>
            <span class="toast-message">${message}</span>
        `;

        this.container.appendChild(toast);

        setTimeout(() => {
            toast.style.animation = 'slideOut 0.25s ease forwards';
            setTimeout(() => toast.remove(), 250);
        }, duration);
    }

    success(message) { this.show(message, 'success'); }
    error(message) { this.show(message, 'error'); }
    warning(message) { this.show(message, 'warning'); }
    info(message) { this.show(message, 'info'); }
}

const toast = new ToastManager();

// ==================== Server Time Sync ====================
class TimeSync {
    constructor() {
        this.serverTimeOffset = 0;
        this.syncInterval = 60000; // 1 minute
        this.init();
    }

    async init() {
        await this.sync();
        setInterval(() => this.sync(), this.syncInterval);
    }

    async sync() {
        try {
            const response = await fetch('/api/time');
            const data = await response.json();
            const serverTime = new Date(data.server_time).getTime();
            const localTime = Date.now();
            this.serverTimeOffset = serverTime - localTime;
        } catch (error) {
            console.error('Time sync failed:', error);
        }
    }

    getServerTime() {
        return new Date(Date.now() + this.serverTimeOffset);
    }

    getServerTimestamp() {
        return this.getServerTime().toISOString();
    }
}

const timeSync = new TimeSync();

// ==================== Countdown Timer ====================
class CountdownTimer {
    constructor(endTime, callbacks = {}) {
        this.endTime = new Date(endTime).getTime();
        this.callbacks = {
            tick: callbacks.tick || (() => {}),
            warning: callbacks.warning || (() => {}),
            expired: callbacks.expired || (() => {})
        };
        this.interval = null;
        this.warningThreshold = 300000; // 5 minutes
        this.dangerThreshold = 60000; // 1 minute
        this.isExpired = false;
    }

    start() {
        this.update();
        this.interval = setInterval(() => this.update(), 1000);
    }

    stop() {
        if (this.interval) {
            clearInterval(this.interval);
            this.interval = null;
        }
    }

    update() {
        const now = timeSync.getServerTime().getTime();
        const remaining = Math.max(0, this.endTime - now);

        const minutes = Math.floor(remaining / 60000);
        const seconds = Math.floor((remaining % 60000) / 1000);

        const timeString = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;

        this.callbacks.tick(timeString, remaining);

        if (remaining <= this.dangerThreshold && remaining > 0) {
            this.callbacks.warning('danger', timeString);
        } else if (remaining <= this.warningThreshold && remaining > this.dangerThreshold) {
            this.callbacks.warning('warning', timeString);
        }

        if (remaining === 0 && !this.isExpired) {
            this.isExpired = true;
            this.stop();
            this.callbacks.expired();
        }
    }

    getRemainingTime() {
        const now = timeSync.getServerTime().getTime();
        return Math.max(0, this.endTime - now);
    }

    isTimeUp() {
        return this.isExpired || this.getRemainingTime() === 0;
    }
}

// ==================== Autosave Manager ====================
class AutosaveManager {
    constructor(saveCallback, interval = 30000) {
        this.saveCallback = saveCallback;
        this.interval = interval;
        this.lastSave = null;
        this.pendingChanges = false;
        this.timer = null;
        this.enabled = true;
    }

    start() {
        if (!this.enabled) return;
        
        this.timer = setInterval(() => {
            if (this.pendingChanges) {
                this.save();
            }
        }, this.interval);

        // Save before unload
        window.addEventListener('beforeunload', () => this.save());
    }

    stop() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
    }

    markChanged() {
        this.pendingChanges = true;
    }

    async save() {
        if (!this.pendingChanges || !this.enabled) return;

        try {
            await this.saveCallback();
            this.lastSave = new Date();
            this.pendingChanges = false;
            toast.success('Черновик сохранён');
        } catch (error) {
            console.error('Autosave failed:', error);
            toast.error('Не удалось сохранить черновик');
        }
    }

    getStatus() {
        if (!this.enabled) return 'disabled';
        if (this.pendingChanges) return 'pending';
        return 'saved';
    }
}

// ==================== Anti-Cheat Monitor ====================
class AntiCheatMonitor {
    constructor(submissionId, callbacks = {}) {
        this.submissionId = submissionId;
        this.callbacks = {
            onTabSwitch: callbacks.onTabSwitch || (() => {}),
            onFullscreenExit: callbacks.onFullscreenExit || (() => {}),
            onDevTools: callbacks.onDevTools || (() => {}),
            onUpdateSuspicion: callbacks.onUpdateSuspicion || (() => {})
        };
        this.suspicionScore = 0;
        this.events = [];
        this.isActive = false;
        this.hiddenCount = 0;
    }

    start() {
        this.isActive = true;
        this.bindEvents();
        this.enterFullscreen();
    }

    stop() {
        this.isActive = false;
        this.unbindEvents();
        this.exitFullscreen();
    }

    bindEvents() {
        // Tab switching
        document.addEventListener('visibilitychange', () => this.handleVisibilityChange());
        
        // Fullscreen
        document.addEventListener('fullscreenchange', () => this.handleFullscreenChange());
        
        // DevTools attempts
        document.addEventListener('keydown', (e) => this.handleKeydown(e));
        document.addEventListener('contextmenu', (e) => this.handleContextMenu(e));
        
        // Blur
        window.addEventListener('blur', () => this.handleWindowBlur());
    }

    unbindEvents() {
        document.removeEventListener('visibilitychange', () => this.handleVisibilityChange());
        document.removeEventListener('fullscreenchange', () => this.handleFullscreenChange());
        document.removeEventListener('keydown', (e) => this.handleKeydown(e));
        document.removeEventListener('contextmenu', (e) => this.handleContextMenu(e));
        window.removeEventListener('blur', () => this.handleWindowBlur());
    }

    handleVisibilityChange() {
        if (!this.isActive) return;

        if (document.hidden) {
            this.hiddenCount++;
            this.logEvent('tab_switch', { count: this.hiddenCount });
            this.suspicionScore = Math.min(100, this.suspicionScore + 10);
            this.callbacks.onTabSwitch(this.hiddenCount);
            this.sendActivity('tab_switch', { count: this.hiddenCount });
        }
    }

    handleFullscreenChange() {
        if (!this.isActive) return;

        if (!document.fullscreenElement) {
            this.logEvent('fullscreen_exit', {});
            this.suspicionScore = Math.min(100, this.suspicionScore + 15);
            this.callbacks.onFullscreenExit();
            this.sendActivity('fullscreen_exit', {});
        }
    }

    handleKeydown(e) {
        if (!this.isActive) return;

        // F12, Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+U
        const devToolsKeys = [
            e.key === 'F12',
            e.ctrlKey && e.shiftKey && (e.key === 'I' || e.key === 'J'),
            e.ctrlKey && e.key === 'U'
        ];

        if (devToolsKeys.some(k => k)) {
            this.logEvent('devtools_attempt', { key: e.key });
            this.suspicionScore = Math.min(100, this.suspicionScore + 20);
            this.callbacks.onDevTools();
            this.sendActivity('devtools_attempt', { key: e.key });
        }
    }

    handleContextMenu(e) {
        if (!this.isActive) return;
        
        // Log right-click but don't prevent it (too aggressive)
        this.logEvent('right_click', { x: e.clientX, y: e.clientY });
    }

    handleWindowBlur() {
        if (!this.isActive) return;
        this.logEvent('window_blur', {});
    }

    enterFullscreen() {
        const elem = document.documentElement;
        if (elem.requestFullscreen) {
            elem.requestFullscreen().catch(err => {
                console.log('Fullscreen not available:', err);
            });
        }
    }

    exitFullscreen() {
        if (document.fullscreenElement) {
            document.exitFullscreen().catch(err => console.log(err));
        }
    }

    logEvent(eventType, data) {
        this.events.push({
            type: eventType,
            data: data,
            timestamp: new Date().toISOString()
        });
        this.callbacks.onUpdateSuspicion(this.suspicionScore);
    }

    async sendActivity(eventType, data) {
        try {
            const response = await fetch(`/api/submission/${this.submissionId}/activity`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    event_type: eventType,
                    event_data: data
                })
            });

            if (response.ok) {
                const result = await response.json();
                this.suspicionScore = result.suspicion_score || this.suspicionScore;
                this.callbacks.onUpdateSuspicion(this.suspicionScore);
            }
        } catch (error) {
            console.error('Failed to send activity:', error);
        }
    }

    getSuspicionLevel() {
        if (this.suspicionScore < 30) return 'low';
        if (this.suspicionScore < 70) return 'medium';
        return 'high';
    }

    getReport() {
        return {
            suspicionScore: this.suspicionScore,
            suspicionLevel: this.getSuspicionLevel(),
            events: this.events,
            hiddenCount: this.hiddenCount
        };
    }
}

// ==================== Code Editor Wrapper ====================
class CodeEditor {
    constructor(elementId, options = {}) {
        this.elementId = elementId;
        this.editor = null;
        this.options = {
            mode: options.mode || 'python',
            theme: options.theme || 'dracula',
            lineNumbers: options.lineNumbers !== false,
            indentUnit: options.indentUnit || 4,
            tabSize: options.tabSize || 4,
            autoCloseBrackets: options.autoCloseBrackets !== false,
            matchBrackets: options.matchBrackets !== false,
            ...options
        };
    }

    init() {
        const textarea = document.getElementById(this.elementId);
        if (!textarea) {
            console.error(`Textarea #${this.elementId} not found`);
            return null;
        }

        if (typeof CodeMirror !== 'undefined') {
            this.editor = CodeMirror.fromTextArea(textarea, {
                mode: this.options.mode,
                theme: this.options.theme,
                lineNumbers: this.options.lineNumbers,
                indentUnit: this.options.indentUnit,
                tabSize: this.options.tabSize,
                autoCloseBrackets: this.options.autoCloseBrackets,
                matchBrackets: this.options.matchBrackets,
                lineWrapping: true,
                extraKeys: {
                    'Tab': (cm) => {
                        if (cm.somethingSelected()) {
                            cm.indentSelection('add');
                        } else {
                            cm.replaceSelection(' '.repeat(this.options.indentUnit));
                        }
                    },
                    'Ctrl-S': (cm) => {
                        if (this.onSave) {
                            this.onSave(cm.getValue());
                        }
                    }
                }
            });

            return this.editor;
        }

        return null;
    }

    getValue() {
        return this.editor ? this.editor.getValue() : '';
    }

    setValue(code) {
        if (this.editor) {
            this.editor.setValue(code);
        }
    }

    setReadOnly(readOnly) {
        if (this.editor) {
            this.editor.setOption('readOnly', readOnly);
        }
    }

    focus() {
        if (this.editor) {
            this.editor.focus();
        }
    }

    refresh() {
        if (this.editor) {
            this.editor.refresh();
        }
    }

    onSave(callback) {
        this.onSave = callback;
    }
}

// ==================== Form Validation ====================
class FormValidator {
    constructor(formElement) {
        this.form = typeof formElement === 'string' 
            ? document.querySelector(formElement) 
            : formElement;
        this.errors = [];
    }

    validate() {
        this.errors = [];
        const inputs = this.form.querySelectorAll('[required], [data-validate]');

        inputs.forEach(input => {
            const value = input.value.trim();
            const name = input.name || input.id;

            if (input.hasAttribute('required') && !value) {
                this.addError(name, 'Это поле обязательно');
            }

            if (input.dataset.validate === 'email' && value && !this.isValidEmail(value)) {
                this.addError(name, 'Введите корректный email');
            }

            if (input.dataset.minLength && value.length < parseInt(input.dataset.minLength)) {
                this.addError(name, `Минимум ${input.dataset.minLength} символов`);
            }

            if (input.dataset.maxLength && value.length > parseInt(input.dataset.maxLength)) {
                this.addError(name, `Максимум ${input.dataset.maxLength} символов`);
            }
        });

        return this.errors.length === 0;
    }

    addError(field, message) {
        this.errors.push({ field, message });
    }

    isValidEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    }

    showErrors() {
        this.errors.forEach(error => {
            toast.error(error.message);
        });
    }
}

// ==================== Modal Manager ====================
class ModalManager {
    constructor() {
        this.activeModal = null;
    }

    open(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;

        const overlay = modal.closest('.modal-overlay') || modal;
        overlay.classList.add('active');
        this.activeModal = overlay;

        // Close on overlay click
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                this.close();
            }
        });

        // Close on Escape
        const escHandler = (e) => {
            if (e.key === 'Escape') {
                this.close();
                document.removeEventListener('keydown', escHandler);
            }
        };
        document.addEventListener('keydown', escHandler);
    }

    close() {
        if (this.activeModal) {
            this.activeModal.classList.remove('active');
            this.activeModal = null;
        }
    }
}

const modal = new ModalManager();

// ==================== Utility Functions ====================
function formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatRelativeTime(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'только что';
    if (diffMins < 60) return `${diffMins} мин назад`;
    if (diffHours < 24) return `${diffHours} ч назад`;
    if (diffDays < 7) return `${diffDays} дн назад`;
    
    return formatDateTime(dateString);
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        toast.success('Скопировано в буфер обмена');
    }).catch(err => {
        console.error('Copy failed:', err);
        toast.error('Не удалось скопировать');
    });
}

// Export for global use
window.toast = toast;
window.timeSync = timeSync;
window.CountdownTimer = CountdownTimer;
window.AutosaveManager = AutosaveManager;
window.AntiCheatMonitor = AntiCheatMonitor;
window.CodeEditor = CodeEditor;
window.FormValidator = FormValidator;
window.modal = modal;
window.formatDateTime = formatDateTime;
window.formatRelativeTime = formatRelativeTime;
window.copyToClipboard = copyToClipboard;

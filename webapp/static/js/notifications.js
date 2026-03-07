/**
 * Custom Themed Notification System
 * Replaces browser alerts with styled toast notifications
 */

class NotificationSystem {
    constructor() {
        this.container = null;
        this.init();
    }

    init() {
        // Create notification container
        this.container = document.createElement('div');
        this.container.id = 'notificationContainer';
        this.container.style.cssText = `
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 10000;
            display: flex;
            flex-direction: column;
            gap: 12px;
            pointer-events: none;
        `;
        document.body.appendChild(this.container);
    }

    show(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `notification notification-${type}`;

        // Icon based on type
        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };

        // Colors based on type
        const colors = {
            success: { bg: 'rgba(16, 185, 129, 0.15)', border: '#10b981', text: '#10b981' },
            error: { bg: 'rgba(239, 68, 68, 0.15)', border: '#ef4444', text: '#ef4444' },
            warning: { bg: 'rgba(245, 158, 11, 0.15)', border: '#f59e0b', text: '#f59e0b' },
            info: { bg: 'rgba(59, 130, 246, 0.15)', border: '#3b82f6', text: '#3b82f6' }
        };

        const color = colors[type] || colors.info;

        toast.style.cssText = `
            background: ${color.bg};
            backdrop-filter: blur(12px);
            border: 1px solid ${color.border};
            border-radius: 12px;
            padding: 14px 18px;
            min-width: 280px;
            max-width: 400px;
            display: flex;
            align-items: center;
            gap: 12px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            pointer-events: auto;
            animation: slideIn 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            cursor: pointer;
        `;

        toast.innerHTML = `
            <div style="
                width: 28px;
                height: 28px;
                border-radius: 50%;
                background: ${color.border};
                color: #0a0e1a;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 700;
                font-size: 16px;
                flex-shrink: 0;
            ">${icons[type]}</div>
            <div style="
                flex: 1;
                color: #ffffff;
                font-size: 14px;
                font-weight: 500;
                line-height: 1.4;
            ">${message}</div>
        `;

        // Add animation styles if not already present
        if (!document.getElementById('notificationStyles')) {
            const style = document.createElement('style');
            style.id = 'notificationStyles';
            style.textContent = `
                @keyframes slideIn {
                    from {
                        transform: translateX(400px);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
                @keyframes slideOut {
                    from {
                        transform: translateX(0);
                        opacity: 1;
                    }
                    to {
                        transform: translateX(400px);
                        opacity: 0;
                    }
                }
            `;
            document.head.appendChild(style);
        }

        this.container.appendChild(toast);

        // Click to dismiss
        toast.addEventListener('click', () => {
            this.dismiss(toast);
        });

        // Auto dismiss
        if (duration > 0) {
            setTimeout(() => {
                this.dismiss(toast);
            }, duration);
        }

        return toast;
    }

    dismiss(toast) {
        toast.style.animation = 'slideOut 0.3s cubic-bezier(0.4, 0, 0.2, 1)';
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, 300);
    }

    success(message, duration = 3000) {
        return this.show(message, 'success', duration);
    }

    error(message, duration = 4000) {
        return this.show(message, 'error', duration);
    }

    warning(message, duration = 3500) {
        return this.show(message, 'warning', duration);
    }

    info(message, duration = 3000) {
        return this.show(message, 'info', duration);
    }

    // Confirmation dialog replacement
    async confirm(message, confirmText = 'Confirm', cancelText = 'Cancel') {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.7);
                backdrop-filter: blur(4px);
                z-index: 10001;
                display: flex;
                align-items: center;
                justify-content: center;
                animation: fadeIn 0.2s ease;
            `;

            const dialog = document.createElement('div');
            dialog.style.cssText = `
                background: var(--panel-solid, #1a1a1a);
                border: 1px solid var(--border, #333);
                border-radius: 16px;
                padding: 24px;
                max-width: 400px;
                width: 90%;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
                animation: scaleIn 0.2s ease;
            `;

            dialog.innerHTML = `
                <div style="
                    color: #ffffff;
                    font-size: 16px;
                    font-weight: 600;
                    margin-bottom: 20px;
                    line-height: 1.5;
                ">${message}</div>
                <div style="
                    display: flex;
                    gap: 12px;
                    justify-content: flex-end;
                ">
                    <button id="cancelBtn" style="
                        padding: 10px 20px;
                        border-radius: 8px;
                        border: 1px solid var(--border, #333);
                        background: transparent;
                        color: #999;
                        font-weight: 600;
                        cursor: pointer;
                        transition: all 0.2s;
                    ">${cancelText}</button>
                    <button id="confirmBtn" style="
                        padding: 10px 20px;
                        border-radius: 8px;
                        border: none;
                        background: #ff8c00;
                        color: #ffffff;
                        font-weight: 600;
                        cursor: pointer;
                        transition: all 0.2s;
                    ">${confirmText}</button>
                </div>
            `;

            overlay.appendChild(dialog);
            document.body.appendChild(overlay);

            const cleanup = () => {
                overlay.style.animation = 'fadeOut 0.2s ease';
                setTimeout(() => overlay.remove(), 200);
            };

            dialog.querySelector('#confirmBtn').addEventListener('click', () => {
                cleanup();
                resolve(true);
            });

            dialog.querySelector('#cancelBtn').addEventListener('click', () => {
                cleanup();
                resolve(false);
            });

            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) {
                    cleanup();
                    resolve(false);
                }
            });
        });
    }
}

// Global instance
window.notify = new NotificationSystem();

// Add animation styles
if (!document.getElementById('dialogAnimations')) {
    const style = document.createElement('style');
    style.id = 'dialogAnimations';
    style.textContent = `
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        @keyframes fadeOut {
            from { opacity: 1; }
            to { opacity: 0; }
        }
        @keyframes scaleIn {
            from {
                transform: scale(0.9);
                opacity: 0;
            }
            to {
                transform: scale(1);
                opacity: 1;
            }
        }
    `;
    document.head.appendChild(style);
}

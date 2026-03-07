// Account Manager - FTMO-style account management
class AccountManager {
    constructor() {
        this.currentAccount = null;
        this.accounts = [];
        this.modal = null;
        this.init();
        this.setupKeyboardShortcuts();
    }

    async init() {
        await this.loadAccounts();
        this.createModal();
        this.render();

        // Trigger initial account change event to load fresh data
        if (this.currentAccount) {
            console.log('🔄 Triggering initial account change event for:', this.currentAccount.name);
            const event = new CustomEvent('accountChanged', {
                detail: { accountId: this.currentAccount.id },
                bubbles: true
            });
            document.dispatchEvent(event);
            window.dispatchEvent(event);
        }
    }

    async loadAccounts() {
        try {
            const response = await fetch('/api/accounts');
            const allAccounts = await response.json();

            // Filter out deleted accounts
            this.accounts = allAccounts.filter(a => a.status !== 'DELETED');

            // Get current account from localStorage or use first account
            const savedAccountId = localStorage.getItem('currentAccountId');
            if (savedAccountId) {
                this.currentAccount = this.accounts.find(a => a.id === parseInt(savedAccountId));
            }
            if (!this.currentAccount && this.accounts.length > 0) {
                this.currentAccount = this.accounts[0];
                localStorage.setItem('currentAccountId', this.accounts[0].id);
            }

            // Clear cache on initial load to ensure fresh data
            if (window.api && typeof window.api.clearCache === 'function') {
                window.api.clearCache();
                console.log('🔄 Cache cleared on account manager init');
            }
        } catch (err) {
            console.error('Failed to load accounts:', err);
        }
    }

    setCurrentAccount(accountId) {
        this.currentAccount = this.accounts.find(a => a.id === accountId);
        localStorage.setItem('currentAccountId', accountId);

        // Clear API cache when switching accounts to force fresh data
        if (window.api && typeof window.api.clearCache === 'function') {
            window.api.clearCache();
        }

        this.render();

        // Trigger account change event on both document and window
        const event = new CustomEvent('accountChanged', {
            detail: { accountId },
            bubbles: true
        });
        document.dispatchEvent(event);
        window.dispatchEvent(event);

        console.log('✅ Account changed to:', accountId, this.currentAccount?.name);
        console.log('   Cache cleared, fresh data will be loaded');
    }

    render() {
        const container = document.getElementById('accountSelector');
        if (!container) return;

        if (this.accounts.length === 0) {
            container.innerHTML = `
                <button class="account-btn" onclick="accountManager.openModal()">
                    <span>➕ Add Account</span>
                </button>
            `;
            return;
        }

        const current = this.currentAccount || this.accounts[0];

        container.innerHTML = `
            <div class="account-selector-wrapper">
                <button class="account-btn" onclick="accountManager.toggleDropdown()">
                    <div class="account-info">
                        <div class="account-name">${current.name}</div>
                        <div class="account-balance">${current.currency} ${(current.balance || current.initial_balance).toFixed(2)}</div>
                    </div>
                    <span class="dropdown-arrow">▼</span>
                </button>
                <div class="account-dropdown" id="accountDropdown" style="display: none;">
                    ${this.accounts.map(acc => `
                        <div class="account-dropdown-item ${acc.id === current.id ? 'active' : ''}" 
                             onclick="accountManager.setCurrentAccount(${acc.id})">
                            <div class="account-info">
                                <div class="account-name">${acc.name}</div>
                                <div class="account-balance">${acc.currency} ${(acc.balance || acc.initial_balance).toFixed(2)}</div>
                            </div>
                            <div style="display: flex; gap: 4px; align-items: center;">
                                ${acc.id === current.id ? '<span class="check">✓</span>' : ''}
                                <button class="icon-btn" onclick="event.stopPropagation(); accountManager.openModal(${acc.id})" title="Edit">
                                    <i data-lucide="edit-2" style="width: 14px; height: 14px;"></i>
                                </button>
                                <button class="icon-btn" onclick="event.stopPropagation(); accountManager.deleteAccount(${acc.id})" title="Delete" style="color: var(--red);">
                                    <i data-lucide="trash-2" style="width: 14px; height: 14px;"></i>
                                </button>
                            </div>
                        </div>
                    `).join('')}
                    <div class="account-dropdown-divider"></div>
                    <div class="account-dropdown-item" onclick="accountManager.openModal()">
                        <span>➕ Add New Account</span>
                    </div>
                </div>
            </div>
        `;

        // Re-initialize Lucide icons for the new buttons
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    toggleDropdown() {
        const dropdown = document.getElementById('accountDropdown');
        if (dropdown) {
            const isVisible = dropdown.style.display !== 'none';
            dropdown.style.display = isVisible ? 'none' : 'block';

            // Close dropdown when clicking outside
            if (!isVisible) {
                setTimeout(() => {
                    const closeOnClickOutside = (e) => {
                        if (!e.target.closest('.account-selector-wrapper')) {
                            dropdown.style.display = 'none';
                            document.removeEventListener('click', closeOnClickOutside);
                        }
                    };
                    document.addEventListener('click', closeOnClickOutside);
                }, 0);
            }
        }
    }

    setupKeyboardShortcuts() {
        const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;

        document.addEventListener('keydown', (e) => {
            // Cmd+K (Mac) or Ctrl+K (Windows/Linux) to open account switcher
            if ((isMac ? e.metaKey : e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                this.toggleDropdown();
            }

            // Escape to close dropdown
            if (e.key === 'Escape') {
                const dropdown = document.getElementById('accountDropdown');
                if (dropdown && dropdown.style.display !== 'none') {
                    dropdown.style.display = 'none';
                }
            }
        });
    }

    createModal() {
        const modalHTML = `
            <div id="accountModal" class="modal" style="display: none;">
                <div class="modal-overlay" onclick="accountManager.closeModal()"></div>
                <div class="modal-content">
                    <div class="modal-header">
                        <h2 id="modalTitle">Add Account</h2>
                        <button class="modal-close" onclick="accountManager.closeModal()">✕</button>
                    </div>
                    <div class="modal-body">
                        <form id="accountForm" onsubmit="accountManager.saveAccount(event)">
                            <div class="form-group">
                                <label>Account Name *</label>
                                <input type="text" id="accountName" required 
                                       placeholder="e.g., FTMO 50k Challenge">
                            </div>
                            
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Initial Balance *</label>
                                    <input type="number" id="initialBalance" required 
                                           step="0.01" placeholder="50000">
                                </div>
                                <div class="form-group">
                                    <label>Currency *</label>
                                    <select id="currency" required>
                                        <option value="USD">USD</option>
                                        <option value="EUR">EUR</option>
                                        <option value="GBP">GBP</option>
                                    </select>
                                </div>
                            </div>

                            <div class="form-group">
                                <label>Firm Name</label>
                                <select id="firmName">
                                    <option value="">Select firm...</option>
                                    <option value="FTMO">FTMO</option>
                                    <option value="MyForexFunds">MyForexFunds</option>
                                    <option value="The5ers">The5ers</option>
                                    <option value="TopstepFX">TopstepFX</option>
                                    <option value="Personal">Personal Account</option>
                                    <option value="Other">Other</option>
                                </select>
                            </div>

                            <div class="form-section-title">Risk Rules</div>
                            
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Max Daily Loss %</label>
                                    <input type="number" id="maxDailyLoss" 
                                           step="0.1" placeholder="5.0">
                                </div>
                                <div class="form-group">
                                    <label>Max Total Loss %</label>
                                    <input type="number" id="maxTotalLoss" 
                                           step="0.1" placeholder="10.0">
                                </div>
                            </div>

                            <div class="form-row">
                                <div class="form-group">
                                    <label>Profit Target %</label>
                                    <input type="number" id="profitTarget" 
                                           step="0.1" placeholder="10.0">
                                </div>
                                <div class="form-group">
                                    <label>Risk Per Trade %</label>
                                    <input type="number" id="riskPerTrade" 
                                           step="0.1" placeholder="1.0">
                                </div>
                            </div>

                            <div class="form-actions">
                                <button type="button" class="btn-secondary" 
                                        onclick="accountManager.closeModal()">Cancel</button>
                                <button type="submit" class="btn-primary">Save Account</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.modal = document.getElementById('accountModal');
    }

    openModal(accountId = null) {
        this.toggleDropdown(); // Close dropdown if open

        if (accountId) {
            // Edit mode
            const account = this.accounts.find(a => a.id === accountId);
            if (account) {
                document.getElementById('modalTitle').textContent = 'Edit Account';
                document.getElementById('accountName').value = account.name;
                document.getElementById('initialBalance').value = account.initial_balance;
                document.getElementById('currency').value = account.currency;
                document.getElementById('firmName').value = account.firm_name || '';
                document.getElementById('maxDailyLoss').value = account.max_daily_loss_pct || '';
                document.getElementById('maxTotalLoss').value = account.max_total_loss_pct || '';
                document.getElementById('profitTarget').value = account.profit_target_pct || '';
                document.getElementById('riskPerTrade').value = account.risk_per_trade_pct || '';
                document.getElementById('accountForm').dataset.accountId = accountId;
            }
        } else {
            // Create mode
            document.getElementById('modalTitle').textContent = 'Add Account';
            document.getElementById('accountForm').reset();
            delete document.getElementById('accountForm').dataset.accountId;
        }

        this.modal.style.display = 'flex';
    }

    closeModal() {
        this.modal.style.display = 'none';
    }

    async saveAccount(event) {
        event.preventDefault();

        const form = event.target;
        const accountId = form.dataset.accountId;

        const data = {
            name: document.getElementById('accountName').value,
            initial_balance: parseFloat(document.getElementById('initialBalance').value),
            currency: document.getElementById('currency').value,
            firm_name: document.getElementById('firmName').value || null,
            max_daily_loss_pct: parseFloat(document.getElementById('maxDailyLoss').value) || null,
            max_total_loss_pct: parseFloat(document.getElementById('maxTotalLoss').value) || null,
            profit_target_pct: parseFloat(document.getElementById('profitTarget').value) || null,
            risk_per_trade_pct: parseFloat(document.getElementById('riskPerTrade').value) || null,
        };

        try {
            const url = accountId ? `/api/accounts/${accountId}` : '/api/accounts';
            const method = accountId ? 'PUT' : 'POST';

            const response = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (!response.ok) throw new Error('Failed to save account');

            await this.loadAccounts();
            this.render();
            this.closeModal();

            // Show success message
            this.showToast(accountId ? 'Account updated!' : 'Account created!');
        } catch (err) {
            console.error('Error saving account:', err);
            alert('Failed to save account. Please try again.');
        }
    }

    async deleteAccount(accountId) {
        const account = this.accounts.find(a => a.id === accountId);
        if (!account) return;

        if (!confirm(`Are you sure you want to delete "${account.name}"?\n\nThis will NOT delete associated trades, but you won't be able to filter by this account anymore.`)) {
            return;
        }

        try {
            const response = await fetch(`/api/accounts/${accountId}`, {
                method: 'DELETE'
            });

            if (!response.ok) throw new Error('Failed to delete account');

            // If we're deleting the current account, switch to another one
            if (this.currentAccount?.id === accountId) {
                const remainingAccounts = this.accounts.filter(a => a.id !== accountId);
                if (remainingAccounts.length > 0) {
                    this.setCurrentAccount(remainingAccounts[0].id);
                } else {
                    this.currentAccount = null;
                    localStorage.removeItem('currentAccountId');
                }
            }

            await this.loadAccounts();
            this.render();
            this.showToast('Account deleted');
        } catch (err) {
            console.error('Error deleting account:', err);
            alert('Failed to delete account. Please try again.');
        }
    }

    showToast(message) {
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(() => toast.classList.add('show'), 10);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 2000);
    }

    getCurrentAccountId() {
        return this.currentAccount?.id || null;
    }
}

// Initialize global account manager
window.accountManager = null;
document.addEventListener('DOMContentLoaded', () => {
    window.accountManager = new AccountManager();
    console.log('✅ Account manager initialized:', window.accountManager);
});

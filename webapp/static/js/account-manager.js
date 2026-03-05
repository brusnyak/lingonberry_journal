// Account Manager - FTMO-style account management
class AccountManager {
    constructor() {
        this.currentAccount = null;
        this.accounts = [];
        this.modal = null;
        this.init();
    }

    async init() {
        await this.loadAccounts();
        this.createModal();
        this.render();
    }

    async loadAccounts() {
        try {
            const response = await fetch('/api/accounts');
            this.accounts = await response.json();

            // Get current account from localStorage or use first account
            const savedAccountId = localStorage.getItem('currentAccountId');
            if (savedAccountId) {
                this.currentAccount = this.accounts.find(a => a.id === parseInt(savedAccountId));
            }
            if (!this.currentAccount && this.accounts.length > 0) {
                this.currentAccount = this.accounts[0];
            }
        } catch (err) {
            console.error('Failed to load accounts:', err);
        }
    }

    setCurrentAccount(accountId) {
        this.currentAccount = this.accounts.find(a => a.id === accountId);
        localStorage.setItem('currentAccountId', accountId);
        this.render();

        // Trigger account change event
        window.dispatchEvent(new CustomEvent('accountChanged', {
            detail: { accountId }
        }));
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
                            ${acc.id === current.id ? '<span class="check">✓</span>' : ''}
                        </div>
                    `).join('')}
                    <div class="account-dropdown-divider"></div>
                    <div class="account-dropdown-item" onclick="accountManager.openModal()">
                        <span>➕ Add New Account</span>
                    </div>
                </div>
            </div>
        `;
    }

    toggleDropdown() {
        const dropdown = document.getElementById('accountDropdown');
        if (dropdown) {
            dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
        }
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
let accountManager;
document.addEventListener('DOMContentLoaded', () => {
    accountManager = new AccountManager();
});

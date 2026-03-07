/**
 * API Client with Caching
 * Handles all backend API calls with localStorage caching
 */

const API_BASE = window.location.origin + '/api';
const CACHE_DURATION = 30000; // 30 seconds

class APIClient {
    constructor() {
        this.cache = new Map();
    }

    /**
     * Get cached data if available and not expired
     */
    getCached(key) {
        try {
            const cached = localStorage.getItem(`cache_${key}`);
            if (!cached) return null;

            const { data, timestamp } = JSON.parse(cached);
            if (Date.now() - timestamp > CACHE_DURATION) {
                localStorage.removeItem(`cache_${key}`);
                return null;
            }
            return data;
        } catch {
            return null;
        }
    }

    /**
     * Set cached data
     */
    setCached(key, data) {
        try {
            localStorage.setItem(`cache_${key}`, JSON.stringify({
                data,
                timestamp: Date.now()
            }));
        } catch (e) {
            console.warn('Failed to cache data:', e);
        }
    }

    /**
     * Fetch with caching
     */
    async fetch(endpoint, options = {}) {
        const useCache = options.cache !== false;
        const cacheKey = endpoint;

        // Try cache first
        if (useCache) {
            const cached = this.getCached(cacheKey);
            if (cached) {
                return cached;
            }
        }

        // Fetch from API
        const response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();

        // Cache GET requests
        if (!options.method || options.method === 'GET') {
            this.setCached(cacheKey, data);
        }

        return data;
    }

    /**
     * Get dashboard data
     */
    async getDashboard(params = {}) {
        const query = new URLSearchParams(params).toString();
        const endpoint = `/dashboard${query ? '?' + query : ''}`;
        // Include account_id in cache key to avoid showing wrong account data
        const cacheKey = endpoint;
        return this.fetch(endpoint, { cacheKey });
    }

    /**
     * Get trades
     */
    async getTrades(params = {}) {
        const query = new URLSearchParams(params).toString();
        const endpoint = `/trades${query ? '?' + query : ''}`;
        // Include account_id in cache key
        const cacheKey = endpoint;
        return this.fetch(endpoint, { cacheKey });
    }

    /**
     * Get trade by ID
     */
    async getTrade(tradeId) {
        return this.fetch(`/trades/${tradeId}`);
    }

    /**
     * Get Monte Carlo data
     */
    async getMonteCarlo() {
        return this.fetch('/analytics/monte-carlo');
    }

    /**
     * Get weekly review
     */
    async getWeeklyReview(weekStart) {
        const query = weekStart ? `?week_start=${weekStart}` : '';
        return this.fetch(`/review/week${query}`);
    }

    /**
     * Update weekly review
     */
    async updateWeeklyReview(data) {
        return this.fetch('/review/week', {
            method: 'POST',
            body: JSON.stringify(data),
            cache: false
        });
    }

    /**
     * Get weekly goals
     */
    async getWeeklyGoals(weekStart) {
        const query = weekStart ? `?week_start=${weekStart}` : '';
        return this.fetch(`/goals/week${query}`);
    }

    /**
     * Clear all cache
     */
    clearCache() {
        const keys = Object.keys(localStorage);
        keys.forEach(key => {
            if (key.startsWith('cache_')) {
                localStorage.removeItem(key);
            }
        });
    }
}

// Export singleton instance
const api = new APIClient();

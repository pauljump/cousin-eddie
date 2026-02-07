// API Configuration
const API_URL = 'http://localhost:8000';  // Change for production

let selectedCompany = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    loadCompanies();
    loadProcessors();
});

// Load dashboard stats
async function loadStats() {
    try {
        const response = await fetch(`${API_URL}/api/stats`);
        const stats = await response.json();

        document.getElementById('total-signals').textContent = stats.total_signals.toLocaleString();
        document.getElementById('active-processors').textContent = stats.active_processors;
        document.getElementById('total-companies').textContent = stats.total_companies;
        document.getElementById('planned-processors').textContent = stats.planned_processors;

        const lastUpdated = new Date(stats.last_updated);
        document.getElementById('last-updated').textContent = lastUpdated.toLocaleDateString();
    } catch (error) {
        console.error('Error loading stats:', error);
        // Show sample data if API not available
        document.getElementById('total-signals').textContent = '140';
        document.getElementById('active-processors').textContent = '7';
        document.getElementById('total-companies').textContent = '2';
        document.getElementById('planned-processors').textContent = '25+';
        document.getElementById('last-updated').textContent = 'Demo Mode';
    }
}

// Load companies
async function loadCompanies() {
    const container = document.getElementById('company-grid');

    try {
        const response = await fetch(`${API_URL}/api/companies`);
        const companies = await response.json();

        container.innerHTML = companies.map(company => `
            <div class="company-card" onclick="selectCompany('${company.id}')">
                <div class="company-ticker">${company.ticker}</div>
                <div class="company-name">${company.name}</div>
                <div class="company-stats">
                    <span>${company.sector}</span>
                    <span>${company.signal_count} signals</span>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading companies:', error);
        // Show sample data
        container.innerHTML = `
            <div class="company-card" onclick="selectCompany('UBER')">
                <div class="company-ticker">UBER</div>
                <div class="company-name">Uber Technologies Inc</div>
                <div class="company-stats">
                    <span>Technology</span>
                    <span>39 signals</span>
                </div>
            </div>
            <div class="company-card" onclick="selectCompany('LYFT')">
                <div class="company-ticker">LYFT</div>
                <div class="company-name">Lyft Inc</div>
                <div class="company-stats">
                    <span>Technology</span>
                    <span>6 signals</span>
                </div>
            </div>
        `;
    }
}

// Load processors
async function loadProcessors() {
    try {
        const response = await fetch(`${API_URL}/api/processors`);
        const processors = await response.json();

        const byCategory = processors.reduce((acc, proc) => {
            if (!acc[proc.category]) acc[proc.category] = [];
            acc[proc.category].push(proc);
            return acc;
        }, {});

        for (const [category, procs] of Object.entries(byCategory)) {
            const container = document.getElementById(`${category}-processors`);
            if (container) {
                container.innerHTML = procs.map(p => renderProcessor(p)).join('');
            }
        }
    } catch (error) {
        console.error('Error loading processors:', error);
        loadSampleProcessors();
    }
}

function renderProcessor(processor) {
    const isActive = processor.status === 'active';
    const badgeClass = isActive ? 'badge-active' : 'badge-coming-soon';
    const cardClass = isActive ? 'active' : 'coming-soon';

    return `
        <div class="processor-card ${cardClass}">
            <div class="processor-header">
                <div class="processor-name">${formatSignalType(processor.signal_type)}</div>
                <div class="processor-badge ${badgeClass}">
                    ${processor.status === 'active' ? '✓ Active' : '⏳ Coming Soon'}
                </div>
            </div>
            <div class="processor-description">${processor.description}</div>
            <div class="processor-meta">
                <span>📅 ${processor.update_frequency}</span>
                <span>📊 ${processor.data_source}</span>
            </div>
        </div>
    `;
}

function loadSampleProcessors() {
    // Sample data for demo mode
    const sampleProcessors = {
        regulatory: [
            { signal_type: 'sec_form_4', description: 'Insider trading filings', status: 'active', update_frequency: 'realtime', data_source: 'SEC EDGAR' },
            { signal_type: 'sec_financials', description: 'Financial statements from 10-K/10-Q', status: 'active', update_frequency: 'quarterly', data_source: 'SEC EDGAR' },
            { signal_type: 'sec_mda', description: 'Management Discussion & Analysis', status: 'active', update_frequency: 'quarterly', data_source: 'SEC EDGAR' },
            { signal_type: 'risk_factors', description: 'Risk factor disclosures', status: 'coming_soon', update_frequency: 'quarterly', data_source: 'SEC EDGAR' },
            { signal_type: 'sec_8k', description: 'Material events (8-K filings)', status: 'coming_soon', update_frequency: 'realtime', data_source: 'SEC EDGAR' },
            { signal_type: 'institutional_holdings', description: '13F institutional ownership', status: 'coming_soon', update_frequency: 'quarterly', data_source: 'SEC EDGAR' },
        ],
        web_digital: [
            { signal_type: 'app_store_ratings', description: 'iOS App Store ratings', status: 'active', update_frequency: 'daily', data_source: 'Apple App Store' },
            { signal_type: 'google_trends', description: 'Search interest trends', status: 'active', update_frequency: 'daily', data_source: 'Google Trends' },
            { signal_type: 'play_store_ratings', description: 'Android Play Store ratings', status: 'coming_soon', update_frequency: 'daily', data_source: 'Google Play' },
        ],
        workforce: [
            { signal_type: 'job_postings', description: 'Hiring velocity tracking', status: 'active', update_frequency: 'daily', data_source: 'Greenhouse API' },
        ],
        alternative: [
            { signal_type: 'reddit_sentiment', description: 'Reddit mentions and sentiment', status: 'active', update_frequency: 'daily', data_source: 'Reddit API' },
            { signal_type: 'news_sentiment', description: 'News sentiment analysis', status: 'coming_soon', update_frequency: 'daily', data_source: 'NewsAPI' },
            { signal_type: 'twitter_sentiment', description: 'Twitter/X sentiment', status: 'coming_soon', update_frequency: 'realtime', data_source: 'Twitter API' },
        ]
    };

    for (const [category, procs] of Object.entries(sampleProcessors)) {
        const container = document.getElementById(`${category}-processors`);
        if (container) {
            container.innerHTML = procs.map(p => renderProcessor(p)).join('');
        }
    }
}

// Select company and load signals
async function selectCompany(companyId) {
    selectedCompany = companyId;

    // Update UI
    document.querySelectorAll('.company-card').forEach(card => {
        card.classList.remove('selected');
    });
    event.target.closest('.company-card').classList.add('selected');

    document.getElementById('selected-company').textContent = companyId;
    document.getElementById('signals-section').style.display = 'block';

    // Load signals
    await loadSignals(companyId);
}

// Load signals for company
async function loadSignals(companyId) {
    const container = document.getElementById('signals-container');
    container.innerHTML = '<div class="loading">Loading signals...</div>';

    try {
        const response = await fetch(`${API_URL}/api/signals/${companyId}?lookback_days=180`);
        const signals = await response.json();

        if (signals.length === 0) {
            container.innerHTML = '<div class="loading">No signals found</div>';
            return;
        }

        container.innerHTML = signals.slice(0, 20).map(signal => renderSignal(signal)).join('');
    } catch (error) {
        console.error('Error loading signals:', error);
        container.innerHTML = '<div class="loading">Error loading signals. API may be offline.</div>';
    }
}

function renderSignal(signal) {
    const sentiment = signal.score > 20 ? 'positive' : signal.score < -20 ? 'negative' : 'neutral';
    const scoreClass = sentiment === 'positive' ? 'score-positive' : sentiment === 'negative' ? 'score-negative' : 'score-neutral';

    const date = new Date(signal.timestamp);
    const dateStr = date.toLocaleDateString();

    return `
        <div class="signal-card ${sentiment}">
            <div class="signal-header">
                <div class="signal-type">${formatSignalType(signal.signal_type)} • ${signal.category}</div>
                <div class="signal-score ${scoreClass}">${signal.score > 0 ? '+' : ''}${signal.score}</div>
            </div>
            <div class="signal-description">${signal.description}</div>
            <div class="signal-meta">
                <span>📅 ${dateStr}</span>
                <span>📊 ${signal.source_name}</span>
                <span>🎯 Confidence: ${(signal.confidence * 100).toFixed(0)}%</span>
            </div>
        </div>
    `;
}

// Utility functions
function formatSignalType(type) {
    return type
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

// Make selectCompany available globally
window.selectCompany = selectCompany;

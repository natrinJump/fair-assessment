/*const API = 'https://fair-assessment.onrender.com';*/
/*const API = 'http://localhost:8000';*/


const API = window.location.hostname === 'localhost' || 
            window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8000'
    : 'https://fair-assessment.onrender.com';


function getLocalHistory() {
    try {
        return JSON.parse(localStorage.getItem('fair_history') || '[]');
    } catch(e) {
        return [];
    }
}

function saveLocalHistory(history) {
    localStorage.setItem('fair_history', JSON.stringify(history));
}

function addToLocalHistory(report, profileSnapshot) {
    const history = getLocalHistory();
    const entry = {
        id: Date.now(),
        doi: report.doi,
        profile_name: report.profile_name,
        overall_score: report.overall_score,
        f_score: report.f_score,
        a_score: report.a_score,
        i_score: report.i_score,
        r_score: report.r_score,
        maturity_level: report.maturity_level || '',
        maturity_description: report.maturity_description || '',
        results: report.results,
        profile_snapshot: profileSnapshot || {},
        created_at: new Date().toISOString()
    };
    history.unshift(entry); // newest first
    saveLocalHistory(history);
    return entry;
}

function getLocalHistoryByDoi(doi) {
    return getLocalHistory().filter(h => h.doi === doi);
}

function deleteLocalHistoryRun(id) {
    const history = getLocalHistory().filter(h => h.id !== id);
    saveLocalHistory(history);
}

function clearLocalHistory() {
    localStorage.removeItem('fair_history');
}

// ── Utility functions ──────────────────────────────────────

async function apiFetch(path, options = {}) {
    const res = await fetch(API + path, {
        headers: { 'Content-Type': 'application/json' },
        ...options
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || res.statusText);
    }
    return res.json();
}

function formatScore(score) {
    return Math.round(score) + '%';
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString();
}

function showError(id, msg) {
    document.getElementById(id).innerHTML =
        '<div class="error">' + msg + '</div>';
}

function showSuccess(id, msg) {
    document.getElementById(id).innerHTML =
        '<div class="success">' + msg + '</div>';
}
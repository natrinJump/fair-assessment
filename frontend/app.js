const API = 'https://fair-assessment.onrender.com/';

async function apiFetch(path, options = {}) {
    const res = await fetch(API + path, {
        headers: { 'Content-Type': 'application/json' },
        ...options
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

function formatScore(score) {
    return Math.round(score) + '%';
}

function getScoreColor(score) {
    if (score >= 80) return '#0f9d58';
    if (score >= 60) return '#f4b400';
    return '#db4437';
}

function formatDate(isoString) {
    const d = new Date(isoString);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString();
}

function showError(containerId, message) {
    const el = document.getElementById(containerId);
    if (el) el.innerHTML = `<div class="error">${message}</div>`;
}

function showSuccess(containerId, message) {
    const el = document.getElementById(containerId);
    if (el) el.innerHTML = `<div class="success">${message}</div>`;
}
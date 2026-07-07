// Custom alert to bypass popup blockers
window.alert = function(msg) {
    const div = document.createElement('div');
    div.textContent = msg;
    div.style.position = 'fixed';
    div.style.bottom = '20px';
    div.style.right = '20px';
    div.style.backgroundColor = '#f44336';
    div.style.color = 'white';
    div.style.padding = '15px';
    div.style.borderRadius = '5px';
    div.style.zIndex = '9999';
    div.style.boxShadow = '0 2px 10px rgba(0,0,0,0.2)';
    div.style.maxWidth = '300px';
    document.body.appendChild(div);
    setTimeout(() => { if (document.body.contains(div)) document.body.removeChild(div); }, 5000);
};

const API_BASE = '/api';

const today = new Date();
const currentYear = today.getFullYear();
const prevMonthDate = new Date(today.getFullYear(), today.getMonth() - 1, 1);
const prevMonthStr = `${prevMonthDate.getFullYear()}-${String(prevMonthDate.getMonth() + 1).padStart(2, '0')}`;

// ── State ─────────────────────────────────────────────────────────────────────
let state = {
    currentPage: 'dashboard',
    apartments: [],
    startDate: `${currentYear}-01-01`,
    endDate: `${currentYear}-12-31`,
    visitedDashboard: false,
    visitedOther: false,
    needsRecalculation: false,
    expandedMonth: null,
    pendingChanges: {},
    dashboardYear: currentYear,
    transactions: [],
    categories: [],
    contractors: [],
    txSearch: '',
    txSortCol: 'date',
    txSortDesc: true,
    
    // Month picker state
    pickerTargetState: null,
    pickerTargetCallback: null,
    pickerYear: currentYear
};

function formatCurrency(val) {
    if (val === undefined || val === null || isNaN(val)) return '0.00';
    return Number(val).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}

// ── DOM refs ──────────────────────────────────────────────────────────────────
const contentArea = document.getElementById('content-area');
const pageTitle = document.getElementById('page-title');
const navItems = document.querySelectorAll('.sidebar-nav li');
const modal = document.getElementById('modal-container');
const modalTitle = document.getElementById('modal-title');
const modalBody = document.getElementById('modal-body');

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    loadPage('dashboard');
    document.querySelectorAll('.close-modal').forEach(btn => { btn.onclick = closeModal; });

    const globalRecalcBtn = document.getElementById('btn-recalculate');
    if (globalRecalcBtn) {
        globalRecalcBtn.onclick = () => recalculateAll();
    }

    // Initialize Custom Period Picker
    const btn = document.getElementById('custom-period-btn');
    const dropdown = document.getElementById('custom-period-dropdown');
    const textSpan = document.getElementById('custom-period-text');
    
    function formatDateUa(dateStr) {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        return ('0' + d.getDate()).slice(-2) + '.' + ('0' + (d.getMonth() + 1)).slice(-2) + '.' + d.getFullYear();
    }
    
    function updatePeriodText(start, end) {
        if(textSpan) textSpan.innerText = `${formatDateUa(start)} - ${formatDateUa(end)}`;
    }
    
    updatePeriodText(state.startDate, state.endDate);
    
    if (btn && dropdown) {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
        });
        
        document.addEventListener('click', (e) => {
            const path = e.composedPath();
            if (!path.includes(btn) && !path.includes(dropdown)) {
                dropdown.style.display = 'none';
            }
        });
        
        const applyPeriod = (start, end) => {
            if (state.startDate !== start || state.endDate !== end) {
                state.startDate = start;
                state.endDate = end;
                updatePeriodText(start, end);
                loadPage(state.currentPage);
            }
            dropdown.style.display = 'none';
            document.querySelectorAll('.period-menu-page').forEach(p => p.style.display = 'none');
            document.getElementById('period-menu-main').style.display = 'block';
        };

        const todayDate = new Date();
        const currentYearNum = todayDate.getFullYear();
        
        // Populate Year Submenu
        const yearCont = document.getElementById('year-options-container');
        if(yearCont) {
            yearCont.innerHTML = '';
            for (let y = currentYearNum; y >= 2021; y--) {
                const div = document.createElement('div');
                div.className = 'period-menu-item';
                div.innerText = `${y} year`;
                div.onclick = () => applyPeriod(`${y}-01-01`, `${y}-12-31`);
                yearCont.appendChild(div);
            }
        }
        
        // Populate Quarter Submenu (Current and previous years)
        const qCont = document.getElementById('quarter-options-container');
        if(qCont) {
            qCont.innerHTML = '';
            for (let y = currentYearNum; y >= currentYearNum - 1; y--) {
                for (let q = 4; q >= 1; q--) {
                    const div = document.createElement('div');
                    div.className = 'period-menu-item';
                    div.innerText = `${q === 1 ? 'I' : q === 2 ? 'II' : q === 3 ? 'III' : 'IV'} quarter ${y}`;
                    const mStart = (q - 1) * 3;
                    const mEnd = q * 3;
                    div.onclick = () => {
                        const sd = new Date(y, mStart, 1);
                        const ed = new Date(y, mEnd, 0);
                        applyPeriod(sd.toISOString().split('T')[0], ed.toISOString().split('T')[0]);
                    };
                    qCont.appendChild(div);
                }
            }
        }

        // Populate Month Submenu
        const monthCont = document.getElementById('month-options-container');
        if(monthCont) {
            monthCont.innerHTML = '';
            const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
            for (let m = 0; m < 12; m++) {
                const div = document.createElement('div');
                div.className = 'period-menu-item';
                div.innerText = monthNames[m];
                div.onclick = () => {
                    const sd = new Date(currentYearNum, m, 1);
                    const ed = new Date(currentYearNum, m + 1, 0);
                    applyPeriod(sd.toISOString().split('T')[0], ed.toISOString().split('T')[0]);
                };
                monthCont.appendChild(div);
            }
        }
        
        // Setup Litepicker inline
        const litepickerContainer = document.getElementById('litepicker-container');
        if(litepickerContainer) {
            window.globalPicker = new Litepicker({
                element: document.getElementById('litepicker-container'),
                inlineMode: true,
                singleMode: false,
                numberOfMonths: 2,
                numberOfColumns: 2,
                format: 'YYYY-MM-DD',
                lang: 'uk-UA',
                startDate: state.startDate,
                endDate: state.endDate,
                setup: (picker) => {
                    picker.on('selected', (date1, date2) => {
                        // We do not auto-apply for inline mode until user clicks "Apply"
                    });
                }
            });
            // Litepicker requires an element. If inlineMode is true, it renders inside the parent element or the element itself.
        }
        
        const btnApply = document.getElementById('custom-period-apply');
        if(btnApply) {
            btnApply.onclick = () => {
                const d1 = window.globalPicker.getStartDate();
                const d2 = window.globalPicker.getEndDate();
                if (d1 && d2) {
                    applyPeriod(d1.format('YYYY-MM-DD'), d2.format('YYYY-MM-DD'));
                }
            };
        }
        
        const btnCancel = document.getElementById('custom-period-cancel');
        if(btnCancel) {
            btnCancel.onclick = () => {
                dropdown.style.display = 'none';
                document.querySelectorAll('.period-menu-page').forEach(p => p.style.display = 'none');
                document.getElementById('period-menu-main').style.display = 'block';
            };
        }

        // Actions
        dropdown.addEventListener('click', (e) => {
            const item = e.target.closest('.period-menu-item[data-action]');
            if (item) {
                const action = item.getAttribute('data-action');
                let sd, ed;
                const t = new Date();
                if (action === 'last7') {
                    sd = new Date(t); sd.setDate(t.getDate() - 7);
                    ed = new Date(t);
                } else if (action === 'today') {
                    sd = new Date(t); ed = new Date(t);
                } else if (action === 'yesterday') {
                    sd = new Date(t); sd.setDate(t.getDate() - 1);
                    ed = new Date(t); ed.setDate(t.getDate() - 1);
                } else if (action === 'thisMonth') {
                    sd = new Date(t.getFullYear(), t.getMonth(), 1);
                    ed = new Date(t.getFullYear(), t.getMonth() + 1, 0);
                } else if (action === 'prevMonth') {
                    sd = new Date(t.getFullYear(), t.getMonth() - 1, 1);
                    ed = new Date(t.getFullYear(), t.getMonth(), 0);
                }
                if (sd && ed) {
                    const sds = sd.getFullYear()+'-'+('0'+(sd.getMonth()+1)).slice(-2)+'-'+('0'+sd.getDate()).slice(-2);
                    const eds = ed.getFullYear()+'-'+('0'+(ed.getMonth()+1)).slice(-2)+'-'+('0'+ed.getDate()).slice(-2);
                    applyPeriod(sds, eds);
                }
            }
            
            const submenu = e.target.closest('.has-submenu');
            if (submenu) {
                document.getElementById('period-menu-main').style.display = 'none';
                document.getElementById(submenu.getAttribute('data-target')).style.display = 'block';
            }
            
            const backBtn = e.target.closest('.period-menu-header[data-back]');
            if (backBtn) {
                backBtn.closest('.period-menu-page').style.display = 'none';
                document.getElementById('period-menu-main').style.display = 'block';
            }
        });
    }
});

// ── Navigation ────────────────────────────────────────────────────────────────
function initNavigation() {
    navItems.forEach(item => {
        item.addEventListener('click', e => {
            e.preventDefault();
            const page = item.getAttribute('data-page');
            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');
            loadPage(page);
        });
    });
}

async function loadPage(page) {
    if (Object.keys(state.pendingChanges).length > 0 && state.currentPage === 'apartments') {
        const proceed = await showConfirmModal(
            'Unsaved Changes',
            'У вас є незбережені зміни в налаштуваннях ліфта. Save їх перед переходом?'
        );
        if (proceed === 'yes') {
            await saveApartmentChanges();
        } else if (proceed === 'no') {
            state.pendingChanges = {};
        } else {
            return; // Stay on page
        }
    }

    if (page === 'dashboard' && !state.visitedDashboard) {
        state.startDate = `${currentYear}-01-01`;
        state.endDate = `${currentYear}-12-31`;
        state.visitedDashboard = true;
    } else if (page !== 'dashboard' && !state.visitedOther) {
        const pYear = prevMonthDate.getFullYear();
        const pMonth = prevMonthDate.getMonth();
        const d1 = new Date(pYear, pMonth, 1);
        const d2 = new Date(pYear, pMonth + 1, 0);
        state.startDate = `${pYear}-${String(pMonth + 1).padStart(2, '0')}-01`;
        state.endDate = `${pYear}-${String(pMonth + 1).padStart(2, '0')}-${String(d2.getDate()).padStart(2, '0')}`;
        state.visitedOther = true;
    }
    
    if (window.globalPicker) {
        window.globalPicker.setDateRange(state.startDate, state.endDate);
    }

    state.currentPage = page;
    contentArea.innerHTML = '<div class="loader">Loading...</div>';

    switch (page) {
        case 'dashboard': await renderDashboard(); break;
        case 'apartments': 
            loadPage('settings'); 
            break;
        case 'transactions': await renderTransactions(); break;
        case 'charges': await renderCharges(); break;
        case 'reports': await renderReports(); break;
        case 'settings': await renderSettings(); break;
        default:
            contentArea.innerHTML = `<h2>Сторінка "${page}" ще в розробці</h2>`;
    }
}

// ── Data fetchers ─────────────────────────────────────────────────────────────
async function fetchApartments() {
    try {
        const res = await fetch(`${API_BASE}/apartments/`);
        state.apartments = await res.json();
    } catch (err) {
        console.error('fetchApartments:', err);
    }
}

async function fetchCategories() {
    try {
        const res = await fetch(`${API_BASE}/categories/`);
        state.categories = await res.json();
    } catch (err) {
        console.error('fetchCategories:', err);
    }
}

async function fetchContractors() {
    try {
        const res = await fetch(`${API_BASE}/contractors/`);
        state.contractors = await res.json();
    } catch (err) {
        console.error('fetchContractors:', err);
    }
}

// ── Modal ─────────────────────────────────────────────────────────────────────
function closeModal() {
    modal.style.display = 'none';
    state.pendingChanges = {};
    const submitBtn = document.getElementById('modal-submit');
    if (submitBtn) submitBtn.onclick = null;

    const modalFooter = document.querySelector('.modal-footer');
    if (modalFooter) {
        modalFooter.innerHTML = `
            <button class="btn btn-secondary close-modal" onclick="closeModal()">Cancel</button>
            <button class="btn btn-primary" id="modal-submit">Save</button>`;
    }
}

// ── Global Month Picker ───────────────────────────────────────────────────────
window.openMonthPicker = function(targetStateKey, callbackName, defaultPeriod = null) {
    state.pickerTargetState = targetStateKey;
    state.pickerTargetCallback = callbackName;
    
    let y, m;
    const periodStr = defaultPeriod || state[targetStateKey] || state.currentPeriod;
    if (periodStr && periodStr.includes('-')) {
        [y, m] = periodStr.split('-');
        state.pickerYear = parseInt(y);
    } else {
        state.pickerYear = new Date().getFullYear();
    }
    
    renderMonthPickerGrid();
    document.getElementById('month-picker-modal').style.display = 'flex';
};

window.closeMonthPicker = function() {
    document.getElementById('month-picker-modal').style.display = 'none';
};

window.changePickerYear = function(delta) {
    state.pickerYear += delta;
    renderMonthPickerGrid();
};

window.selectPickerMonth = function(monthIndex) {
    const periodStr = `${state.pickerYear}-${String(monthIndex).padStart(2, '0')}`;
    if (state.pickerTargetState) {
        state[state.pickerTargetState] = periodStr;
    }
    closeMonthPicker();
    
    if (state.pickerTargetCallback && typeof window[state.pickerTargetCallback] === 'function') {
        window[state.pickerTargetCallback](periodStr);
    }
};

function renderMonthPickerGrid() {
    const yearDisplay = document.getElementById('picker-year-display');
    if(yearDisplay) yearDisplay.innerText = state.pickerYear;
    
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const targetVal = state[state.pickerTargetState] || '';
    
    const html = months.map((m, i) => {
        const pStr = `${state.pickerYear}-${String(i + 1).padStart(2, '0')}`;
        const isActive = pStr === targetVal;
        return `<div class="month-cell ${isActive ? 'active' : ''}" onclick="selectPickerMonth(${i + 1})">${m}</div>`;
    }).join('');
    
    const grid = document.getElementById('picker-month-grid');
    if(grid) grid.innerHTML = html;
}

window.formatPeriodStr = function(periodStr) {
    if (!periodStr || !periodStr.includes('-')) return periodStr || '—';
    const [y, m] = periodStr.split('-');
    const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    return `${months[parseInt(m)-1]} ${y}`;
};

function showConfirmModal(title, message) {
    return new Promise(resolve => {
        modalTitle.innerText = title;
        modalBody.innerHTML = `<p style="font-size:1.1rem">${message}</p>`;

        const modalFooter = document.querySelector('.modal-footer');
        modalFooter.innerHTML = `
            <button class="btn btn-secondary" id="confirm-no">Ні, відмінити зміни</button>
            <button class="btn btn-primary" id="confirm-yes">Так, зберегти</button>
            <button class="btn btn-secondary" id="confirm-cancel">Cancel (залишитись)</button>
        `;

        document.getElementById('confirm-yes').onclick = () => { resolve('yes'); closeModal(); };
        document.getElementById('confirm-no').onclick = () => { resolve('no'); closeModal(); };
        document.getElementById('confirm-cancel').onclick = () => { resolve('cancel'); closeModal(); };

        modal.style.display = 'flex';
    });
}

// ── Pages ─────────────────────────────────────────────────────────────────────

// Dashboard
async function renderDashboard() {
    try {
        pageTitle.innerText = 'Dashboard';

        const res = await fetch(`${API_BASE}/dashboard/stats?start_date=${state.startDate}&end_date=${state.endDate}`);
        const data = await res.json();
        state.dashboardData = data;
        
        const year = state.startDate.split('-')[0];

        // ── Balance table HTML ──
        const bt = data.balance_table;
        const btHeaders = bt.headers.map(h => `<th>${h}</th>`).join('');
        const btRows = bt.rows.map(r => `<tr><td>${r.label}</td>${r.values.map(v => `<td class="text-right ${v < 0 ? 'color-danger' : ''}">${formatCurrency(v)}</td>`).join('')}</tr>`).join('');
        const btGrandRow = `<tr class="total-row"><td>${bt.grand_total.label}</td>${bt.grand_total.values.map(v => `<td class="text-right ${v < 0 ? 'color-danger' : ''}">${formatCurrency(v)}</td>`).join('')}</tr>`;
        const btBalanceRow = `<tr style="background:rgba(56,189,248,0.08)"><td style="font-weight:600">${bt.balance_row.label}</td>${bt.balance_row.values.map(v => `<td class="text-right" style="font-weight:600">${formatCurrency(v)}</td>`).join('')}</tr>`;

        // ── Expense breakdown HTML ──
        const ebRows = data.expense_breakdown.map(e =>
            `<tr><td>${e.group}</td><td class="text-right">${e.pct}%</td><td class="text-right color-danger">${formatCurrency(e.amount)}</td></tr>`
        ).join('');
        const ebTotal = data.expense_breakdown.reduce((s, e) => s + e.amount, 0);

        // ── Detail table HTML ──
        const detailHeaders = ['Type', 'Group', 'Purpose'].concat(data.labels).concat(['Grand Total']);
        const detailHeadersHtml = detailHeaders.map(h => `<th>${h}</th>`).join('');
        const detailRowsHtml = data.detail_rows.map(r => {
            let cls = '';
            if (r.level === 'grand_total') cls = 'total-row';
            else if (r.level === 'type_total') cls = 'total-row';
            else if (r.level === 'group_total') cls = 'subtotal-row';
            
            const valCells = r.values.map(v => `<td class="text-right ${v < 0 ? 'color-danger' : ''}">${v !== 0 ? formatCurrency(v) : ''}</td>`).join('');
            return `<tr class="${cls}"><td>${r.type}</td><td>${r.group}</td><td>${r.purpose}</td>${valCells}</tr>`;
        }).join('');

                let topDebtors = [];
        let otherDebt = 0;
        if (data.debtors && data.debtors.length > 0) {
            const sorted = [...data.debtors].sort((a, b) => b.debt - a.debt);
            topDebtors = sorted.slice(0, 10);
            for(let i=10; i<sorted.length; i++) {
                otherDebt += sorted[i].debt;
            }
        }
        
        let debtorsRowsHtml = topDebtors.map((d, i) =>
            `<tr><td>Кв. ${d.apartment || d.apt_number}</td><td>${d.owner}</td><td class="text-right color-danger">${formatCurrency(d.debt)} ₴</td></tr>`
        ).join('');
        if (otherDebt > 0) {
            debtorsRowsHtml += `<tr class="total-row"><td>Other</td><td>—</td><td class="text-right color-danger">${formatCurrency(otherDebt)} ₴</td></tr>`;
        }

        // ── Setup Forecast Scenarios state ──
        const now = new Date();
        const currentMonthStr = now.toISOString().substring(0, 7); // YYYY-MM
        
        const actualMonths = data.months.filter(m => m < currentMonthStr);
        const forecastMonths = data.months.filter(m => m >= currentMonthStr);
        
        window.globalForecastStartMonth = forecastMonths.length > 0 ? forecastMonths[0] : currentMonthStr;
        window.globalForecastEndMonth = forecastMonths.length > 0 ? forecastMonths[forecastMonths.length - 1] : currentMonthStr;
        
        const startBal = actualMonths.length > 0 ? data.balance[actualMonths.length - 1] : data.totals.start_balance;

        // Store actual data for chart overlay
        const monthNamesUa = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        window.dashboardActuals = {
            labels: actualMonths.map(m => `${monthNamesUa[parseInt(m.split('-')[1])-1]}-${m.split('-')[0].substring(2)}`),
            months: actualMonths,
            inflow: actualMonths.map((m, i) => data.inflow[i]),
            expenses: actualMonths.map((m, i) => data.expenses[i]),
            balance: actualMonths.map((m, i) => data.balance[i])
        };

        let activeTariff = 4.4;
        try {
            const tr = await fetch(`${API_BASE}/settings`);
            if (tr.ok) {
                const settings = await tr.json();
                const maint = settings.tariffs.find(t => t.name === 'Maintenance' || t.name === 'Утримання');
                if (maint) activeTariff = maint.value;
            }
        } catch(e) {}

        if (!window.scenarioParams) {
            window.scenarioParams = {
                1: { balance: startBal, tariff: activeTariff, collection: 85 },
                2: { balance: startBal, tariff: 8.0, collection: 85 },
                3: { balance: startBal, tariff: 12.0, collection: 85 }
            };
        } else {
            window.scenarioParams[1].balance = startBal;
            window.scenarioParams[2].balance = startBal;
            window.scenarioParams[3].balance = startBal;
        }

        if (!window.scenarioExcludedActivities) {
            window.scenarioExcludedActivities = { 1: new Set(), 2: new Set(), 3: new Set() };
        }
        if (!window.scenariosData) {
            window.scenariosData = {};
        }

        contentArea.innerHTML = `
            <div id="dashboard-grid" style="display: flex; flex-direction: column; gap: 1.5rem;">
                <!-- Top Stats Block -->
                <div class="dash-card" id="dash-stats" style="overflow: hidden; min-height: 100px;">
                    <div class="stats-grid">
                        <div class="stat-card">
                            <h3>Initial Balance</h3>
                            <div class="value ${data.totals.start_balance < 0 ? 'color-danger' : 'color-success'}">
                                ${formatCurrency(data.totals.start_balance)} ₴
                            </div>
                        </div>
                        <div class="stat-card">
                            <h3>Inflows</h3>
                            <div class="value color-success">
                                + ${formatCurrency(data.totals.inflow)} ₴
                            </div>
                        </div>
                        <div class="stat-card">
                            <h3>Expenses</h3>
                            <div class="value color-danger">
                                - ${formatCurrency(data.totals.expenses)} ₴
                            </div>
                        </div>
                        <div class="stat-card">
                            <h3>Final Balance</h3>
                            <div class="value ${data.totals.balance < 0 ? 'color-danger' : 'color-success'}">
                                ${formatCurrency(data.totals.balance)} ₴
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Full-Width Chart: Actuals + Scenarios -->
                <div class="chart-container dash-card" id="dash-chart" style="overflow: hidden; min-height: 350px; display: flex; flex-direction: column; width: 100%;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                        <h3 class="dash-section-title"><i class="fas fa-chart-area" style="color: var(--accent-color);"></i> Balance: Actual vs Forecast</h3>
                    </div>
                    <div class="collapsible-content" style="flex-grow: 1; display: flex; flex-direction: column;">
                        <div style="flex-grow: 1; min-height: 280px; position: relative;">
                            <canvas id="scenariosLineChart"></canvas>
                        </div>
                    </div>
                </div>

                <!-- Balance Table -->
                <div class="dash-table-card dash-card" id="dash-balance" style="overflow: hidden; min-height: 200px; display: flex; flex-direction: column;">
                    <h3 style="display:flex; justify-content:space-between; align-items:center;" data-collapsible="true">
                        <span class="dash-section-title">Balance</span>
                        <div>
                            <button id="toggle-details-btn" class="section-toggle-btn" style="margin-right:0.75rem;" onclick="toggleDetailsTable(event)"><i class="fas fa-plus"></i> Details</button>
                            <i class="fas fa-chevron-up toggle-icon" style="cursor:pointer; transition:transform 0.3s;" onclick="toggleCard(this)"></i>
                        </div>
                    </h3>
                    <div class="collapsible-content" style="flex-grow: 1; overflow-y: auto;">
                        <div style="overflow-x:auto">
                            <table style="margin-bottom:1rem;">
                                <thead><tr>${btHeaders}</tr></thead>
                                <tbody>${btRows}${btGrandRow}${btBalanceRow}</tbody>
                            </table>
                        </div>
                        <div id="details-table-container" style="display:none; overflow-x:auto; margin-top:2rem; border-top:1px solid rgba(255,255,255,0.1); padding-top:1rem;">
                            <h4 style="margin-bottom:1rem; color:var(--text-primary); font-size: 0.95rem;">Details Breakdown</h4>
                            <table>
                                <thead><tr>${detailHeadersHtml}</tr></thead>
                                <tbody>${detailRowsHtml}</tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- Full-Width Initiatives Grid -->
                <div class="dash-card dash-table-card" id="dash-initiatives" style="overflow: hidden; min-height: 200px; display: flex; flex-direction: column; width: 100%; padding: 1.5rem;">
                    <h3 style="margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center;" data-collapsible="true">
                        <span class="dash-section-title">Initiatives Availability</span>
                        <div>
                            <button class="btn btn-primary btn-sm" onclick="window.showAddActivityModalGlobal(); event.stopPropagation();" style="border-radius: 8px; font-size: 0.8rem; margin-right: 1rem;"><i class="fas fa-plus"></i> Add Initiative</button>
                            <i class="fas fa-chevron-up toggle-icon" style="cursor:pointer; transition:transform 0.3s;" onclick="toggleCard(this)"></i>
                        </div>
                    </h3>
                    <div class="collapsible-content" style="flex-grow: 1; overflow-y: auto;">
                        <div id="scenariosInitiativesGrid" style="width: 100%; overflow-x: auto;">
                            <div class="loader" style="margin: 2rem auto;">Loading...</div>
                        </div>
                    </div>
                </div>

                <!-- Single Scenario Detail Card (Full Width) -->
                <div id="scenario-detail-card" class="dash-card dash-table-card" style="overflow: hidden; min-height: 200px; display: flex; flex-direction: column; width: 100%; padding: 1.5rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.75rem;">
                        <h3 class="dash-section-title">
                            <i class="fas fa-sliders-h" style="color: var(--accent-color);"></i>
                            Scenario Parameters and Details
                        </h3>
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <div style="display: inline-flex; background: rgba(0,0,0,0.1); border: 1px solid var(--border-color); border-radius: 8px; padding: 3px;">
                                <button type="button" id="tab-btn-1" onclick="window.switchDetailScenario(1)" style="border: none; padding: 5px 14px; border-radius: 6px; font-size: 0.8rem; font-weight: 600; cursor: pointer; transition: all 0.2s; background: var(--accent-color); color: white; font-family: 'Inter', sans-serif;">А</button>
                                <button type="button" id="tab-btn-2" onclick="window.switchDetailScenario(2)" style="border: none; padding: 5px 14px; border-radius: 6px; font-size: 0.8rem; font-weight: 600; cursor: pointer; transition: all 0.2s; background: transparent; color: var(--text-secondary); font-family: 'Inter', sans-serif;">Б</button>
                                <button type="button" id="tab-btn-3" onclick="window.switchDetailScenario(3)" style="border: none; padding: 5px 14px; border-radius: 6px; font-size: 0.8rem; font-weight: 600; cursor: pointer; transition: all 0.2s; background: transparent; color: var(--text-secondary); font-family: 'Inter', sans-serif;">В</button>
                            </div>
                        </div>
                    </div>

                    <!-- Parameters Inputs — collapsible -->
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 0.75rem;">
                        <button class="section-toggle-btn" onclick="window.toggleSectionCollapse('scenario-params-section', this)">
                            <i class="fas fa-chevron-up"></i> Parameters
                        </button>
                    </div>
                    <div id="scenario-params-section" class="section-collapsible" style="background: rgba(255,255,255,0.02); padding: 1rem 1.25rem; border-radius: 12px; margin-bottom: 1rem; border: 1px solid var(--border-color);">
                        <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 1.25rem;">
                            <div>
                                <span class="dash-section-subtitle">Current Balance</span>
                                <div id="scenario-balance-display" style="font-weight: 600; font-size: 1rem; padding: 4px 0; color: var(--text-primary);">0.00 ₴</div>
                            </div>
                            <div>
                                <span class="dash-section-subtitle">Tariff (₴/m²)</span>
                                <div class="editable-pill" style="margin-top: 4px;">
                                    <input type="number" id="scenario-tariff" step="0.1" style="width: 50px;">
                                    <span class="pill-suffix">₴/м²</span>
                                </div>
                            </div>
                            <div>
                                <span class="dash-section-subtitle">Expected Collection</span>
                                <div class="editable-pill" style="margin-top: 4px;">
                                    <input type="number" id="scenario-collection" max="150" style="width: 42px;">
                                    <span class="pill-suffix">%</span>
                                </div>
                            </div>
                            <div style="display:flex; align-items:flex-end;">
                                <button class="btn btn-primary btn-sm" onclick="window.updateCurrentScenarioParams()" style="font-weight: 600; display: flex; align-items: center; gap: 6px; border-radius: 8px; padding: 6px 16px; font-size: 0.8rem;">
                                    <i class="fas fa-sync-alt"></i> Update
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- Detail Table & Summary Stats — collapsible -->
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 0.75rem;">
                        <button class="section-toggle-btn" onclick="window.toggleSectionCollapse('scenario-detail-results', this)">
                            <i class="fas fa-chevron-up"></i> Details Breakdown
                        </button>
                    </div>
                    <div id="scenario-detail-results" class="section-collapsible">
                        <div class="loader" style="margin: 2rem auto;">Loading...</div>
                    </div>
                </div>

                <!-- Debtors and Expenses Breakdown -->
                <div id="dash-tables-row" class="dashboard-tables-grid" style="display:flex; flex-direction:row; flex-wrap:wrap; gap:1.5rem; align-items: stretch;">
                    <div class="dash-table-card dash-card" id="dash-debtors" style="width: calc(50% - 0.75rem); min-width:400px; overflow: hidden; min-height: 300px; display: flex; flex-direction: column; flex-grow: 1;">
                        <h3 style="display:flex; justify-content:space-between; align-items:center;" data-collapsible="true">
                            <span class="dash-section-title">Debtors (Top 10)</span>
                            <i class="fas fa-chevron-up toggle-icon" style="cursor:pointer; transition:transform 0.3s;" onclick="toggleCard(this)"></i>
                        </h3>
                        <div class="collapsible-content" style="display:flex; flex-direction:row; align-items:flex-start; gap:1.5rem; flex-wrap:wrap; flex-grow: 1; overflow-y: auto; overflow-x: auto;">
                            <div style="flex:1; min-width:200px; height:250px">
                                <canvas id="debtChart"></canvas>
                            </div>
                            <div style="flex:1.5; min-width:250px; max-height:100%; overflow-y:auto; overflow-x:auto; font-size:0.85rem;">
                                <table style="width:100%">
                                    <thead><tr><th>Apartment</th><th>Owner</th><th class="text-right">Debt</th></tr></thead>
                                    <tbody>
                                        ${debtorsRowsHtml}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                    
                    <div class="dash-table-card dash-card" id="dash-expenses" style="width: calc(50% - 0.75rem); min-width:400px; overflow: hidden; min-height: 300px; display: flex; flex-direction: column; flex-grow: 1;">
                        <h3 style="display:flex; justify-content:space-between; align-items:center;" data-collapsible="true">
                            <span class="dash-section-title">Expenses: Breakdown</span>
                            <i class="fas fa-chevron-up toggle-icon" style="cursor:pointer; transition:transform 0.3s;" onclick="toggleCard(this)"></i>
                        </h3>
                        <div class="collapsible-content" style="display:flex; flex-direction:row; align-items:flex-start; gap:1.5rem; flex-wrap:wrap; flex-grow: 1; overflow-y: auto; overflow-x: auto;">
                            <div style="flex:1; min-width:200px; height:250px">
                                <canvas id="expensesPieChart"></canvas>
                            </div>
                            <div style="flex:1.5; min-width:250px; max-height:100%; overflow-y:auto; overflow-x:auto; font-size:0.85rem;">
                                <table style="width:100%">
                                    <thead><tr><th>Group</th><th class="text-right">%</th><th class="text-right">Amount</th></tr></thead>
                                    <tbody>
                                        ${ebRows}
                                        <tr class="total-row"><td>Total</td><td class="text-right">100%</td><td class="text-right color-danger">${formatCurrency(ebTotal)}</td></tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;


        renderDashboardCharts(data);

        // Run scenario forecasts
        await Promise.all([
            window.generateForecastScenario(1),
            window.generateForecastScenario(2),
            window.generateForecastScenario(3)
        ]);
        window.switchDetailScenario(window.currentDetailScenarioIndex || 1);
        

    } catch (err) {
        contentArea.innerHTML = `<p class="color-danger">Dashboard error: ${err.message}</p>`;
    }
}

function renderDashboardCharts(data) {
    const debtCtx = document.getElementById('debtChart');
    const expCtx = document.getElementById('expensesPieChart');
    if (typeof Chart === 'undefined') return;
    
    const existingDebt = Chart.getChart("debtChart");
    if (existingDebt) existingDebt.destroy();
    
    const existingExp = Chart.getChart("expensesPieChart");
    if (existingExp) existingExp.destroy();

    const colors = ['#4a828f', '#588c73', '#bc6b7d', '#9e8565', '#5a7880', '#6f8b70', '#aa7d6f', '#b17487', '#83876e', '#937484', '#666974'];

    let topDebtors = [];
    let otherDebt = 0;
    if (data.debtors && data.debtors.length > 0) {
        const sorted = [...data.debtors].sort((a, b) => b.debt - a.debt);
        topDebtors = sorted.slice(0, 10);
        for(let i=10; i<sorted.length; i++) {
            otherDebt += sorted[i].debt;
        }
    }
    
    const pieLabels = topDebtors.map(d => `Кв. ${d.apartment || d.apt_number} - ${d.owner} (${formatCurrency(d.debt)} ₴)`);
    const pieData = topDebtors.map(d => d.debt);
    if (otherDebt > 0) {
        pieLabels.push('Other');
        pieData.push(otherDebt);
    }
    
    if(debtCtx && pieData.length > 0) {
        window.dashboardDebtChart = new Chart(debtCtx, {
            type: 'doughnut',
            data: {
                labels: pieLabels,
                datasets: [{
                    data: pieData,
                    backgroundColor: colors.slice(0, pieLabels.length),
                    borderWidth: 1,
                    borderColor: 'var(--bg-color)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: (ctx) => ` ${ctx.label}: ${formatCurrency(ctx.raw)} ₴` } }
                }
            }
        });
    }

    if (expCtx && data.expense_breakdown && data.expense_breakdown.length > 0) {
        const expLabels = data.expense_breakdown.map(e => e.group);
        const expData = data.expense_breakdown.map(e => e.amount);
        
        new Chart(expCtx, {
            type: 'doughnut',
            data: {
                labels: expLabels,
                datasets: [{
                    data: expData,
                    backgroundColor: colors.slice(0, expLabels.length),
                    borderWidth: 1,
                    borderColor: 'var(--bg-color)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: (ctx) => ` ${ctx.label}: ${formatCurrency(ctx.raw)} ₴` } }
                }
            }
        });
    }
}

// ── Resizable Columns ────────────────────────────────────────────────────────
function makeColumnsResizable(tableEl) {
    if (!tableEl) return;
    const ths = tableEl.querySelectorAll('thead th');
    if (!ths.length) return;

    // Set initial widths from computed style
    ths.forEach(th => {
        if (!th.style.width) {
            th.style.width = th.offsetWidth + 'px';
        }
    });

    ths.forEach(th => {
        // Skip if already has handle
        if (th.querySelector('.col-resize-handle')) return;
        const handle = document.createElement('div');
        handle.className = 'col-resize-handle';
        th.appendChild(handle);

        let startX, startW;
        handle.addEventListener('mousedown', (e) => {
            e.preventDefault();
            e.stopPropagation();
            startX = e.pageX;
            startW = th.offsetWidth;
            handle.classList.add('resizing');

            const onMove = (ev) => {
                const diff = ev.pageX - startX;
                const newW = Math.max(40, startW + diff);
                th.style.width = newW + 'px';
            };
            const onUp = () => {
                handle.classList.remove('resizing');
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
            };
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
    });
}

// Removed old custom month picker logic

// Apartments
async function renderApartments() {
    try {
        pageTitle.innerText = 'Квартири';
        if (state.apartments.length === 0) await fetchApartments();

        const hasChanges = Object.keys(state.pendingChanges).length > 0;

        const rows = state.apartments
            .filter(a => !a.number.includes('Total'))
            .map(a => {
                const pending = state.pendingChanges[a.id];
                const hasLiftExemption = pending !== undefined ? pending.has_lift_exemption : a.has_lift_exemption;

                return `
                <tr onclick="toggleInlineLogs(${a.id})" id="row-${a.id}" style="cursor:pointer">
                    <td>${a.number}</td>
                    <td>${a.owner_name || '—'}</td>
                    <td>${a.area_m2} м²</td>
                    <td onclick="event.stopPropagation()">
                        <input type="checkbox" ${!hasLiftExemption ? 'checked' : ''} onchange="queueLiftToggle(${a.id}, this.checked)">
                    </td>
                    <td class="${a.current_balance < 0 ? 'color-danger' : 'color-success'}">
                        ${formatCurrency(a.current_balance)} ₴
                    </td>
                    <td onclick="event.stopPropagation()">
                        <button class="btn btn-secondary btn-sm" onclick="editApartment(${a.id})" title="Edit">✏️</button>
                    </td>
                </tr>
                <tr id="logs-row-${a.id}" style="display:none" class="log-detail-row">
                    <td colspan="6" id="logs-content-${a.id}" style="padding: 1rem; background: rgba(255,255,255,0.02)">
                        Loading...
                    </td>
                </tr>`;
            }).join('');

        contentArea.innerHTML = `
            <div style="margin-bottom: 1.5rem; display:flex; justify-content: flex-end">
                <button id="btn-save-apartments" class="btn btn-primary" onclick="saveApartmentChanges()">💾 Save зміни</button>
            </div>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>№</th><th>Owner</th><th>Площа</th>
                            <th>Ліфт</th><th>Balance</th><th>Дії</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                    <tfoot>
                        <tr style="font-weight: 700; background: rgba(255,255,255,0.05)">
                            <td colspan="2">Загалом:</td>
                            <td>${state.apartments.reduce((s, a) => s + (a.area_m2 || 0), 0).toFixed(2)} м²</td>
                            <td></td>
                            <td class="${state.apartments.reduce((s, a) => s + (a.current_balance || 0), 0) < 0 ? 'color-danger' : 'color-success'}">
                                ${formatCurrency(state.apartments.reduce((s, a) => s + (a.current_balance || 0), 0))} ₴
                            </td>
                            <td></td>
                        </tr>
                    </tfoot>
                </table>
            </div>`;

        // Ensure button state is correct
        const btn = document.getElementById('btn-save-apartments');
        if (btn) btn.disabled = !hasChanges;
    } catch (err) {
        contentArea.innerHTML = `<p class="color-danger">Помилка: ${err.message}</p>`;
    }
}

function queueLiftToggle(id, isChecked) {
    const apt = state.apartments.find(a => a.id === id);
    if (!apt) return;

    const newExemption = !isChecked;
    if (newExemption === apt.has_lift_exemption) {
        delete state.pendingChanges[id];
    } else {
        state.pendingChanges[id] = { has_lift_exemption: newExemption };
    }

    // Update button state
    const btn = document.getElementById('btn-save-apartments');
    if (btn) btn.disabled = Object.keys(state.pendingChanges).length === 0;
}

async function saveApartmentChanges() {
    const btn = document.getElementById('btn-save-apartments');
    if (btn) { btn.disabled = true; btn.innerText = '⏳ Зберігаю...'; }

    try {
        for (const id in state.pendingChanges) {
            await fetch(`${API_BASE}/apartments/${id}/toggle-lift`, { method: 'POST' });
        }
        state.pendingChanges = {};
        state.needsRecalculation = true;
        updateGlobalUI();
        await fetchApartments();
        await renderSettings();
    } catch (err) {
        alert('Помилка при збереженні: ' + err.message);
        if (btn) { btn.disabled = false; btn.innerText = '💾 Save зміни'; }
    }
}

function updateGlobalUI() {
    const recalcBtn = document.getElementById('btn-recalculate');
    if (recalcBtn) {
        if (state.needsRecalculation) {
            recalcBtn.classList.add('pulse-animation');
            recalcBtn.innerHTML = '<i class="fas fa-sync"></i> Потрібен перерахунок';
        } else {
            recalcBtn.classList.remove('pulse-animation');
            recalcBtn.innerHTML = '<i class="fas fa-sync"></i> Recalculate';
        }
    }
}

async function toggleInlineLogs(id) {
    const logRow = document.getElementById(`logs-row-${id}`);
    const isVisible = logRow.style.display !== 'none';

    if (isVisible) {
        logRow.style.display = 'none';
    } else {
        // Close other open logs to keep it clean
        document.querySelectorAll('.log-detail-row').forEach(r => r.style.display = 'none');

        logRow.style.display = 'table-row';
        await fetchAndShowInlineLogs(id);
    }
}

async function fetchAndShowInlineLogs(id) {
    const content = document.getElementById(`logs-content-${id}`);
    const apt = state.apartments.find(a => a.id === id);

    try {
        const res = await fetch(`${API_BASE}/apartments/${id}/logs`);
        const logs = await res.json();

        const typeNames = {
            'adjustment': 'Корегування',
            'owner_change': 'Зміна власника',
            'area_change': 'Зміна площі'
        };

        const rows = logs.map(l => {
            let valStr = '';
            if (l.type === 'adjustment') valStr = `${l.amount.toFixed(2)} ₴ (${l.description || '—'})`;
            else if (l.type === 'owner_change') valStr = `${l.old_value || '—'} → ${l.new_value}`;
            else if (l.type === 'area_change') valStr = `${l.old_value} м² → ${l.new_value} м²`;

            return `
            <tr>
                <td>${new Date(l.date).toLocaleDateString('uk-UA')}</td>
                <td>${l.period || '—'}</td>
                <td>${typeNames[l.type] || l.type}</td>
                <td>${valStr}</td>
            </tr>`;
        }).join('');

        content.innerHTML = `
            <div class="table-container" style="background: transparent; box-shadow: none; border: 1px solid var(--border-color)">
                <table style="width: 100%; font-size: 0.85rem">
                    <thead>
                        <tr><th>Дата запису</th><th>Застосовано з</th><th>Type</th><th>Значення</th></tr>
                    </thead>
                    <tbody>
                        ${logs.length ? rows : '<tr><td colspan="4" style="text-align:center">Логів поки немає</td></tr>'}
                    </tbody>
                </table>
            </div>`;
    } catch (err) {
        content.innerHTML = `<p class="color-danger">Помилка: ${err.message}</p>`;
    }
}

// Transactions
async function renderTransactions() {
    try {
        pageTitle.innerText = 'Транзакції';

        // Fetch data if needed
        if (state.apartments.length === 0) await fetchApartments();
        if (state.categories.length === 0) await fetchCategories();
        if (state.contractors.length === 0) await fetchContractors();

        const res = await fetch(`${API_BASE}/transactions/`);
        let txs = await res.json();
        
        const resBank = await fetch(`${API_BASE}/bank/payments?posted=false`);
        let unpostedBank = await resBank.json();
        
        // Filter by date range
        txs = txs.filter(tx => tx.date >= state.startDate && tx.date <= state.endDate);

        // Compute extra fields for filtering and display
        txs = txs.map(tx => {
            const typeStr = tx.category ? (tx.category.type === 'income' ? 'Inflows' : 'Витрата') : '—';
            const groupStr = tx.category ? (tx.category.name || '—') : '—';
            const purposeStr = tx.description || '—';

            let counterpartyStr = tx.counterparty || '—';
            if (tx.apartment) counterpartyStr = 'Кв. ' + tx.apartment.number;
            else if (tx.contractor) counterpartyStr = tx.contractor.name;

            return {
                ...tx,
                _typeStr: typeStr,
                _groupStr: groupStr,
                _purposeStr: purposeStr,
                _counterpartyStr: counterpartyStr,
                _amountStr: formatCurrency(tx.amount)
            };
        });

        // Apply Search — match against ALL visible fields including formatted amount
        if (state.txSearch) {
            const s = state.txSearch.toLowerCase();
            txs = txs.filter(tx =>
                (tx.date && tx.date.toLowerCase().includes(s)) ||
                tx._typeStr.toLowerCase().includes(s) ||
                tx._groupStr.toLowerCase().includes(s) ||
                tx._purposeStr.toLowerCase().includes(s) ||
                tx._counterpartyStr.toLowerCase().includes(s) ||
                (tx.comment && tx.comment.toLowerCase().includes(s)) ||
                tx._amountStr.includes(s) ||
                String(tx.amount).includes(s)
            );
        }

        // Apply Sorting (default: date DESC)
        txs.sort((a, b) => {
            let valA, valB;
            switch (state.txSortCol) {
                case 'date': valA = a.date; valB = b.date; break;
                case 'type': valA = a._typeStr; valB = b._typeStr; break;
                case 'group': valA = a._groupStr; valB = b._groupStr; break;
                case 'purpose': valA = a._purposeStr; valB = b._purposeStr; break;
                case 'counterparty': valA = a._counterpartyStr; valB = b._counterpartyStr; break;
                case 'amount': valA = a.amount; valB = b.amount; break;
                case 'comment': valA = a.comment || ''; valB = b.comment || ''; break;
                default: valA = a.date; valB = b.date;
            }
            if (valA < valB) return state.txSortDesc ? 1 : -1;
            if (valA > valB) return state.txSortDesc ? -1 : 1;
            return 0;
        });

        if (state.showErrorsOnly) {
            txs = []; // Hide standard transactions
        }

        const rows = txs.map(tx => `
            <tr>
                <td>${tx.date}</td>
                <td>${tx._typeStr}</td>
                <td>${tx._groupStr}</td>
                <td>${tx._purposeStr}</td>
                <td>${tx._counterpartyStr}</td>
                <td class="${tx.amount < 0 ? 'color-danger' : 'color-success'}">${formatCurrency(tx.amount)} ₴</td>
                <td>${tx.comment || '—'}</td>
                <td style="white-space: nowrap;">
                    <button class="btn btn-secondary btn-sm" onclick="copyTransaction(${tx.id})" title="Копіювати">📄</button>
                    <button class="btn btn-secondary btn-sm" onclick="deleteTransaction(${tx.id})" title="Видалити" style="color: var(--danger-color); margin-left: 0.2rem;">🗑️</button>
                </td>
            </tr>`).join('');

        // Filter and sort bank rows
        unpostedBank = unpostedBank.filter(p => p.operation_date >= state.startDate && p.operation_date <= state.endDate);
        // Apply Search — match against ALL visible fields including formatted amount
        if (state.txSearch) {
            const s = state.txSearch.toLowerCase();
            unpostedBank = unpostedBank.filter(p => 
                (p.operation_date && p.operation_date.includes(s)) ||
                (p.payer_name && p.payer_name.toLowerCase().includes(s)) ||
                (p.correspondent_name && p.correspondent_name.toLowerCase().includes(s)) ||
                (p.purpose && p.purpose.toLowerCase().includes(s))
            );
        }

        if (state.showErrorsOnly) {
            unpostedBank = unpostedBank.filter(p => p.match_status === 'unrecognized' || p.match_status === 'unconfirmed');
        }
        
        const bankRows = unpostedBank.map(p => {
            const isExpense = p.amount < 0;
            let rowStyle = '';
            let tag = '';
            if (p.match_status === 'unrecognized') {
                rowStyle = 'border-left: 4px solid var(--danger); background: rgba(239, 68, 68, 0.05);';
                tag = '<span style="font-size:0.7rem; padding:2px 6px; border-radius:4px; background:var(--danger); color:#fff; font-weight:600">UNRECOGNIZED</span>';
            } else if (p.match_status === 'unconfirmed') {
                rowStyle = 'border-left: 4px solid var(--warning); background: rgba(245, 158, 11, 0.05);';
                tag = '<span style="font-size:0.7rem; padding:2px 6px; border-radius:4px; background:var(--warning); color:#fff; font-weight:600">UNCONFIRMED</span>';
            } else {
                rowStyle = 'border-left: 4px solid var(--success); background: rgba(16, 185, 129, 0.05);';
                tag = '<span style="font-size:0.7rem; padding:2px 6px; border-radius:4px; background:var(--success); color:#fff; font-weight:600">READY</span>';
            }
            const isMatched = p.match_status === 'matched' || p.match_status === 'mapped';
            const typeLabel = isExpense ? 'Витрата' : 'Inflows';
            
            let linkInfo = '—';
            let actionBtn = '';
            if (isExpense) {
                // For expenses, show contractor name as link info
                linkInfo = isMatched ? (p.correspondent_name || '—') : '—';
                // No manual map button needed for expenses — they auto-match to contractors
                if (!isMatched) {
                    actionBtn = `<button class="btn btn-secondary btn-sm" onclick="openBankMapModal(${p.id})">🔗 Зв'язати</button>`;
                }
            } else {
                // For income, show apartment info
                linkInfo = isMatched && p.apartment ? `Кв. ${p.apartment.number}` : (p.match_status === 'unconfirmed' && p.suggested_apartment ? `(Кв. ${p.suggested_apartment.number} ?)` : '—');
                actionBtn = `<button class="btn btn-secondary btn-sm" onclick="openBankMapModal(${p.id})">🔗 ${isMatched ? 'Змінити' : "Зв'язати"}</button>`;
            }
            
            return `
            <tr style="${rowStyle}">
                <td>${p.operation_date}</td>
                <td style="color: ${isExpense ? 'var(--danger)' : 'var(--success)'}">${typeLabel}</td>
                <td>Буфер (Банк)</td>
                <td><div style="max-width:250px" class="truncate-text" title="${p.payer_address || p.purpose || '—'}">${p.payer_address || p.purpose || '—'}</div></td>
                <td>${p.payer_name || p.correspondent_name || '—'} <div style="margin-top:4px">${tag}</div></td>
                <td class="${p.amount < 0 ? 'color-danger' : 'color-success'}">${formatCurrency(p.amount)} ₴</td>
                <td>${linkInfo}</td>
                <td style="white-space: nowrap;">
                    ${actionBtn}
                </td>
            </tr>`;
        }).join('');

        // Store to state for copy action
        state.transactions = txs;

        const sortTh = (col, label) => {
            const isActive = state.txSortCol === col;
            const arrow = isActive ? (state.txSortDesc ? '▼' : '▲') : '⇅';
            return `<th class="sortable ${isActive ? 'active' : ''}" onclick="setTxSort('${col}')">${label} <span class="sort-icon">${arrow}</span></th>`;
        };

        contentArea.innerHTML = `
            <div class="filters-bar" style="margin-bottom:1.5rem; display:flex; gap:0.5rem; align-items:flex-end; flex-wrap: wrap;">
                <div class="form-group" style="flex-grow:1; max-width: 250px;">
                    <label>Пошук транзакцій</label>
                    <input type="text" id="tx-search" class="form-control" placeholder="Пошук по всім полям..." value="${state.txSearch}">
                </div>
                
                <div style="margin-left:auto; display:flex; gap:0.5rem">
                    <button class="btn btn-secondary" onclick="document.getElementById('bank-csv-upload').click()" title="Імпорт виписки (CSV)">
                        <i class="fas fa-file-csv"></i> Завантажити CSV
                    </button>
                    <input type="file" id="bank-csv-upload" accept=".csv,.xls,.xlsx" style="display:none" onchange="uploadBankFile(event, 'csv')">
                    
                    <button class="btn btn-secondary" style="${state.showErrorsOnly ? 'background: var(--warning); color: #fff; border-color: var(--warning);' : ''}" onclick="toggleErrorsFilter()" title="Фільтр транзакцій, що потребують ручних дій">
                        <i class="fas fa-exclamation-triangle"></i> Показати з помилками
                    </button>
                    
                    <button class="btn btn-primary" onclick="syncGmailRegistries()" title="Автоматично стягнути реєстри з пошти за обраний період" style="background: var(--success); border-color: var(--success);">
                        <i class="fab fa-google"></i> Синхронізація Gmail
                    </button>
                    
                    ${unpostedBank.length > 0 ? `
                    <button class="btn btn-secondary" onclick="rematchBankPayments()">
                        <i class="fas fa-magic"></i> Recalculate зв'язки
                    </button>
                    <button class="btn btn-primary" onclick="postMatchedBankPayments()">
                        <i class="fas fa-check-double"></i> Провести всі зв'язані
                    </button>
                    ` : ''}

                    <button class="btn btn-primary" onclick="showAddTransactionModal()">
                        + Внести транзакцію
                    </button>
                </div>
            </div>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            ${sortTh('date', 'Дата')}
                            ${sortTh('type', 'Type')}
                            ${sortTh('group', 'Group')}
                            ${sortTh('purpose', 'Purpose')}
                            ${sortTh('counterparty', 'Контрагент')}
                            ${sortTh('amount', 'Amount')}
                            ${sortTh('comment', 'Коментар')}
                            <th>Дії</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${bankRows}
                        ${rows.length ? rows : '<tr><td colspan="8" class="text-center">Немає записів</td></tr>'}
                    </tbody>
                    <tfoot>
                        <tr style="font-weight: 700; background: rgba(255,255,255,0.05)">
                            <td colspan="5" class="text-right">Загалом:</td>
                            <td class="${txs.reduce((s, tx) => s + tx.amount, 0) < 0 ? 'color-danger' : 'color-success'}">
                                ${formatCurrency(txs.reduce((s, tx) => s + tx.amount, 0))} ₴
                            </td>
                            <td colspan="2"></td>
                        </tr>
                    </tfoot>
                </table>
            </div>`;

        // Add event listener for search
        const searchInput = document.getElementById('tx-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                state.txSearch = e.target.value;
                clearTimeout(window.txSearchTimeout);
                window.txSearchTimeout = setTimeout(() => renderTransactions(), 300);
            });
            searchInput.focus();
            searchInput.setSelectionRange(searchInput.value.length, searchInput.value.length);
        }
        // Make columns resizable
        const txTable = contentArea.querySelector('.table-container table');
        makeColumnsResizable(txTable);
    } catch (err) {
        contentArea.innerHTML = `<p class="color-danger">Помилка: ${err.message}</p>`;
    }
}

window.setTxSort = function (col) {
    if (state.txSortCol === col) {
        state.txSortDesc = !state.txSortDesc;
    } else {
        state.txSortCol = col;
        state.txSortDesc = (col === 'date');
    }
    renderTransactions();
};

window.toggleErrorsFilter = function() {
    state.showErrorsOnly = !state.showErrorsOnly;
    renderTransactions();
};

window.copyTransaction = function (txId) {
    const tx = state.transactions.find(t => t.id === txId);
    if (!tx) return;
    showAddTransactionModal(tx);
};

// ── Auto-determine counterparty type from category ───────────────────────────
function getCpTypeForCategory(cat) {
    if (!cat) return { cpType: 'none', label: '' };
    const name = (cat.name || '').toLowerCase();
    if (cat.type === 'income' && (name.includes('квартплата') || name.includes('мешканц'))) {
        return { cpType: 'apartment', label: 'Apartment (мешканець)' };
    }
    if (cat.type === 'income' && name.includes('договор')) {
        return { cpType: 'contractor_income', label: 'Контрагент (Договора)' };
    }
    if (cat.type === 'expense') {
        return { cpType: 'contractor_expense', label: 'Контрагент (Expenses)' };
    }
    return { cpType: 'manual', label: 'Контрагент' };
}

function renderCpField(cpType, selectedValue) {
    if (cpType === 'apartment') {
        const opts = state.apartments.filter(a => !a.number.includes('Total')).map(a =>
            `<option value="${a.id}" ${a.id == selectedValue ? 'selected' : ''}>Кв. ${a.number} (${a.owner_name || 'Невідомо'})</option>`
        ).join('');
        return `<select id="tx-cp-value" class="form-control"><option value="">-- Оберіть квартиру --</option>${opts}</select>`;
    }
    if (cpType === 'contractor_income') {
        const filtered = state.contractors.filter(c => c.default_category && c.default_category.type === 'income' && c.active);
        const opts = filtered.map(c =>
            `<option value="${c.id}" ${c.id == selectedValue ? 'selected' : ''}>${c.name}</option>`
        ).join('');
        return `<select id="tx-cp-value" class="form-control"><option value="">-- Оберіть контрагента --</option>${opts}${filtered.length === 0 ? '<option disabled>Додайте контрагентів в Налаштуваннях</option>' : ''}</select>`;
    }
    if (cpType === 'contractor_expense') {
        const filtered = state.contractors.filter(c => c.default_category && c.default_category.type === 'expense' && c.active);
        const opts = filtered.map(c =>
            `<option value="${c.id}" ${c.id == selectedValue ? 'selected' : ''}>${c.name}</option>`
        ).join('');
        return `<select id="tx-cp-value" class="form-control"><option value="">-- Оберіть контрагента --</option>${opts}${filtered.length === 0 ? '<option disabled>Додайте контрагентів в Налаштуваннях</option>' : ''}</select>`;
    }
    return `<input type="text" id="tx-cp-value" class="form-control" placeholder="Введіть назву контрагента" value="${selectedValue || ''}">`;
}

window.showAddTransactionModal = function (templateTx = null) {
    modalTitle.innerText = templateTx ? 'Копіювати транзакцію' : 'Внести транзакцію';

    let dDate = new Date().toISOString().split('T')[0];
    let dAmount = '';
    let dCatId = '';
    let dDesc = '';
    let dComment = '';
    let dCpValue = '';

    if (templateTx) {
        dDate = templateTx.date;
        dAmount = Math.abs(templateTx.amount);
        dCatId = templateTx.category_id;
        dDesc = templateTx.description || '';
        dComment = templateTx.comment || '';
        if (templateTx.apartment_id) dCpValue = templateTx.apartment_id;
        else if (templateTx.contractor_id) dCpValue = templateTx.contractor_id;
        else dCpValue = templateTx.counterparty || '';
    }

    // Sort categories alphabetically: by type label then by name
    const sortedCats = [...state.categories].sort((a, b) => {
        const typeA = a.type === 'income' ? 'Inflows' : 'Витрата';
        const typeB = b.type === 'income' ? 'Inflows' : 'Витрата';
        if (typeA !== typeB) return typeA.localeCompare(typeB, 'uk');
        return (a.name || '').localeCompare(b.name || '', 'uk');
    });

    const catOptions = sortedCats.map(c =>
        `<option value="${c.id}" ${c.id == dCatId ? 'selected' : ''}>[${c.type === 'income' ? 'Inflows' : 'Витрата'}] ${c.name}</option>`
    ).join('');

    const selectedCat = state.categories.find(c => c.id == dCatId);
    const { cpType, label: cpLabel } = getCpTypeForCategory(selectedCat);

    modalBody.innerHTML = `
        <form id="tx-form" onsubmit="submitTransaction(event)">
            <div class="form-group" style="margin-bottom:1rem">
                <label>Дата</label>
                <input type="date" id="tx-date" class="form-control" required value="${dDate}">
            </div>
            <div class="form-group" style="margin-bottom:1rem">
                <label>Категорія (Type / Group)</label>
                <select id="tx-category" class="form-control" required onchange="onTxCategoryChange()">
                    <option value="">-- Оберіть категорію --</option>
                    ${catOptions}
                    <option value="__edit__" style="font-style: italic">✏️ Edit список...</option>
                </select>
            </div>
            <div class="form-group" id="wrap-cp" style="margin-bottom:1rem; ${selectedCat ? '' : 'display:none'}">
                <label id="cp-label">${cpLabel || 'Контрагент'}</label>
                <div id="cp-field-container">${selectedCat ? renderCpField(cpType, dCpValue) : ''}</div>
            </div>
            <div class="form-group" style="margin-bottom:1rem">
                <label>Amount (₴)</label>
                <input type="number" id="tx-amount" class="form-control" step="0.01" required value="${dAmount}">
            </div>
            <div class="form-group" style="margin-bottom:1rem">
                <label>Purpose (опціонально)</label>
                <input type="text" id="tx-desc" class="form-control" value="${dDesc}">
            </div>
            <div class="form-group" style="margin-bottom:1rem">
                <label>Коментар (опціонально)</label>
                <input type="text" id="tx-comment" class="form-control" value="${dComment}">
            </div>
            <button type="submit" style="display:none" id="tx-hidden-submit"></button>
        </form>
    `;

    const submitBtn = document.getElementById('modal-submit');
    submitBtn.innerText = 'Save транзакцію';
    submitBtn.onclick = () => document.getElementById('tx-hidden-submit').click();
    modal.style.display = 'flex';
};

window.onTxCategoryChange = function () {
    const sel = document.getElementById('tx-category');
    if (sel.value === '__edit__') {
        closeModal();
        document.querySelectorAll('.sidebar-nav li').forEach(n => n.classList.remove('active'));
        const settingsNav = document.querySelector('[data-page="settings"]');
        if (settingsNav) settingsNav.classList.add('active');
        loadPage('settings');
        return;
    }
    const catId = parseInt(sel.value);
    const cat = state.categories.find(c => c.id === catId);
    const wrap = document.getElementById('wrap-cp');
    const label = document.getElementById('cp-label');
    const container = document.getElementById('cp-field-container');
    if (!cat) { wrap.style.display = 'none'; return; }
    const { cpType, label: cpLabel } = getCpTypeForCategory(cat);
    wrap.style.display = 'block';
    label.innerText = cpLabel;
    container.innerHTML = renderCpField(cpType, '');
};

window.submitTransaction = async function (e) {
    e.preventDefault();
    const catId = parseInt(document.getElementById('tx-category').value);
    const dateStr = document.getElementById('tx-date').value;
    let amount = parseFloat(document.getElementById('tx-amount').value);
    const desc = document.getElementById('tx-desc').value;
    const comment = document.getElementById('tx-comment').value;

    const cat = state.categories.find(c => c.id === catId);
    if (!cat) return alert('Оберіть категорію!');

    const { cpType } = getCpTypeForCategory(cat);
    let aptId = null, contId = null, counterparty = null;

    const cpEl = document.getElementById('tx-cp-value');
    if (cpEl) {
        const cpVal = cpEl.value;
        if (cpType === 'apartment') {
            aptId = parseInt(cpVal);
            if (isNaN(aptId)) return alert('Оберіть квартиру!');
        } else if (cpType === 'contractor_income' || cpType === 'contractor_expense') {
            contId = parseInt(cpVal);
            if (isNaN(contId)) return alert('Оберіть контрагента!');
        } else if (cpType === 'manual') {
            counterparty = cpVal.trim() || null;
        }
    }

    amount = Math.abs(amount);
    if (cat.type === 'expense') amount = -amount;

    const payload = {
        date: dateStr, amount, description: desc || null, comment: comment || null,
        counterparty, category_id: catId, contractor_id: contId, apartment_id: aptId
    };

    try {
        const btn = document.getElementById('modal-submit');
        btn.disabled = true; btn.innerText = 'Збереження...';
        const res = await fetch(`${API_BASE}/transactions/`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Невідома помилка'); }
        closeModal();
        state.needsRecalculation = true;
        updateGlobalUI();
        await renderTransactions();
    } catch (err) {
        alert('Помилка при збереженні: ' + err.message);
        document.getElementById('modal-submit').disabled = false;
        document.getElementById('modal-submit').innerText = 'Save транзакцію';
    };
}

window.deleteTransaction = async function(txId) {
    // if (!confirm('Ви впевнені, що хочете видалити цю транзакцію?')) return;
    try {
        const res = await fetch(`${API_BASE}/transactions/${txId}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Помилка видалення');
        state.needsRecalculation = true;
        updateGlobalUI();
        await renderTransactions();
    } catch (e) {
        alert(e.message);
    }
};

window.uploadTransactions = async function(event) {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const btn = document.querySelector('button[title="Імпорт транзакцій з ПриватБанку (Excel)"]');
        if (btn) btn.innerText = 'Loading...';

        const res = await fetch(`${API_BASE}/transactions/upload`, {
            method: 'POST',
            body: formData
        });

        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || 'Невідома помилка');
        }

        const data = await res.json();
        alert(`Імпорт завершено!\nЗавантажено нових транзакцій: ${data.imported}\nПропущено дублікатів: ${data.duplicates}`);
        
        state.needsRecalculation = true;
        updateGlobalUI();
        await renderTransactions();
    } catch (err) {
        alert('Помилка при завантаженні: ' + err.message);
    } finally {
        event.target.value = ''; // Reset input
    }
};

// ── Bank Integration ──────────────────────────────────────────────────────────

window.syncGmailRegistries = async function() {
    if (!state.startDate || !state.endDate) {
        alert("Будь ласка, оберіть період для синхронізації.");
        return;
    }
    
    try {
        const btn = document.querySelector('button[onclick="syncGmailRegistries()"]');
        if (btn) {
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Синхронізація...';
            btn.disabled = true;
        }
        
        const res = await fetch(`${API_BASE}/bank/sync-gmail`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                from_date: state.startDate,
                to_date: state.endDate
            })
        });
        
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Помилка синхронізації');
        }
        
        const data = await res.json();
        alert(`Синхронізація завершена!\nНових записів: ${data.inserted}\nПропущено дублікатів: ${data.skipped}`);
        
        await renderTransactions();
    } catch (err) {
        alert('Помилка синхронізації з Gmail: ' + err.message);
        const btn = document.querySelector('button[onclick="syncGmailRegistries()"]');
        if (btn) {
            btn.innerHTML = '<i class="fab fa-google"></i> Синхронізація Gmail';
            btn.disabled = false;
        }
    }
};

window.uploadBankFile = async function(event, type) {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    const endpoint = type === 'csv' ? '/bank/import-csv' : '/bank/import-registry';
    
    try {
        const res = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            body: formData
        });

        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || 'Невідома помилка');
        }

        const data = await res.json();
        alert(`Імпорт завершено!\nНових: ${data.inserted}\nПропущено дублікатів: ${data.skipped}\nЗнайдено помилок: ${data.errors ? data.errors.length : 0}`);
        
        await renderTransactions();
    } catch (err) {
        alert('Помилка при завантаженні: ' + err.message);
    } finally {
        event.target.value = ''; // Reset
    }
};

window.rematchBankPayments = async function() {
    try {
        const res = await fetch(`${API_BASE}/bank/re-match`, { method: 'POST' });
        if (!res.ok) throw new Error('Помилка');
        await renderTransactions();
    } catch (e) {
        alert(e.message);
    }
};

window.postMatchedBankPayments = async function() {
    try {
        const res = await fetch(`${API_BASE}/bank/post-matched`, { method: 'POST' });
        if (!res.ok) throw new Error('Помилка');
        const data = await res.json();
        alert(`Проведено платежів: ${data.posted}`);
        state.needsRecalculation = true;
        updateGlobalUI();
        await renderTransactions();
    } catch (e) {
        alert(e.message);
    }
};

window.openBankMapModal = async function(paymentId) {
    try {
        const res = await fetch(`${API_BASE}/bank/payments/${paymentId}`);
        const p = await res.json();
        
        modalTitle.innerText = `Зв'язати платіж`;
        
        const aptOpts = state.apartments.filter(a => !a.number.includes('Total')).map(a => 
            `<option value="${a.id}" ${p.suggested_apartment_id === a.id || p.apartment_id === a.id ? 'selected' : ''}>Кв. ${a.number} (${a.owner_name || 'Невідомо'})</option>`
        ).join('');
        
        let unconfirmedHtml = '';
        if (p.match_status === 'unconfirmed' && p.suggested_apartment) {
            unconfirmedHtml = `
                <div style="background:rgba(245, 158, 11, 0.1); border:1px solid var(--warning); padding:1rem; border-radius:8px; margin-bottom:1rem">
                    <p style="margin-bottom:0.5rem"><b>Система пропонує:</b> Кв. ${p.suggested_apartment.number} (Збіг: ${Math.round(p.match_score)}%)</p>
                    <div style="display:flex; gap:0.5rem">
                        <button class="btn btn-sm btn-primary" type="button" onclick="confirmBankPayment(${p.id})">Підтвердити</button>
                        <button class="btn btn-sm btn-secondary" type="button" onclick="rejectBankPayment(${p.id})">Відхилити</button>
                    </div>
                </div>
            `;
        }

        modalBody.innerHTML = `
            ${unconfirmedHtml}
            <div style="margin-bottom:1rem; font-size:0.9rem">
                <p><b>Платник:</b> ${p.payer_name || p.correspondent_name || '—'}</p>
                <p><b>Purpose/Адреса:</b> ${p.payer_address || p.purpose || '—'}</p>
                <p><b>Amount:</b> ${formatCurrency(p.amount)} ₴</p>
            </div>
            
            <form id="bank-map-form" onsubmit="submitBankMap(event, ${p.id})">
                <div class="form-group" style="margin-bottom:1rem">
                    <label>Оберіть квартиру</label>
                    <select id="bank-map-apt" class="form-control" required>
                        <option value="">-- Оберіть --</option>
                        ${aptOpts}
                    </select>
                </div>
                
                <div class="form-group" style="margin-bottom:1rem; padding:1rem; background:rgba(255,255,255,0.05); border-radius:8px">
                    <label style="display:flex; align-items:center; gap:0.5rem; cursor:pointer">
                        <input type="checkbox" id="bank-map-save" onchange="document.getElementById('bank-map-key-type-wrap').style.display = this.checked ? 'block' : 'none'">
                        <b>Запам'ятати для майбутніх платежів</b>
                    </label>
                    
                    <div id="bank-map-key-type-wrap" style="display:none; margin-top:1rem">
                        <label>Type ключа</label>
                        <select id="bank-map-key-type" class="form-control">
                            <option value="payer_name">Точний збіг платника (${p.payer_name || p.correspondent_name})</option>
                            <option value="address_substring">Містить в призначенні (${p.payer_address || p.purpose})</option>
                            <option value="both">Обидві умови</option>
                        </select>
                    </div>
                </div>
                <button type="submit" style="display:none" id="bank-map-hidden-submit"></button>
            </form>
        `;
        
        const submitBtn = document.getElementById('modal-submit');
        submitBtn.innerText = 'Save зв\'язок';
        submitBtn.onclick = () => document.getElementById('bank-map-hidden-submit').click();
        modal.style.display = 'flex';
        
    } catch (e) {
        alert(e.message);
    }
};

window.confirmBankPayment = async function(id) {
    try {
        const res = await fetch(`${API_BASE}/bank/payments/${id}/confirm`, { method: 'POST' });
        if (!res.ok) throw new Error('Помилка');
        closeModal();
        await renderTransactions();
    } catch (e) { alert(e.message); }
};

window.rejectBankPayment = async function(id) {
    try {
        const res = await fetch(`${API_BASE}/bank/payments/${id}/reject`, { method: 'POST' });
        if (!res.ok) throw new Error('Помилка');
        closeModal();
        await renderTransactions();
    } catch (e) { alert(e.message); }
};

window.submitBankMap = async function(e, id) {
    e.preventDefault();
    const aptId = document.getElementById('bank-map-apt').value;
    const save = document.getElementById('bank-map-save').checked;
    const keyType = document.getElementById('bank-map-key-type').value;
    
    if (!aptId) return alert('Оберіть квартиру');
    
    try {
        const btn = document.getElementById('modal-submit');
        btn.disabled = true; btn.innerText = 'Збереження...';
        
        const res = await fetch(`${API_BASE}/bank/payments/${id}/map`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                apartment_id: parseInt(aptId),
                save_mapping: save,
                key_type: save ? keyType : null
            })
        });
        
        if (!res.ok) throw new Error('Помилка сервера');
        
        closeModal();
        await renderTransactions();
    } catch (err) {
        alert('Помилка: ' + err.message);
        document.getElementById('modal-submit').disabled = false;
        document.getElementById('modal-submit').innerText = 'Save зв\'язок';
    }
};

async function renderCharges() {
    try {
        pageTitle.innerText = 'Нарахування та Оплати';
        if (state.apartments.length === 0) await fetchApartments();

        contentArea.innerHTML = `
            <div class="filters-bar" style="margin-bottom:1.5rem; display:flex; gap:1rem; align-items:flex-end; flex-wrap:wrap">
                <div style="flex-grow:1"></div>
                <div id="recalc-status" style="font-size:0.9rem; margin-bottom:0.5rem"></div>
                <button class="btn btn-secondary" onclick="exportMainReport()" style="margin-left:auto">
                    <i class="fas fa-file-export"></i> Експорт (Excel/CSV)
                </button>
            </div>
            <div class="table-container" style="overflow-x: auto;">
                <table id="charges-report-table">
                    <thead id="report-header"></thead>
                    <tbody id="report-body">
                        <tr><td colspan="10" style="text-align:center">Завантаження даних...</td></tr>
                    </tbody>
                    <tfoot id="report-footer"></tfoot>
                </table>
            </div>`;

        await fetchAndRenderReport();

    } catch (err) {
        contentArea.innerHTML = `<p class="color-danger">Помилка: ${err.message}</p>`;
    }
}

// updateReportRange removed, using global date range

async function fetchAndRenderReport() {
    const tbody = document.getElementById('report-body');
    const thead = document.getElementById('report-header');
    if (!tbody || !thead) return;

    try {
        const res = await fetch(`${API_BASE}/charges/report`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                start_period: state.startDate.substring(0, 7),
                end_period: state.endDate.substring(0, 7)
            })
        });
        const rawData = await res.json();

        if (rawData.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" style="text-align:center">Немає даних</td></tr>';
            return;
        }

        // Normalize backend response to match frontend expectations
        const data = rawData.map(item => {
            let runBal = item.start_balance;
            const normalizedMonthly = (item.monthly_details || []).map(md => {
                const mStart = runBal;
                const mCharge = md.charge || 0;
                const mPay = md.payment || 0;
                runBal = mStart - mCharge + mPay;
                return {
                    period: md.period,
                    maintenance: md.maintenance_fee || 0,
                    lift: md.lift_fee || 0,
                    gas: md.gas_fee || 0,
                    adjustment: md.adjustment || 0,
                    total_charged: mCharge,
                    paid: mPay,
                    start_balance: mStart,
                    end_balance: runBal,
                    payment: mPay
                };
            });
            return {
                apartment: {
                    id: item.apartment_id,
                    number: item.apartment_number,
                    owner_name: item.owner_name
                },
                apartment_id: item.apartment_id,
                summary: {
                    start_balance: item.start_balance,
                    end_balance: item.end_balance,
                    total_charged: item.total_charges,
                    total_paid: item.total_payments
                },
                start_balance: item.start_balance,
                end_balance: item.end_balance,
                monthly_details: normalizedMonthly
            };
        });

        const months = data[0].monthly_details.map(m => m.period);
        const isSingleMonth = months.length === 1;

        if (isSingleMonth) {
            thead.innerHTML = `
                <tr>
                    <th>№ кв.</th>
                    <th>П.І.Б.</th>
                    <th class="text-right">Поч. борг</th>
                    <th class="text-right">Утримання</th>
                    <th class="text-right">Ліфт</th>
                    <th class="text-right">Газ</th>
                    <th class="text-right">Корегув.</th>
                    <th class="text-right">Нараховано</th>
                    <th class="text-right">Сплачено</th>
                    <th class="text-right">Кінц. борг</th>
                </tr>`;
        } else {
            thead.innerHTML = `
                <tr>
                    <th>№ кв.</th>
                    <th>П.І.Б.</th>
                    <th class="text-right">Поч. борг<br><small>(${formatPeriod(months[0])})</small></th>
                    <th class="text-right">Нараховано<br><small>(За період)</small></th>
                    <th class="text-right">Сплачено<br><small>(За період)</small></th>
                    <th class="text-right">Кінц. борг<br><small>(${formatPeriod(months[months.length-1])})</small></th>
                    <th>Details Breakdown</th>
                </tr>`;
        }

        let html = '';
        const totals = { start: 0, maint: 0, lift: 0, gas: 0, adj: 0, charged: 0, paid: 0, end: 0 };

        data.forEach(item => {
            const sum = item.summary;
            totals.start += sum.start_balance;
            totals.charged += sum.total_charged;
            totals.paid += sum.total_paid;
            totals.end += sum.end_balance;

            if (isSingleMonth) {
                const md = item.monthly_details[0];
                totals.maint += md.maintenance;
                totals.lift += md.lift;
                totals.gas += md.gas;
                totals.adj += md.adjustment;

                html += `
                    <tr>
                        <td><b>${item.apartment.number}</b></td>
                        <td><div class="truncate-text" style="max-width:120px" title="${item.apartment.owner_name}">${item.apartment.owner_name || '—'}</div></td>
                        <td class="text-right ${md.start_balance < 0 ? 'color-danger' : 'color-success'}">${formatCurrency(md.start_balance)}</td>
                        <td class="text-right">${formatCurrency(md.maintenance)}</td>
                        <td class="text-right">${formatCurrency(md.lift)}</td>
                        <td class="text-right">${formatCurrency(md.gas)}</td>
                        <td class="text-right">${formatCurrency(md.adjustment)}</td>
                        <td class="text-right" style="font-weight:600">${formatCurrency(md.total_charged)}</td>
                        <td class="text-right color-success" style="font-weight:600">${formatCurrency(md.paid)}</td>
                        <td class="text-right ${md.end_balance < 0 ? 'color-danger' : 'color-success'}"><b>${formatCurrency(md.end_balance)}</b></td>
                    </tr>`;
            } else {
                html += `
                    <tr>
                        <td><b>${item.apartment.number}</b></td>
                        <td><div class="truncate-text" style="max-width:120px" title="${item.apartment.owner_name}">${item.apartment.owner_name || '—'}</div></td>
                        <td class="text-right ${sum.start_balance < 0 ? 'color-danger' : 'color-success'}">${formatCurrency(sum.start_balance)}</td>
                        <td class="text-right" style="font-weight:600">${formatCurrency(sum.total_charged)}</td>
                        <td class="text-right color-success" style="font-weight:600">${formatCurrency(sum.total_paid)}</td>
                        <td class="text-right ${sum.end_balance < 0 ? 'color-danger' : 'color-success'}"><b>${formatCurrency(sum.end_balance)}</b></td>
                        <td class="text-center">
                            <button class="btn btn-secondary btn-sm" onclick="toggleApartmentHistory(this.closest('tr'), ${item.apartment.id})">
                                <i class="fas fa-chevron-down"></i>
                            </button>
                        </td>
                    </tr>
                    <tr id="history-${item.apartment.id}" class="history-row" style="display:none">
                        <td colspan="7" style="padding: 0; background: rgba(0,0,0,0.2)">
                            <table style="width:100%; font-size:0.85rem; margin:0">
                                <thead>
                                    <tr style="background:transparent; border-bottom:1px solid rgba(255,255,255,0.1)">
                                        <th>Month</th>
                                        <th class="text-right">Поч. борг</th>
                                        <th class="text-right">Утрим.</th>
                                        <th class="text-right">Ліфт</th>
                                        <th class="text-right">Газ</th>
                                        <th class="text-right">Корег.</th>
                                        <th class="text-right">Нарах.</th>
                                        <th class="text-right">Сплачено</th>
                                        <th class="text-right">Кінц. борг</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${item.monthly_details.map(md => `
                                    <tr>
                                        <td>${formatPeriod(md.period)}</td>
                                        <td class="text-right ${md.start_balance < 0 ? 'color-danger' : ''}">${formatCurrency(md.start_balance)}</td>
                                        <td class="text-right">${formatCurrency(md.maintenance)}</td>
                                        <td class="text-right">${formatCurrency(md.lift)}</td>
                                        <td class="text-right">${formatCurrency(md.gas)}</td>
                                        <td class="text-right">${formatCurrency(md.adjustment)}</td>
                                        <td class="text-right">${formatCurrency(md.total_charged)}</td>
                                        <td class="text-right color-success">${formatCurrency(md.paid)}</td>
                                        <td class="text-right ${md.end_balance < 0 ? 'color-danger' : ''}">${formatCurrency(md.end_balance)}</td>
                                    </tr>`).join('')}
                                </tbody>
                            </table>
                        </td>
                    </tr>`;
            }
        });

        tbody.innerHTML = html;

        let footerCells = '';
        if (isSingleMonth) {
            footerCells = `
                <td class="text-right ${totals.start < 0 ? 'color-danger' : 'color-success'}">${formatCurrency(totals.start)} ₴</td>
                <td class="text-right">${formatCurrency(totals.maint)} ₴</td>
                <td class="text-right">${formatCurrency(totals.lift)} ₴</td>
                <td class="text-right">${formatCurrency(totals.gas)} ₴</td>
                <td class="text-right">${formatCurrency(totals.adj)} ₴</td>
                <td class="text-right">${formatCurrency(totals.charged)} ₴</td>
                <td class="text-right color-success">${formatCurrency(totals.paid)} ₴</td>
                <td class="text-right ${totals.end < 0 ? 'color-danger' : 'color-success'}">${formatCurrency(totals.end)} ₴</td>
            `;
        } else {
            footerCells = `
                <td class="text-right ${totals.start < 0 ? 'color-danger' : 'color-success'}">${formatCurrency(totals.start)} ₴</td>
                <td class="text-right">${formatCurrency(totals.charged)} ₴</td>
                <td class="text-right color-success">${formatCurrency(totals.paid)} ₴</td>
                <td class="text-right ${totals.end < 0 ? 'color-danger' : 'color-success'}">${formatCurrency(totals.end)} ₴</td>
                <td></td>
            `;
        }

        document.getElementById('report-footer').innerHTML = `
            <tr style="font-weight: 700; background: rgba(255,255,255,0.08)">
                <td colspan="2">ЗАГАЛОМ:</td>
                ${footerCells}
            </tr>
        `;

    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="10" class="color-danger">Помилка завантаження звіту: ${err.message}</td></tr>`;
    }
}

function toggleMonthExpand(month) {
    state.expandedMonth = (state.expandedMonth === month) ? null : month;
    fetchAndRenderReport();
}

function formatPeriod(p) {
    const [y, m] = p.split('-');
    const months = ['січ', 'лют', 'бер', 'квіт', 'трав', 'черв', 'лип', 'серп', 'вер', 'жовт', 'лист', 'груд'];
    return `${months[parseInt(m) - 1]}., ${y}`;
}

function toggleApartmentHistory(row, aptId) {
    const detailRow = document.getElementById(`history-${aptId}`);
    if (!detailRow) return;
    const isVisible = detailRow.style.display !== 'none';
    detailRow.style.display = isVisible ? 'none' : 'table-row';
    row.classList.toggle('expanded', !isVisible);
}

// ── Export Functions ──────────────────────────────────────────────────────────
async function exportMainReport() {
    try {
        const res = await fetch(`${API_BASE}/charges/report`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                start_period: state.startPeriod,
                end_period: state.endPeriod
            })
        });
        const data = await res.json();
        if (!data || data.length === 0) return alert('Немає даних для експорту');

        const months = data[0].monthly_details.map(m => m.period);
        const isSingleMonth = months.length === 1;

        let csv = [];
        // Header
        if (isSingleMonth) {
            csv.push(['Кв.', 'ПІБ', 'Поч. борг', 'Утримання', 'Ліфт', 'Газ', 'Корегув.', 'Нараховано', 'Сплачено', 'Кін. борг'].join(';'));
        } else {
            let row1 = ['Кв.', 'ПІБ', 'Поч. борг'];
            months.forEach(m => {
                if (state.expandedMonth === m) row1.push(`${m} (Утрим.)`, `${m} (Ліфт)`, `${m} (Газ)`, `${m} (Кор.)`, `${m} (Сплачено)`, `${m} (Debt)`);
                else row1.push(m);
            });
            row1.push('Кін. борг');
            csv.push(row1.join(';'));
        }

        // Body
        data.forEach(row => {
            let csvRow = [row.apartment_number, `"${row.owner_name || ''}"`, row.start_balance.toFixed(2)];

            if (isSingleMonth) {
                const m = row.monthly_details[0];
                csvRow.push(
                    m.maintenance_fee.toFixed(2),
                    m.lift_fee.toFixed(2),
                    m.gas_fee.toFixed(2),
                    m.adjustment.toFixed(2),
                    m.charge.toFixed(2),
                    m.payment.toFixed(2),
                    row.end_balance.toFixed(2)
                );
            } else {
                let runningBalance = row.start_balance;
                row.monthly_details.forEach(m => {
                    runningBalance = runningBalance - m.charge + m.payment;
                    if (state.expandedMonth === m.period) {
                        csvRow.push(
                            m.maintenance_fee.toFixed(2),
                            m.lift_fee.toFixed(2),
                            m.gas_fee.toFixed(2),
                            m.adjustment.toFixed(2),
                            m.payment.toFixed(2),
                            runningBalance.toFixed(2)
                        );
                    } else {
                        csvRow.push(runningBalance.toFixed(2));
                    }
                });
                csvRow.push(row.end_balance.toFixed(2));
            }
            csv.push(csvRow.join(';'));
        });

        downloadCSV(csv.join('\n'), `Report_${state.startPeriod}_${state.endPeriod}.csv`);
    } catch (err) {
        console.error(err);
        alert('Помилка при експорті: ' + err.message);
    }
}

async function exportApartmentHistory(aptId, aptNum) {
    try {
        const res = await fetch(`${API_BASE}/charges/report`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                start_period: state.startPeriod,
                end_period: state.endPeriod
            })
        });
        const data = await res.json();
        const row = data.find(r => r.apartment_id === aptId);
        if (!row) return alert('Квартиру не знайдено');

        let csv = [['Місяць', 'Debt на поч.', 'Утримання', 'Ліфт', 'Газ', 'Корегув.', 'Сплачено', 'Debt на кін.'].join(';')];
        let rb = row.start_balance;

        row.monthly_details.forEach(m => {
            const startB = rb;
            rb = rb - m.charge + m.payment;
            csv.push([
                m.period,
                startB.toFixed(2),
                m.maintenance_fee.toFixed(2),
                m.lift_fee.toFixed(2),
                m.gas_fee.toFixed(2),
                m.adjustment.toFixed(2),
                m.payment.toFixed(2),
                rb.toFixed(2)
            ].join(';'));
        });

        downloadCSV(csv.join('\n'), `History_Apt_${aptNum}_${state.startPeriod}_${state.endPeriod}.csv`);
    } catch (err) {
        console.error(err);
        alert('Помилка при експорті історії: ' + err.message);
    }
}

function downloadCSV(csvContent, filename) {
    const BOM = '\uFEFF';
    const blob = new Blob([BOM + csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

async function recalculateAll() {
    const btn = document.getElementById('btn-recalculate');
    const statusEl = document.getElementById('recalc-status');
    if (btn) {
        btn.disabled = true;
        const originalHTML = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        try {
            const startD = new Date(state.startDate);
            const endD = new Date(state.endDate);
            let curr = new Date(startD);
            curr.setDate(1);
            while (curr <= endD) {
                const p = curr.toISOString().substring(0, 7);
                await fetch(`${API_BASE}/charges/calculate`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ period: p })
                });
                curr.setMonth(curr.getMonth() + 1);
            }
            state.needsRecalculation = false;
            updateGlobalUI();
            if (statusEl) {
                statusEl.innerText = `✅ Перерахунок завершено`;
                statusEl.style.color = 'var(--success)';
            }
            if (state.currentPage === 'charges') await fetchAndRenderReport();
            if (state.currentPage === 'dashboard') await renderDashboard();
        } catch (err) {
            if (statusEl) {
                statusEl.innerText = `❌ Помилка: ${err.message}`;
                statusEl.style.color = 'var(--danger)';
            }
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalHTML;
            setTimeout(() => { if(statusEl) statusEl.innerText = ''; }, 3000);
        }
    }
}

function updateGlobalUI() {
    const btn = document.getElementById('btn-recalculate');
    if (!btn) return;

    if (state.needsRecalculation) {
        btn.classList.add('pulse');
        btn.style.opacity = '1';
        btn.style.filter = 'none';
    } else {
        btn.classList.remove('pulse');
        btn.style.opacity = '0.7';
        btn.style.filter = 'grayscale(0.5)';
    }
}

// Reports
async function renderReports() {
    pageTitle.innerText = 'Друк';
    if (state.apartments.length === 0) await fetchApartments();

    let selectedApts = JSON.parse(localStorage.getItem('printSelectedApts') || '[]');
    if (selectedApts.length === 0 && !localStorage.getItem('printSelectedApts')) {
        selectedApts = state.apartments.map(a => a.id);
        localStorage.setItem('printSelectedApts', JSON.stringify(selectedApts));
    }

    contentArea.innerHTML = `
        <div class="print-page-layout" style="display:flex; gap: 2rem; align-items: flex-start;">
            <!-- Ліва частина: Панель керування -->
            <div style="flex: 0 0 350px; display: flex; flex-direction: column; gap: 1.5rem;">
                
                <div class="stat-card">
                    <h3>🖨️ Налаштування друку</h3>
                    
                    <div style="margin-top: 1rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                            <label style="font-weight: 600;">Квартири для друку</label>
                            <div>
                                <button class="btn btn-sm btn-secondary" onclick="selectAllPrintApts(true)" style="padding: 0.2rem 0.5rem; font-size:0.75rem">Всі</button>
                                <button class="btn btn-sm btn-secondary" onclick="selectAllPrintApts(false)" style="padding: 0.2rem 0.5rem; font-size:0.75rem">Жодної</button>
                            </div>
                        </div>
                        <div class="apt-filter-list" style="max-height: 250px; overflow-y: auto; border: 1px solid var(--border-color); border-radius: 4px; padding: 0.5rem; background: rgba(0,0,0,0.1);">
                            ${state.apartments.map(a => `
                                <label style="display: flex; align-items: center; gap: 0.5rem; padding: 0.35rem 0; cursor: pointer; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                    <input type="checkbox" class="print-apt-cb" value="${a.id}" ${selectedApts.includes(a.id) ? 'checked' : ''} onchange="savePrintApts()">
                                    <b>№ ${a.number}</b> <span style="color:var(--text-secondary); font-size:0.8rem">(${a.owner_name || '—'})</span>
                                </label>
                            `).join('')}
                        </div>
                    </div>

                    <button class="btn btn-primary" style="width: 100%; margin-top: 1.5rem; padding: 1rem; font-size: 1.1rem;" onclick="printReceipts()">
                        <i class="fas fa-file-invoice"></i> Сформувати квитанції
                    </button>
                </div>

                <div class="stat-card">
                    <h3>📋 Список боржників</h3>
                    <p style="color:var(--text-secondary); margin-bottom: 1rem; font-size: 0.9rem;">Генерація списку квартир з від'ємним балансом (боргом) на поточний момент.</p>
                    <button class="btn btn-secondary" style="width: 100%;" onclick="renderDebtors()">Показати боржників</button>
                </div>
            </div>

            <!-- Права частина: Зона попереднього перегляду -->
            <div class="stat-card" style="flex: 1; min-height: 500px; display: flex; flex-direction: column;">
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 1rem; margin-bottom: 1rem;">
                    <h3 style="margin: 0;">Попередній перегляд</h3>
                    <button class="btn btn-primary" onclick="window.print()" id="btn-print-action" style="display:none;">
                        <i class="fas fa-print"></i> Друкувати
                    </button>
                </div>
                <div id="print-preview-area" style="flex: 1; overflow-y: auto; background: var(--bg-card); border: 1px dashed var(--border-color); border-radius: 4px; display: flex; justify-content: center; align-items: center; padding: 1rem;">
                    <span style="color: var(--text-secondary);">Оберіть дію ліворуч, щоб побачити результат тут</span>
                </div>
            </div>
        </div>`;
}

window.selectAllPrintApts = function (selectAll) {
    const cbs = document.querySelectorAll('.print-apt-cb');
    cbs.forEach(cb => cb.checked = selectAll);
    savePrintApts();
};

window.savePrintApts = function () {
    const cbs = document.querySelectorAll('.print-apt-cb:checked');
    const selected = Array.from(cbs).map(cb => parseInt(cb.value));
    localStorage.setItem('printSelectedApts', JSON.stringify(selected));
};

async function printReceipts() {
    const previewArea = document.getElementById('print-preview-area');
    const printBtn = document.getElementById('btn-print-action');
    if (!previewArea) return;
    
    try {
        previewArea.innerHTML = '<div class="loader">Формування...</div>';
        
        if (state.apartments.length === 0) await fetchApartments();

        let selectedApts = JSON.parse(localStorage.getItem('printSelectedApts') || '[]');
        if (selectedApts.length === 0) {
            previewArea.innerHTML = '<span style="color: var(--danger);">Будь ласка, оберіть хоча б одну квартиру для друку.</span>';
            if (printBtn) printBtn.style.display = 'none';
            return;
        }

        const period = state.startDate.substring(0, 7);

        // Fetch charges to get owner_name and area_m2 for that period
        const chargesRes = await fetch(`${API_BASE}/charges/?period=${period}`);
        const charges = await chargesRes.json();
        const chargeMap = Object.fromEntries(charges.map(c => [c.apartment_id, c]));

        // Fetch report to get accurate start/end balances and payments
        const reportRes = await fetch(`${API_BASE}/charges/report`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ start_period: period, end_period: period })
        });
        const reportData = await reportRes.json();
        const reportMap = Object.fromEntries(reportData.map(r => [r.apartment_id, r]));

        const aptMap = Object.fromEntries(state.apartments.map(a => [a.id, a]));

        // Filter and map data
        const receiptsToPrint = selectedApts.map(id => {
            const apt = aptMap[id];
            const ch = chargeMap[id];
            const rep = reportMap[id];
            if (!apt || !ch || !rep) return null;
            return { apt, ch, rep };
        }).filter(Boolean);

        if (receiptsToPrint.length === 0) {
            previewArea.innerHTML = `<span style="color: var(--danger);">Немає даних (нарахувань) за обраний період (${period}) для обраних квартир. Перерахуйте період у розділі "Нарахування".</span>`;
            if (printBtn) printBtn.style.display = 'none';
            return;
        }

        const y = parseInt(period.split('-')[0]);
        const m = parseInt(period.split('-')[1]);
        const dateStart = new Date(y, m - 1, 0);
        const dateEnd = new Date(y, m, 0);

        const startPeriodFormatted = `${String(dateStart.getDate()).padStart(2, '0')}-${String(dateStart.getMonth() + 1).padStart(2, '0')}-${dateStart.getFullYear()}`;
        const endPeriodFormatted = `${String(dateEnd.getDate()).padStart(2, '0')}-${String(dateEnd.getMonth() + 1).padStart(2, '0')}-${dateEnd.getFullYear()}`;

        const monthsUaShort = ['січ', 'лют', 'бер', 'квіт', 'трав', 'черв', 'лип', 'серп', 'вер', 'жовт', 'лист', 'груд'];
        const periodStr = `${monthsUaShort[m - 1]}-${String(y).slice(-2)}`;

        const html = '<div class="receipt-grid preview-grid" id="print-area">' +
            receiptsToPrint.map(data => {
                const { apt, ch, rep } = data;
                const owner = ch.owner_name || apt.owner_name || '—';
                const area = ch.area_m2 || apt.area_m2 || 0;

                const startDebt = rep.start_balance < 0 ? Math.abs(rep.start_balance) : -rep.start_balance;
                const endDebt = rep.end_balance < 0 ? Math.abs(rep.end_balance) : -rep.end_balance;

                return `
                <div class="receipt">
                    <div class="r-header">
                        <div style="font-weight:bold; text-align:center;">ЖБК № 102 "Заполярье"</div>
                        <div style="text-align:center; font-size:0.8em;">Р/Р UA803052990000026005050281468 ПАТ КБ "ПРИВАТБАНК"</div>
                        <div style="text-align:center; font-size:0.8em;">МФО 305299 ОКПО 23025161</div>
                    </div>
                    <hr class="r-line">
                    <div class="r-row"><span>Абонент:</span> <span><b>${owner}</b></span></div>
                    <div class="r-row"><span>Адреса:</span> <span>вул. Михайла Грушевського, буд.14, кв <b>${apt.number}</b></span></div>
                    <div class="r-row"><span><b>Загальна площ.м²</b></span> <span><b>${area.toFixed(2)}</b></span></div>
                    <hr class="r-line">
                    <div class="r-row r-small"><span>1. За екс. витрати за 1м² з 01.01.2020</span> <span>4,40 грн.</span></div>
                    <div class="r-row"><span><b>Ітого</b></span> <span><b>${ch.maintenance_fee.toFixed(2)} грн.</b></span></div>
                    <hr class="r-line">
                    <div class="r-row r-small"><span>2. За тех.обслуговування систем газопостачання<br>за 1м² з 01.01.2022</span> <span>0,47 грн.</span></div>
                    <div class="r-row"><span><b>Ітого</b></span> <span><b>${ch.gas_fee.toFixed(2)} грн.</b></span></div>
                    <hr class="r-line">
                    <div class="r-row r-small"><span>3. За тех.обслуговування ліфтів за 1м²</span> <span>0,90 грн.</span></div>
                    <div class="r-row"><span><b>Ітого</b></span> <span><b>${ch.lift_fee.toFixed(2)} грн.</b></span></div>
                    <hr class="r-line">
                    <div class="r-row"><span>Нараховано <b>${periodStr}</b></span> <span><b>${ch.total.toFixed(2)} грн.</b></span></div>
                    <div class="r-row"><span>Корегування</span> <span>${ch.adjustment.toFixed(2)} грн.</span></div>
                    <div class="r-row"><span><b>Debt</b> ${startPeriodFormatted}</span> <span><b>${startDebt.toFixed(2)} грн.</b></span></div>
                    <div class="r-row"><span><b>Сплачено</b> ${periodStr}</span> <span><b>${rep.monthly_details[0].payment.toFixed(2)} грн.</b></span></div>
                    <div class="r-row r-total"><span><b>Debt</b> ${endPeriodFormatted}</span> <span><b>${endDebt.toFixed(2)} грн.</b></span></div>
                    <hr class="r-line">
                    <div class="r-footer">
                        <div>бухгалтер Олена Олександрівна тел. 098 206 0931</div>
                        <div>приймальний день субота з 12<sup>00</sup> до 16<sup>00</sup></div>
                    </div>
                </div>`;
            }).join('') + '</div>';

        previewArea.style.alignItems = 'flex-start';
        previewArea.innerHTML = html;
        if (printBtn) printBtn.style.display = 'block';

        // Set global print area for window.print()
        const oldPrint = document.getElementById('global-print-area');
        if (oldPrint) oldPrint.remove();
        
        const globalPrintArea = document.createElement('div');
        globalPrintArea.id = 'global-print-area';
        globalPrintArea.className = 'print-container';
        globalPrintArea.innerHTML = html;
        document.body.appendChild(globalPrintArea);

    } catch (err) {
        previewArea.innerHTML = `<span class="color-danger">Помилка: ${err.message}</span>`;
    }
}

async function renderDebtors() {
    const previewArea = document.getElementById('print-preview-area');
    const printBtn = document.getElementById('btn-print-action');
    if (!previewArea) return;

    try {
        previewArea.innerHTML = '<div class="loader">Loading...</div>';
        if (state.apartments.length === 0) await fetchApartments();

        const debtors = state.apartments.filter(a => (a.current_balance || 0) < 0).sort((a, b) => a.current_balance - b.current_balance);

        const rows = debtors.map(a => `
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid var(--border-color);">${a.number}</td>
                <td style="padding: 8px; border-bottom: 1px solid var(--border-color);">${a.owner_name || '—'}</td>
                <td style="padding: 8px; border-bottom: 1px solid var(--border-color);" class="color-danger"><b>${formatCurrency(Math.abs(a.current_balance))} ₴</b></td>
            </tr>`).join('');

        const html = `
            <div id="print-area" style="width: 100%; max-width: 600px; margin: 0 auto; color: var(--text-color);">
                <h2 style="text-align:center; margin-bottom: 1rem;">Список боржників (станом на поточний момент)</h2>
                <table style="width: 100%; border-collapse: collapse; text-align: left;">
                    <thead>
                        <tr style="background: rgba(255,255,255,0.05);">
                            <th style="padding: 8px; border-bottom: 2px solid var(--border-color);">№ Квартири</th>
                            <th style="padding: 8px; border-bottom: 2px solid var(--border-color);">Owner</th>
                            <th style="padding: 8px; border-bottom: 2px solid var(--border-color);">Debt</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>`;

        previewArea.style.alignItems = 'flex-start';
        previewArea.innerHTML = html;
        if (printBtn) printBtn.style.display = 'block';

        // Set global print area for window.print()
        const oldPrint = document.getElementById('global-print-area');
        if (oldPrint) oldPrint.remove();
        
        const globalPrintArea = document.createElement('div');
        globalPrintArea.id = 'global-print-area';
        globalPrintArea.className = 'print-container';
        globalPrintArea.innerHTML = html;
        document.body.appendChild(globalPrintArea);

    } catch (err) {
        previewArea.innerHTML = `<span class="color-danger">Помилка: ${err.message}</span>`;
    }
}

// Settings
async function renderSettings() {
    pageTitle.innerText = 'Налаштування';
    
    if (state.apartments.length === 0) await fetchApartments();
    const hasChanges = Object.keys(state.pendingChanges || {}).length > 0;
    
    const aptRows = state.apartments
        .filter(a => !a.number.includes('Total'))
        .map(a => {
            return `
            <tr onclick="toggleInlineLogs(${a.id})" id="row-${a.id}" style="cursor:pointer">
                <td style="padding: 0.3rem 0.5rem;">${a.number}</td>
                <td style="padding: 0.3rem 0.5rem;">${a.owner_name || '—'}</td>
                <td style="padding: 0.3rem 0.5rem;">${a.area_m2} м²</td>
                <td style="padding: 0.3rem 0.5rem;" onclick="event.stopPropagation()">
                    <button class="btn btn-secondary btn-sm" onclick="editApartment(${a.id})" title="Edit">✏️</button>
                </td>
            </tr>
            <tr id="logs-row-${a.id}" style="display:none" class="log-detail-row">
                <td colspan="4" id="logs-content-${a.id}" style="padding: 1rem; background: rgba(255,255,255,0.02)">
                    Loading...
                </td>
            </tr>`;
        }).join('');

    const aptFooter = `
        <tr style="font-weight: 700; background: rgba(255,255,255,0.05)">
            <td colspan="2" style="padding: 0.3rem 0.5rem;">Загалом:</td>
            <td style="padding: 0.3rem 0.5rem;">${state.apartments.reduce((s, a) => s + (a.area_m2 || 0), 0).toFixed(2)} м²</td>
            <td style="padding: 0.3rem 0.5rem;"></td>
        </tr>`;

    // Cards mapping
    const cardsHtml = {
        'card-apt': `
            <div class="stat-card draggable-card" id="card-apt" draggable="true" style="display: flex; flex-direction: column; resize: both; overflow: hidden; min-width: 200px; min-height: 250px; cursor: grab; flex-grow: 0; height: 1400px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
                    <h3 style="margin:0;">Словник: Квартири</h3>
                </div>
                <div style="flex-grow: 1; overflow-y: auto;">
                    <table style="width: 100%; font-size: 0.85rem; table-layout: fixed;">
                        <thead>
                            <tr>
                                <th style="padding: 0.3rem 0.5rem; width: 15%;">№</th>
                                <th style="padding: 0.3rem 0.5rem; width: 50%;">Owner</th>
                                <th style="padding: 0.3rem 0.5rem; width: 20%;">Площа</th>
                                <th style="padding: 0.3rem 0.5rem; width: 15%;">Дії</th>
                            </tr>
                        </thead>
                        <tbody>${aptRows}</tbody>
                        <tfoot>${aptFooter}</tfoot>
                    </table>
                </div>
            </div>`,
        'card-cat': `
            <div class="stat-card draggable-card" id="card-cat" draggable="true" style="display: flex; flex-direction: column; resize: both; overflow: hidden; min-width: 200px; min-height: 250px; cursor: grab; flex-grow: 1;">
                <h3>Словник: Категорії</h3>
                <div id="cats-list" style="margin:1rem 0; flex-grow: 1; overflow-y: auto;"></div>
                <button class="btn btn-primary" style="margin-top: auto;" onclick="showAddCategoryModal()">+ Додати категорію</button>
            </div>`,
        'card-tariffs': `
            <div class="stat-card draggable-card" id="card-tariffs" draggable="true" style="display: flex; flex-direction: column; resize: both; overflow: hidden; min-width: 200px; min-height: 150px; cursor: grab; flex-grow: 1;">
                <h3>Тарифи</h3>
                <div id="tariffs-list" style="margin:1rem 0; flex-grow: 1; overflow-y: auto;"></div>
                <button class="btn btn-primary" style="margin-top: auto;" onclick="showAddTariffModal()">+ Додати тариф</button>
            </div>`,
        'card-cont': `
            <div class="stat-card draggable-card" id="card-cont" draggable="true" style="display: flex; flex-direction: column; resize: both; overflow: hidden; min-width: 200px; min-height: 250px; cursor: grab; flex-grow: 1;">
                <h3>Словник: Контрагенти</h3>
                <div id="conts-list" style="margin:1rem 0; flex-grow: 1; overflow-y: auto;"></div>
                <button class="btn btn-primary" style="margin-top: auto;" onclick="showAddContractorModal()">+ Додати контрагента</button>
            </div>`,
        'card-gmail': `
            <div class="stat-card draggable-card" id="card-gmail" draggable="true" style="display: flex; flex-direction: column; border: 2px dashed transparent; transition: all 0.3s ease; resize: both; overflow: hidden; min-width: 200px; min-height: 150px; cursor: grab; flex-grow: 1;">
                <h3>Інтеграція з Gmail</h3>
                <div id="gmail-status" style="margin: 1rem 0 0 0; font-size: 0.95rem;">
                    <div class="loader">Перевірка статусу...</div>
                </div>
                <div style="margin:1rem 0; color: var(--text-secondary); font-size: 0.9rem;">
                    Для автоматичного завантаження реєстрів потрібен <b>credentials.json</b>.
                </div>
                <div class="drop-zone-content" style="flex-grow: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 2rem; border: 1px dashed var(--border-color); border-radius: 8px; background: rgba(255,255,255,0.02); cursor: pointer;" onclick="document.getElementById('gmail-creds-upload').click()">
                    <i class="fas fa-cloud-upload-alt" style="font-size: 2rem; color: var(--text-secondary); margin-bottom: 1rem;"></i>
                    <p style="margin: 0; color: var(--text-secondary); text-align: center;">Перетягніть файл credentials.json сюди або <b>натисніть</b></p>
                    <input type="file" id="gmail-creds-upload" accept=".json" style="display:none" onchange="uploadGmailCreds(event)">
                </div>
            </div>`
    };

    // Load layout
    let layout = {
        'col-1': ['card-apt'],
        'col-2': ['card-cat', 'card-tariffs'],
        'col-3': ['card-cont', 'card-gmail']
    };
    try {
        const saved = localStorage.getItem('settings_layout');
        if (saved) {
            const parsed = JSON.parse(saved);
            // Verify it has all cards
            const allSavedCards = [...(parsed['col-1']||[]), ...(parsed['col-2']||[]), ...(parsed['col-3']||[])];
            const allExpectedCards = Object.keys(cardsHtml);
            if (allExpectedCards.every(c => allSavedCards.includes(c))) {
                layout = parsed;
            }
        }
    } catch(e) {}

    contentArea.innerHTML = `
        <div id="settings-grid" style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1.5rem; align-items: stretch;">
            <div id="col-1" class="layout-column" style="display: flex; flex-direction: column; gap: 1.5rem; height: 100%;">
                ${(layout['col-1']||[]).map(id => cardsHtml[id]).join('')}
            </div>
            <div id="col-2" class="layout-column" style="display: flex; flex-direction: column; gap: 1.5rem; height: 100%;">
                ${(layout['col-2']||[]).map(id => cardsHtml[id]).join('')}
            </div>
            <div id="col-3" class="layout-column" style="display: flex; flex-direction: column; gap: 1.5rem; height: 100%;">
                ${(layout['col-3']||[]).map(id => cardsHtml[id]).join('')}
            </div>
        </div>`;
    loadTariffs();
    loadCategoriesSettings();
    loadContractorsSettings();
    loadGmailStatus();
    
    // Setup Drag-and-Drop for cards (reordering)
    setTimeout(() => {
        const grid = document.getElementById('settings-grid');
        const cards = grid.querySelectorAll('.draggable-card');
        
        cards.forEach(card => {
            card.addEventListener('dragstart', (e) => {
                card.classList.add('dragging');
                e.dataTransfer.effectAllowed = 'move';
            });
            card.addEventListener('dragend', () => {
                card.classList.remove('dragging');
                card.style.opacity = '1';
                cards.forEach(c => c.style.border = '');
                
                // Save layout
                const cols = document.querySelectorAll('.layout-column');
                let newLayout = {};
                cols.forEach(col => {
                    newLayout[col.id] = [...col.querySelectorAll('.draggable-card')].map(c => c.id);
                });
                localStorage.setItem('settings_layout', JSON.stringify(newLayout));
            });
            card.addEventListener('mousedown', () => card.style.cursor = 'grabbing');
            card.addEventListener('mouseup', () => card.style.cursor = 'grab');
        });

        const columns = grid.querySelectorAll('.layout-column');
        columns.forEach(col => {
            col.addEventListener('dragover', (e) => {
                e.preventDefault();
                const draggingCard = grid.querySelector('.dragging');
                if (!draggingCard) return;

                const afterElement = getDragAfterElement(col, e.clientY);
                if (afterElement == null) {
                    col.appendChild(draggingCard);
                } else {
                    col.insertBefore(draggingCard, afterElement);
                }
            });
        });

        function getDragAfterElement(container, y) {
            const draggableElements = [...container.querySelectorAll('.draggable-card:not(.dragging)')];
            return draggableElements.reduce((closest, child) => {
                const box = child.getBoundingClientRect();
                const offset = y - box.top - box.height / 2;
                if (offset < 0 && offset > closest.offset) {
                    return { offset: offset, element: child };
                } else {
                    return closest;
                }
            }, { offset: Number.NEGATIVE_INFINITY }).element;
        }

        // Setup Drag-and-Drop for Gmail file
            const dropZone = document.getElementById('card-gmail'); // using card-gmail as dropzone
            if (dropZone) {
                ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                    dropZone.addEventListener(eventName, preventDefaults, false);
                });
                function preventDefaults(e) {
                    if (e.dataTransfer && e.dataTransfer.types && e.dataTransfer.types.includes('Files')) {
                        e.preventDefault();
                        e.stopPropagation();
                    }
                }
            }
            
            // Layout persistence logic for Settings
            const gridEl = document.getElementById('settings-grid');
            if (gridEl) {
                const cardsElements = gridEl.querySelectorAll('.draggable-card');
                
                // Load saved sizes
                cardsElements.forEach((card, index) => {
                    if (!card.id) card.id = 'settings-card-' + index;
                    const savedSize = localStorage.getItem(card.id + '_size');
                    if (savedSize) {
                        const { w, h } = JSON.parse(savedSize);
                        if (w) card.style.width = w;
                        if (h) card.style.height = h;
                    }
                });

                // Observe resizes
                if (window.ResizeObserver) {
                    const ro = new ResizeObserver(entries => {
                        for (let entry of entries) {
                            const t = entry.target;
                            if (t.id) {
                                localStorage.setItem(t.id + '_size', JSON.stringify({
                                    w: t.style.width,
                                    h: t.style.height
                                }));
                            }
                        }
                    });
                    cardsElements.forEach(c => ro.observe(c));
                }
            }

            if (dropZone) {
                ['dragenter', 'dragover'].forEach(eventName => {
                dropZone.addEventListener(eventName, (e) => {
                    if (e.dataTransfer.types.includes('Files')) {
                        dropZone.style.borderColor = 'var(--primary-color)';
                        dropZone.style.background = 'rgba(var(--primary-rgb), 0.05)';
                    }
                }, false);
            });
            ['dragleave', 'drop'].forEach(eventName => {
                dropZone.addEventListener(eventName, (e) => {
                    if (e.dataTransfer.types.includes('Files')) {
                        dropZone.style.borderColor = 'transparent';
                        dropZone.style.background = 'transparent';
                    }
                }, false);
            });
            dropZone.addEventListener('drop', (e) => {
                if (e.dataTransfer.types.includes('Files')) {
                    const dt = e.dataTransfer;
                    const files = dt.files;
                    if (files && files.length > 0) {
                        handleGmailDrop(files[0]);
                    }
                }
            }, false);
        }
    }, 100);
}

window.handleGmailDrop = async function(file) {
    if (file.name !== 'credentials.json' && !file.name.endsWith('.json')) {
        alert('Будь ласка, завантажте JSON файл');
        return;
    }
    const formData = new FormData();
    formData.append('file', file);
    try {
        const res = await fetch(`${API_BASE}/bank/gmail-credentials`, {
            method: 'POST',
            body: formData
        });
        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || 'Невідома помилка');
        }
        alert('Файл credentials.json успішно збережено на сервері!');
        await loadGmailStatus();
    } catch (err) {
        alert('Помилка при завантаженні: ' + err.message);
    }
};

async function loadGmailStatus() {
    try {
        const res = await fetch(`${API_BASE}/bank/gmail-status`);
        const status = await res.json();
        
        const credsIcon = status.credentials_exist 
            ? '<i class="fas fa-check-circle" style="color: var(--success)"></i> Завантажено' 
            : '<i class="fas fa-times-circle" style="color: var(--danger)"></i> Немає';
            
        const tokenIcon = status.token_exists
            ? '<i class="fas fa-check-circle" style="color: var(--success)"></i> Авторизовано' 
            : '<i class="fas fa-times-circle" style="color: var(--warning)"></i> Очікує авторизації';
            
        document.getElementById('gmail-status').innerHTML = `
            <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem; padding-bottom:0.5rem; border-bottom:1px solid rgba(255,255,255,0.1)">
                <span>Ключ (credentials.json):</span>
                <b>${credsIcon}</b>
            </div>
            <div style="display:flex; justify-content:space-between;">
                <span>Токен (token.json):</span>
                <b>${tokenIcon}</b>
            </div>
        `;
    } catch (e) {
        document.getElementById('gmail-status').innerHTML = '<span class="color-danger">Помилка завантаження статусу</span>';
    }
}

window.uploadGmailCreds = async function(event) {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch(`${API_BASE}/bank/gmail-credentials`, {
            method: 'POST',
            body: formData
        });

        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || 'Невідома помилка');
        }

        alert('Файл credentials.json успішно збережено на сервері!');
        await loadGmailStatus();
    } catch (err) {
        alert('Помилка при завантаженні: ' + err.message);
    } finally {
        event.target.value = ''; // Reset
    }
};

async function loadCategoriesSettings() {
    const el = document.getElementById('cats-list');
    if (!el) return;
    try {
        if (state.categories.length === 0) await fetchCategories();
        const cats = [...state.categories].sort((a, b) => {
            if (a.type !== b.type) return a.type.localeCompare(b.type);
            const grpA = a.group || a.name;
            const grpB = b.group || b.name;
            if (grpA !== grpB) return grpA.localeCompare(grpB, 'uk');
            return (a.name || '').localeCompare(b.name || '', 'uk');
        });

        if (!cats.length) {
            el.innerHTML = '<p style="color:var(--text-secondary)">Немає категорій</p>';
            return;
        }

        // Build two-level tree: Type → Group → [categories]
        const tree = {};
        cats.forEach(c => {
            const tLabel = c.type === 'income' ? 'Inflows' : 'Expenses';
            const grp = c.group || c.name;
            if (!tree[tLabel]) tree[tLabel] = {};
            if (!tree[tLabel][grp]) tree[tLabel][grp] = [];
            tree[tLabel][grp].push(c);
        });

        let html = '';
        for (const [tLabel, groups] of Object.entries(tree)) {
            const typeColor = tLabel === 'Inflows' ? 'var(--success)' : 'var(--danger)';
            html += `<div style="margin-bottom:0.5rem">
                <div style="font-weight:700; font-size:0.8rem; color:${typeColor}; padding:0.3rem 0.5rem; text-transform:uppercase; letter-spacing:0.05em; border-bottom:1px solid rgba(255,255,255,0.08)">
                    ${tLabel === 'Inflows' ? '↓' : '↑'} ${tLabel}
                </div>`;
            for (const [grp, items] of Object.entries(groups)) {
                html += `<div style="padding-left:0.5rem; border-left:2px solid rgba(255,255,255,0.1); margin:0.25rem 0 0.25rem 0.5rem">
                    <div style="font-weight:600; font-size:0.85rem; color:var(--text-secondary); padding:0.2rem 0">${grp}</div>`;
                items.forEach(c => {
                    html += `<div style="display:flex;justify-content:space-between;padding:0.3rem 0.5rem;align-items:center;font-size:0.9rem">
                        <span>${c.name}</span>
                        <div style="display:flex;gap:0.3rem">
                            <button class="btn btn-secondary btn-sm" onclick="editCategory(${c.id})" title="Edit">✏️</button>
                            <button class="btn btn-secondary btn-sm" onclick="deleteCategory(${c.id})" title="Видалити">🗑️</button>
                        </div>
                    </div>`;
                });
                html += `</div>`;
            }
            html += `</div>`;
        }
        el.innerHTML = html;
    } catch (e) { console.error(e); }
}

window.showAddCategoryModal = function() {
    modalTitle.innerText = 'Додати категорію';

    // Collect existing groups for datalist suggestions
    const existingGroups = [...new Set(state.categories.map(c => c.group).filter(Boolean))];
    const groupOptions = existingGroups.map(g => `<option value="${g}">`).join('');

    modalBody.innerHTML = `
        <div class="form-group">
            <label>Type операції</label>
            <select id="cat-type" class="form-control" style="width:100%;margin-bottom:1rem">
                <option value="income">Inflows</option>
                <option value="expense">Витрата</option>
            </select>
            <label>Group призначення</label>
            <input type="text" id="cat-group" class="form-control" list="cat-group-list" style="width:100%;margin-bottom:1rem" placeholder="Наприклад: Ліфт, Прибирання, Квартплата">
            <datalist id="cat-group-list">${groupOptions}</datalist>
            <label>Назва (Purpose)</label>
            <input type="text" id="cat-name" class="form-control" style="width:100%;margin-bottom:1rem" placeholder="Наприклад: Квартплата (банк)">
        </div>`;
    modal.style.display = 'flex';

    const submitBtn = document.getElementById('modal-submit');
    if (submitBtn) {
        submitBtn.onclick = async () => {
            const name = document.getElementById('cat-name').value.trim();
            const group = document.getElementById('cat-group').value.trim();
            if (!name) return alert('Введіть назву');
            if (!group) return alert('Введіть групу призначення');
            const type = document.getElementById('cat-type').value;

            await fetch(`${API_BASE}/categories/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, type, group })
            });
            await fetchCategories();
            closeModal();
            loadCategoriesSettings();
        };
    }
};

window.editCategory = function(id) {
    const cat = state.categories.find(c => c.id === id);
    if (!cat) return;

    modalTitle.innerText = 'Edit категорію';

    const existingGroups = [...new Set(state.categories.map(c => c.group).filter(Boolean))];
    const groupOptions = existingGroups.map(g => `<option value="${g}">`).join('');

    modalBody.innerHTML = `
        <div class="form-group">
            <label>Type операції</label>
            <select id="cat-type" class="form-control" style="width:100%;margin-bottom:1rem">
                <option value="income" ${cat.type === 'income' ? 'selected' : ''}>Inflows</option>
                <option value="expense" ${cat.type === 'expense' ? 'selected' : ''}>Витрата</option>
            </select>
            <label>Group призначення</label>
            <input type="text" id="cat-group" class="form-control" list="cat-group-list" style="width:100%;margin-bottom:1rem" value="${cat.group || ''}">
            <datalist id="cat-group-list">${groupOptions}</datalist>
            <label>Назва (Purpose)</label>
            <input type="text" id="cat-name" class="form-control" style="width:100%;margin-bottom:1rem" value="${cat.name || ''}">
        </div>`;
    modal.style.display = 'flex';

    const submitBtn = document.getElementById('modal-submit');
    if (submitBtn) {
        submitBtn.onclick = async () => {
            const name = document.getElementById('cat-name').value.trim();
            const group = document.getElementById('cat-group').value.trim();
            if (!name) return alert('Введіть назву');
            if (!group) return alert('Введіть групу призначення');
            const type = document.getElementById('cat-type').value;

            const res = await fetch(`${API_BASE}/categories/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, type, group })
            });
            if (!res.ok) {
                const err = await res.json();
                return alert(err.detail || 'Помилка');
            }
            await fetchCategories();
            closeModal();
            loadCategoriesSettings();
        };
    }
};

window.deleteCategory = async function(id) {
    // if (!confirm('Ви впевнені, що хочете видалити цю категорію?')) return;
    try {
        const res = await fetch(`${API_BASE}/categories/${id}`, { method: 'DELETE' });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Помилка');
        }
        await fetchCategories();
        loadCategoriesSettings();
    } catch (e) {
        alert(e.message);
    }
};

async function loadContractorsSettings() {
    const el = document.getElementById('conts-list');
    if (!el) return;
    try {
        if (state.contractors.length === 0) await fetchContractors();
        if (!state.contractors.length) {
            el.innerHTML = '<p style="color:var(--text-secondary)">Немає контрагентів</p>';
            return;
        }
        // Group by category (income / expense)
        const grouped = { income: [], expense: [], other: [] };
        state.contractors.forEach(c => {
            const catType = c.default_category ? c.default_category.type : 'other';
            if (catType === 'income') grouped.income.push(c);
            else if (catType === 'expense') grouped.expense.push(c);
            else grouped.other.push(c);
        });

        let html = '';
        const sections = [
            { key: 'income', label: 'Inflows', color: 'var(--success)', icon: '↓' },
            { key: 'expense', label: 'Expenses', color: 'var(--danger)', icon: '↑' },
            { key: 'other', label: 'Без категорії', color: 'var(--text-secondary)', icon: '•' }
        ];
        for (const sec of sections) {
            if (!grouped[sec.key].length) continue;
            html += `<div style="margin-bottom:0.5rem">
                <div style="font-weight:700; font-size:0.8rem; color:${sec.color}; padding:0.3rem 0.5rem; text-transform:uppercase; letter-spacing:0.05em; border-bottom:1px solid rgba(255,255,255,0.08)">
                    ${sec.icon} ${sec.label}
                </div>`;
            grouped[sec.key].forEach(c => {
                const catDisplay = c.default_category ? (c.default_category.group ? `${c.default_category.group} / ${c.default_category.name}` : c.default_category.name) : '—';
                html += `<div style="display:flex;justify-content:space-between;padding:0.4rem 0.5rem;border-bottom:1px solid var(--border-color);align-items:center">
                    <div>
                        <span style="font-size:0.8rem; color:var(--text-secondary)">
                            ${catDisplay}
                        </span>
                        <br>${c.name}
                    </div>
                    <div style="display:flex;gap:0.3rem">
                        <button class="btn btn-secondary btn-sm" onclick="editContractor(${c.id})" title="Edit">✏️</button>
                        <button class="btn btn-secondary btn-sm" onclick="deleteContractor(${c.id})" title="Видалити">🗑️</button>
                    </div>
                </div>`;
            });
            html += `</div>`;
        }
        el.innerHTML = html;
    } catch (e) { console.error(e); }
}

window.showAddContractorModal = function() {
    modalTitle.innerText = 'Додати контрагента';
    const catOptions = state.categories.map(c => `<option value="${c.id}">${c.name} (${c.group || c.type})</option>`).join('');
    modalBody.innerHTML = `
        <div class="form-group">
            <label>Назва (Purpose)</label>
            <select id="cont-category-id" class="form-control" style="width:100%;margin-bottom:1rem">
                <option value="">Без категорії</option>
                ${catOptions}
            </select>
            <label>Назва контрагента</label>
            <input type="text" id="cont-name" class="form-control" style="width:100%;margin-bottom:1rem">
        </div>`;
    modal.style.display = 'flex';

    const submitBtn = document.getElementById('modal-submit');
    if (submitBtn) {
        submitBtn.onclick = async () => {
            const name = document.getElementById('cont-name').value.trim();
            if (!name) return alert('Введіть назву');
            const catId = document.getElementById('cont-category-id').value;

            const res = await fetch(`${API_BASE}/contractors/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, default_category_id: catId ? parseInt(catId) : null, active: true })
            });
            if (!res.ok) {
                const err = await res.json();
                return alert(err.detail || 'Помилка');
            }
            await fetchContractors();
            closeModal();
            loadContractorsSettings();
        };
    }
};

window.editContractor = function(id) {
    const cont = state.contractors.find(c => c.id === id);
    if (!cont) return;

    modalTitle.innerText = 'Edit контрагента';
    const catOptions = state.categories.map(c => `<option value="${c.id}" ${cont.default_category_id === c.id ? 'selected' : ''}>${c.name} (${c.group || c.type})</option>`).join('');
    modalBody.innerHTML = `
        <div class="form-group">
            <label>Назва (Purpose)</label>
            <select id="cont-category-id" class="form-control" style="width:100%;margin-bottom:1rem">
                <option value="">Без категорії</option>
                ${catOptions}
            </select>
            <label>Назва контрагента</label>
            <input type="text" id="cont-name" class="form-control" style="width:100%;margin-bottom:1rem" value="${cont.name}">
        </div>`;
    modal.style.display = 'flex';

    const submitBtn = document.getElementById('modal-submit');
    if (submitBtn) {
        submitBtn.onclick = async () => {
            const name = document.getElementById('cont-name').value.trim();
            if (!name) return alert('Введіть назву');
            const catId = document.getElementById('cont-category-id').value;

            const res = await fetch(`${API_BASE}/contractors/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, default_category_id: catId ? parseInt(catId) : null, active: cont.active })
            });
            if (!res.ok) {
                const err = await res.json();
                return alert(err.detail || 'Помилка');
            }
            await fetchContractors();
            closeModal();
            loadContractorsSettings();
        };
    }
};

window.deleteContractor = async function(id) {
    // if (!confirm('Ви впевнені, що хочете видалити цього контрагента?')) return;
    try {
        const res = await fetch(`${API_BASE}/contractors/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Помилка видалення');
        await fetchContractors();
        loadContractorsSettings();
    } catch (e) {
        alert(e.message);
    }
};

async function loadTariffs() {
    const el = document.getElementById('tariffs-list');
    if (!el) return;
    try {
        const res = await fetch(`${API_BASE}/tariffs/`);
        const tariffs = await res.json();
        el.innerHTML = tariffs.length
            ? tariffs.map(t => `
                <div style="display:flex;justify-content:space-between;padding:.5rem;border-bottom:1px solid var(--border-color)">
                    <span>${t.name}</span>
                    <span style="font-weight:600">${t.value} ₴ / ${t.unit}</span>
                </div>`).join('')
            : '<p style="color:var(--text-secondary)">Тарифи ще не задані</p>';
    } catch (e) { console.error(e); }
}

function showAddTariffModal() {
    modalTitle.innerText = 'Додати тариф';
    modalBody.innerHTML = `
        <div class="form-group">
            <label>Назва</label>
            <select id="t-name" class="form-control" style="width:100%;margin-bottom:1rem">
                <option value="Maintenance">Утримання будинку (Maintenance)</option>
                <option value="Lift">Ліфт (Lift)</option>
                <option value="Gas">Газ (Gas)</option>
            </select>
            <label>Amount (₴)</label>
            <input type="number" step="0.01" id="t-value" class="form-control" style="width:100%;margin-bottom:1rem" placeholder="Наприклад: 5.50">
            <label>Одиниця нарахування</label>
            <select id="t-unit" class="form-control" style="width:100%">
                <option value="m2">за м²</option>
                <option value="person">за мешканця</option>
                <option value="flat">за квартиру</option>
            </select>
        </div>`;
    modal.style.display = 'flex';

    const submitBtn = document.getElementById('modal-submit');
    if (submitBtn) {
        submitBtn.onclick = async () => {
            const val = parseFloat(document.getElementById('t-value').value);
            if (isNaN(val)) return alert('Введіть коректну суму');

            await fetch(`${API_BASE}/tariffs/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: document.getElementById('t-name').value,
                    value: val,
                    unit: document.getElementById('t-unit').value,
                    is_active: true
                })
            });
            state.needsRecalculation = true;
            updateGlobalUI();
            closeModal();
            renderSettings();
        };
    }
}

// Apartment edit / action modal
async function editApartment(id) {
    const apt = state.apartments.find(a => a.id === id);
    if (!apt) return;

    modalTitle.innerText = `Дія: Apartment № ${apt.number}`;
    const liftStatusText = apt.has_lift_exemption ? '<span class="color-danger">Без ліфта</span>' : '<span class="color-success">З ліфтом</span>';
    modalBody.innerHTML = `
        <div style="margin-bottom: 1rem">
            <p><b>Owner:</b> ${apt.owner_name || '—'}</p>
            <p><b>Площа:</b> ${apt.area_m2} м²</p>
            <p style="display:flex; justify-content:space-between; align-items:center;">
                <span><b>Ліфт:</b> ${liftStatusText}</span>
                <button type="button" class="btn btn-secondary btn-sm" onclick="toggleLiftStatus(${apt.id})">
                    ${apt.has_lift_exemption ? 'Включити' : 'Виключити'}
                </button>
            </p>
        </div>
        <div class="form-group">
            <label>Період застосування (місяць)</label>
            <input type="month" id="action-period" class="form-control" style="width:100%; margin-bottom: 1rem" value="${state.startDate.substring(0, 7)}" onclick="this.showPicker()">

            <label>Type дії</label>
            <select id="action-type" class="form-control" style="width:100%; margin-bottom: 1rem">
                <option value="adjustment">Корегування (Фінансове)</option>
                <option value="owner_change">Зміна власника</option>
                <option value="area_change">Зміна площі</option>
            </select>

            <div id="fields-adjustment">
                <label>Amount (+ або −)</label>
                <input type="number" step="0.01" id="adj-amount" class="form-control" style="width:100%;margin-bottom:1rem" placeholder="0.00">
                <label>Причина</label>
                <input type="text" id="adj-desc" class="form-control" style="width:100%">
            </div>

            <div id="fields-owner_change" style="display:none">
                <label>Нове ім'я власника</label>
                <input type="text" id="new-owner" class="form-control" style="width:100%" placeholder="П.І.Б.">
            </div>

            <div id="fields-area_change" style="display:none">
                <label>Нова площа (м²)</label>
                <input type="number" step="0.01" id="new-area" class="form-control" style="width:100%" value="${apt.area_m2}">
            </div>
        </div>`;

    const typeSelect = document.getElementById('action-type');
    typeSelect.onchange = () => {
        ['adjustment', 'owner_change', 'area_change'].forEach(t => {
            document.getElementById(`fields-${t}`).style.display = (t === typeSelect.value) ? 'block' : 'none';
        });
    };

    modal.style.display = 'flex';

    const submitBtn = document.getElementById('modal-submit');
    if (submitBtn) {
        submitBtn.onclick = async () => {
            const type = typeSelect.value;
            const period = document.getElementById('action-period').value;
            let payload = { apartment_id: id, type, period };

            if (type === 'adjustment') {
                const amount = parseFloat(document.getElementById('adj-amount').value);
                if (isNaN(amount)) return alert('Введіть суму');
                payload.amount = amount;
                payload.description = document.getElementById('adj-desc').value;
            } else if (type === 'owner_change') {
                const val = document.getElementById('new-owner').value.trim();
                if (!val) return alert('Введіть ім\'я');
                payload.new_value = val;
            } else if (type === 'area_change') {
                const val = document.getElementById('new-area').value;
                if (!val) return alert('Введіть площу');
                payload.new_value = val;
            }

            try {
                const res = await fetch(`${API_BASE}/apartments/${id}/logs`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (!res.ok) throw new Error('Помилка сервера');

                closeModal();
                state.needsRecalculation = true;
                updateGlobalUI();
                await fetchApartments();
                await renderSettings();
            } catch (err) {
                alert('Помилка: ' + err.message);
            }
        };
    }
}

window.toggleLiftStatus = async function(id) {
    try {
        const res = await fetch(`${API_BASE}/apartments/${id}/toggle-lift`, { method: 'POST' });
        if (!res.ok) throw new Error('Помилка зміни статусу');
        state.needsRecalculation = true;
        updateGlobalUI();
        await fetchApartments();
        await renderSettings();
        editApartment(id); // Reload modal
    } catch (err) {
        alert('Помилка: ' + err.message);
    }
};












window.toggleCard = function(icon) {
    const parentH3 = icon.closest('h3');
    if (!parentH3) return;
    const content = parentH3.nextElementSibling;
    const card = icon.closest('.dash-card') || icon.closest('.draggable-card') || icon.closest('.stat-card');
    
    if(content.style.display === 'none') {
        content.style.display = '';
        icon.style.transform = 'rotate(0deg)';
        if (card) {
            if (card.dataset.savedMinHeight) card.style.minHeight = card.dataset.savedMinHeight;
            if (card.dataset.savedHeight) card.style.height = card.dataset.savedHeight;
        }
    } else {
        content.style.display = 'none';
        icon.style.transform = 'rotate(180deg)';
        if (card) {
            card.dataset.savedMinHeight = card.style.minHeight;
            card.dataset.savedHeight = card.style.height;
            card.style.minHeight = 'auto';
            card.style.height = 'auto';
        }
    }
};

window.toggleDetailsTable = function(event) {
    if (event) event.stopPropagation(); // prevent toggling the parent card
    const cont = document.getElementById('details-table-container');
    const btn = document.getElementById('toggle-details-btn');
    if(cont.style.display === 'none') {
        cont.style.display = 'block';
        btn.innerHTML = '<i class="fas fa-minus"></i> Сховати деталі';
    } else {
        cont.style.display = 'none';
        btn.innerHTML = '<i class="fas fa-plus"></i> Details';
    }
};

window.toggleTheme = function() {
    document.body.classList.toggle('light-theme');
    const isLight = document.body.classList.contains('light-theme');
    const icon = document.querySelector('#theme-toggle i');
    if (icon) {
        if (isLight) {
            icon.classList.remove('fa-sun');
            icon.classList.add('fa-moon');
        } else {
            icon.classList.remove('fa-moon');
            icon.classList.add('fa-sun');
        }
    }
    
    // Update charts if they exist
    const charts = [Chart.getChart("mainChart"), Chart.getChart("debtChart"), Chart.getChart("expensePieChart"), Chart.getChart("scenariosLineChart")];
    charts.forEach(chart => {
        if (chart) {
            const textColor = isLight ? '#475569' : '#94a3b8';
            const gridColor = isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.07)';
            
            if (chart.options.plugins && chart.options.plugins.legend && chart.options.plugins.legend.labels) {
                chart.options.plugins.legend.labels.color = textColor;
            }
            if (chart.options.scales && chart.options.scales.x) {
                chart.options.scales.x.ticks.color = textColor;
                if (chart.options.scales.x.grid) chart.options.scales.x.grid.color = gridColor;
            }
            if (chart.options.scales && chart.options.scales.y) {
                chart.options.scales.y.ticks.color = textColor;
                if (chart.options.scales.y.grid) chart.options.scales.y.grid.color = gridColor;
            }
            chart.update();
        }
    });
}

// ── Forecast Page ─────────────────────────────────────────────────────────────

window.toggleSectionCollapse = function(sectionId, btn) {
    const section = document.getElementById(sectionId);
    if (!section) return;
    section.classList.toggle('collapsed');
    if (btn) btn.classList.toggle('is-collapsed');
}


window.switchDetailScenario = function(index) {
    window.currentDetailScenarioIndex = index;
    
    for (let i = 1; i <= 3; i++) {
        const btn = document.getElementById(`tab-btn-${i}`);
        if (btn) {
            if (i === index) {
                btn.style.background = 'var(--accent-color)';
                btn.style.color = 'white';
            } else {
                btn.style.background = 'transparent';
                btn.style.color = 'var(--text-secondary)';
            }
        }
    }
    
    const params = window.scenarioParams[index];
    if (params) {
        const balDisp = document.getElementById('scenario-balance-display');
        if (balDisp) {
            balDisp.innerText = formatCurrency(params.balance) + ' ₴';
        }
        document.getElementById('scenario-tariff').value = params.tariff.toFixed(1);
        document.getElementById('scenario-collection').value = params.collection;
    }
    
    window.renderDetailScenarioResults(index);
}

window.updateCurrentScenarioParams = async function() {
    const index = window.currentDetailScenarioIndex;
    if (!index) return;
    
    const tariff = parseFloat(document.getElementById('scenario-tariff').value) || 0;
    const collection = parseFloat(document.getElementById('scenario-collection').value) || 0;
    
    const existingBalance = (window.scenarioParams[index] && window.scenarioParams[index].balance) || 0;
    const existingDebt = (window.scenarioParams[index] && window.scenarioParams[index].debt) || 0;
    
    window.scenarioParams[index] = { balance: existingBalance, debt: existingDebt, tariff, collection };
    
    const resultsContainer = document.getElementById('scenario-detail-results');
    if (resultsContainer) {
        resultsContainer.innerHTML = '<div class="loader" style="margin: 2rem auto;">Loading...</div>';
    }
    
    await window.generateForecastScenario(index);
}

window.renderDetailScenarioResults = function(index) {
    const resultsContainer = document.getElementById('scenario-detail-results');
    if (!resultsContainer) return;
    
    const sData = window.scenariosData[index];
    if (!sData) {
        resultsContainer.innerHTML = '<div class="loader" style="margin: 2rem auto;">Loading...</div>';
        return;
    }
    
    const data = sData.data;
    const params = window.scenarioParams[index];
    
    const forRows = data.map(f => `
        <tr>
            <td style="font-weight:600">${['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][parseInt(f.month.split('-')[1])-1]}-${f.month.split('-')[0].substring(2)}</td>
            <td class="color-success">+${formatCurrency(f.income_total)} ₴</td>
            <td class="color-danger">-${formatCurrency(f.expense_total)} ₴</td>
            <td class="color-danger">${f.expense_activities > 0 ? "-" + formatCurrency(f.expense_activities) + " ₴" : "0.00 ₴"}</td>
            <td class="${f.net >= 0 ? 'color-success' : 'color-danger'}">${formatCurrency(f.net)} ₴</td>
            <td style="font-weight:600" class="${f.cumulative >= 0 ? 'color-success' : 'color-danger'}">${formatCurrency(f.cumulative)} ₴</td>
        </tr>
    `).join("");

    resultsContainer.innerHTML = `
        <div style="overflow-x:auto; margin-bottom: 2rem;">
            <table>
                <thead><tr><th>Month</th><th>Дохід (план)</th><th>Expenses (план)</th><th>Активності</th><th>Net Cash Flow</th><th>Balance (Накопич.)</th></tr></thead>
                <tbody>${forRows || "<tr><td colspan='6' class='text-center'>Немає прогнозу</td></tr>"}</tbody>
            </table>
        </div>
        
        <h4 style="margin-bottom: 1rem;">Зведені показники</h4>
        <div class="stats-grid" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); width: 100%; gap:1rem; margin-bottom: 0;">
            <div class="stat-card" style="padding: 1.5rem;">
                <h3 style="font-size:0.85rem">План. Inflows</h3>
                <div class="value color-success" style="font-size: 1.5rem;">+${formatCurrency(sData.planIncome)} ₴</div>
            </div>
            <div class="stat-card" style="padding: 1.5rem;">
                <h3 style="font-size:0.85rem">План. Expenses</h3>
                <div class="value color-danger" style="font-size: 1.5rem;">-${formatCurrency(sData.planExpenses)} ₴</div>
            </div>
            <div class="stat-card" style="padding: 1.5rem;">
                <h3 style="font-size:0.85rem">Очікуваний баланс</h3>
                <div class="value ${sData.finalBalance >= 0 ? 'color-success' : 'color-danger'}" style="font-size: 1.5rem;">${formatCurrency(sData.finalBalance)} ₴</div>
            </div>
        </div>
    `;
}

window.updateScenarioTariff = async function(index, newTariff) {
    let val = parseFloat(newTariff);
    if (isNaN(val)) val = index === 1 ? 4.4 : (index === 2 ? 8.0 : 12.0);
    
    if (window.scenarioParams && window.scenarioParams[index]) {
        window.scenarioParams[index].tariff = val;
    }
    
    if (window.currentDetailScenarioIndex === index) {
        const tInput = document.getElementById('scenario-tariff');
        if (tInput) tInput.value = val.toFixed(1);
    }
    
    await window.generateForecastScenario(index);
}

window.updateActivityMonth = async function(actId, newMonth) {
    if (!newMonth) return;
    try {
        const res = await fetch(`${API_BASE}/forecast/activities/${actId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ planned_month: newMonth })
        });
        if (res.ok) {
            await Promise.all([
                window.generateForecastScenario(1),
                window.generateForecastScenario(2),
                window.generateForecastScenario(3)
            ]);
        }
    } catch(e) {
        console.error(e);
    }
}

window.updateActivityAmount = async function(actId, newAmount) {
    const amt = parseFloat(newAmount);
    if (isNaN(amt)) return;
    try {
        const res = await fetch(`${API_BASE}/forecast/activities/${actId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ planned_amount: amt })
        });
        if (res.ok) {
            await Promise.all([
                window.generateForecastScenario(1),
                window.generateForecastScenario(2),
                window.generateForecastScenario(3)
            ]);
        }
    } catch(e) {
        console.error(e);
    }
}

window.deleteActivityGlobal = async function(actId) {
    try {
        const res = await fetch(`${API_BASE}/forecast/activities/${actId}`, {
            method: "DELETE"
        });
        if (res.ok) {
            await Promise.all([
                window.generateForecastScenario(1),
                window.generateForecastScenario(2),
                window.generateForecastScenario(3)
            ]);
        }
    } catch(e) {
        console.error(e);
    }
}

window.generateForecastScenario = async function(index) {
    const params = window.scenarioParams[index];
    if (!params) return;
    
    const startMonth = window.globalForecastStartMonth;
    const endMonth = window.globalForecastEndMonth;
    
    try {
        const res = await fetch(`${API_BASE}/forecast/custom`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                start_month: startMonth,
                end_month: endMonth,
                starting_balance: params.balance,
                starting_debt: 0.0,
                resident_tariff: params.tariff,
                collection_rate: params.collection / 100.0
            })
        });
        
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        
        const excludedIds = window.scenarioExcludedActivities[index] || new Set();
        if (excludedIds.size > 0) {
            const actsRes = await fetch(`${API_BASE}/forecast/activities`);
            if (actsRes.ok) {
                const allActs = await actsRes.json();
                const excludedActs = allActs.filter(a => excludedIds.has(a.id));
                for (const ea of excludedActs) {
                    let found = false;
                    for (let i = 0; i < data.length; i++) {
                        if (data[i].month === ea.planned_month) found = true;
                        if (found) {
                            if (data[i].month === ea.planned_month) {
                                data[i].expense_activities -= ea.planned_amount;
                                data[i].expense_total -= ea.planned_amount;
                                data[i].net += ea.planned_amount;
                            }
                            data[i].cumulative += ea.planned_amount;
                        }
                    }
                }
            }
        }
        
        let planIncome = 0;
        let planExpenses = 0;
        data.forEach(f => {
            planIncome += f.income_total;
            planExpenses += f.expense_total;
        });

        const finalBalance = data.length > 0 ? data[data.length - 1].cumulative : params.balance;
        
        if (!window.scenariosData) window.scenariosData = {};
        window.scenariosData[index] = {
            data: data,
            planIncome,
            planExpenses,
            finalBalance
        };
        
        await window.updateScenariosCharts();
        
        if (window.currentDetailScenarioIndex === index) {
            window.renderDetailScenarioResults(index);
        }
    } catch (err) {
        console.error(err);
        if (window.currentDetailScenarioIndex === index) {
            const resultsContainer = document.getElementById('scenario-detail-results');
            if (resultsContainer) {
                resultsContainer.innerHTML = `<p class="color-danger">Помилка: ${err.message}</p>`;
            }
        }
    }
}

window.updateScenariosCharts = async function() {
    if (!window.scenariosData || Object.keys(window.scenariosData).length === 0) return;
    
    const indices = [1, 2, 3];
    const loaded = indices.filter(i => window.scenariosData[i]);
    if (loaded.length === 0) return;
    
    const monthNamesUa = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const firstData = window.scenariosData[loaded[0]].data;
    const forecastLabels = firstData.map(f => `${monthNamesUa[parseInt(f.month.split('-')[1])-1]}-${f.month.split('-')[0].substring(2)}`);
    
    // Build combined labels: actuals + forecast
    const actuals = window.dashboardActuals || { labels: [], balance: [], inflow: [], expenses: [] };
    const allLabels = [...actuals.labels, ...forecastLabels];
    const actualCount = actuals.labels.length;
    
    // Actual balance dataset (solid line for past)
    const actualBalanceData = [...actuals.balance, ...new Array(forecastLabels.length).fill(null)];
    
    const isLight = document.body.classList.contains('light-theme');
    const textColor = isLight ? '#475569' : '#94a3b8';
    const gridColor = isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.07)';
    
    const datasets = [];
    
    // Add actual balance line if there are past months
    if (actualCount > 0) {
        datasets.push({
            label: 'Факт (баланс)',
            data: actualBalanceData,
            borderColor: 'rgba(88, 140, 115, 1)',
            backgroundColor: 'rgba(88, 140, 115, 0.1)',
            tension: 0.3,
            borderWidth: 2.5,
            pointRadius: 4,
            pointBackgroundColor: 'rgba(88, 140, 115, 1)',
            pointBorderColor: 'rgba(88, 140, 115, 1)',
            fill: false,
            spanGaps: false
        });
    }
    
    // Scenario datasets — prepend nulls for actual months
    const scenarioColors = [
        'rgba(74, 130, 143, 1)', 
        'rgba(158, 133, 101, 1)', 
        'rgba(188, 107, 125, 1)'   
    ];
    
    const negativeColors = [
        'rgba(74, 130, 143, 0.65)', 
        'rgba(158, 133, 101, 0.65)',  
        'rgba(188, 107, 125, 0.65)'   
    ];

    for (let i = 0; i < loaded.length; i++) {
        const idx = loaded[i];
        const d = window.scenariosData[idx];
        const color = scenarioColors[i % scenarioColors.length];
        const negColor = negativeColors[i % negativeColors.length];
        const letter = idx === 1 ? 'А' : (idx === 2 ? 'Б' : 'В');
        
        // Bridge from last actual balance into forecast
        const bridgeVal = actualCount > 0 ? actuals.balance[actualCount - 1] : null;
        const forecastValues = d.data.map(f => f.cumulative);
        const scenarioData = actualCount > 0
            ? [...new Array(actualCount - 1).fill(null), bridgeVal, ...forecastValues]
            : forecastValues;
        
        datasets.push({
            label: `Сценарій ${letter}`,
            data: scenarioData,
            borderColor: color,
            backgroundColor: 'transparent',
            tension: 0.3,
            borderWidth: 2,
            borderDash: [6, 3],
            pointRadius: 3,
            pointBackgroundColor: ctx => {
                const val = ctx.parsed ? ctx.parsed.y : ctx.raw;
                return val !== null && val < 0 ? negColor : color;
            },
            pointBorderColor: ctx => {
                const val = ctx.parsed ? ctx.parsed.y : ctx.raw;
                return val !== null && val < 0 ? negColor : color;
            },
            segment: {
                borderColor: ctx => {
                    const y0 = ctx.p0.parsed.y;
                    const y1 = ctx.p1.parsed.y;
                    return (y0 < 0 || y1 < 0) ? negColor : color;
                },
                borderDash: ctx => {
                    const y0 = ctx.p0.parsed.y;
                    const y1 = ctx.p1.parsed.y;
                    return (y0 < 0 || y1 < 0) ? [4, 4] : [6, 3];
                }
            },
            spanGaps: false
        });
    }
    
    const ctxLine = document.getElementById('scenariosLineChart');
    if (ctxLine) {
        if (window.scenariosLineChartObj) window.scenariosLineChartObj.destroy();
        window.scenariosLineChartObj = new Chart(ctxLine, {
            type: 'line',
            data: { labels: allLabels, datasets: datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: textColor, font: { family: "'Inter', sans-serif", size: 12 } } }
                },
                scales: {
                    x: { 
                        ticks: { color: textColor, font: { family: "'Inter', sans-serif", size: 11 } },
                        grid: { color: gridColor }
                    },
                    y: { 
                        ticks: { color: textColor, font: { family: "'Inter', sans-serif", size: 11 } },
                        grid: { 
                            color: ctx => ctx.tick.value === 0 ? (isLight ? 'rgba(239, 68, 68, 0.4)' : 'rgba(248, 113, 113, 0.4)') : gridColor,
                            lineWidth: ctx => ctx.tick.value === 0 ? 2 : 1
                        }
                    }
                }
            }
        });
    }

    const gridContainer = document.getElementById('scenariosInitiativesGrid');
    if (gridContainer) {
        let activities = [];
        try {
            const res = await fetch(`${API_BASE}/forecast/activities`);
            if (res.ok) activities = await res.json();
        } catch(e) {}
        
        if (activities.length === 0) {
            gridContainer.innerHTML = "<p style='color:var(--text-secondary); font-size: 0.85rem;'>Немає запланованих ініціатив.</p>";
            return;
        }

        let html = `
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="border-bottom: 1px solid var(--border-color);">
                        <th style="padding: 0.5rem; text-align: left; vertical-align: middle; font-size: 0.8rem;">Ініціатива</th>
                        <th style="padding: 0.5rem; text-align: center; vertical-align: middle; width: 160px; font-size: 0.8rem;">Дата старту</th>
                        <th style="padding: 0.5rem; text-align: right; vertical-align: middle; width: 130px; font-size: 0.8rem;">Вартість</th>
                        ${loaded.map(idx => {
                            const tariffVal = window.scenarioParams[idx].tariff;
                            const letter = idx === 1 ? 'А' : (idx === 2 ? 'Б' : 'В');
                            return `
                                <th style="padding: 0.5rem; text-align: center; font-weight: normal; vertical-align: middle;">
                                    <div style="font-weight: 600; font-size: 0.85rem; margin-bottom: 4px; color: var(--text-primary);">Сценарій ${letter}</div>
                                    <div class="editable-pill" style="justify-content: center;">
                                        <input type="number" step="0.1" value="${tariffVal.toFixed(1)}" 
                                               onchange="window.updateScenarioTariff(${idx}, this.value)" 
                                               style="width: 45px;">
                                        <span class="pill-suffix">грн</span>
                                    </div>
                                </th>
                            `;
                        }).join('')}
                        <th style="padding: 0.5rem; text-align: center; vertical-align: middle; width: 60px; font-size: 0.8rem;">Дії</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        activities.sort((a, b) => a.planned_month.localeCompare(b.planned_month));

        for (const act of activities) {
            html += `<tr style="border-bottom: 1px solid rgba(255,255,255,0.05); transition: background 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.02)'" onmouseout="this.style.background='transparent'">
                        <td style="padding: 0.5rem; vertical-align: middle; font-size: 0.85rem;">
                            <strong>${act.name}</strong>
                            ${act.note ? `<div style="font-size:0.75rem; color:var(--text-secondary)">${act.note}</div>` : ''}
                        </td>
                        <td style="padding: 0.5rem; text-align: center; vertical-align: middle;">
                            <div class="editable-pill" style="justify-content: center;">
                                <input type="month" class="no-calendar-icon" value="${act.planned_month}" 
                                       onchange="window.updateActivityMonth(${act.id}, this.value)"
                                       style="width: 140px; text-align: center; font-size: 0.8rem;">
                            </div>
                        </td>
                        <td style="padding: 0.5rem; text-align: right; vertical-align: middle;">
                            <div class="editable-pill" style="justify-content: flex-end;">
                                <input type="number" step="100" value="${act.planned_amount}" 
                                       onchange="window.updateActivityAmount(${act.id}, this.value)"
                                       style="width: 75px; text-align: right; font-size: 0.8rem;">
                                <span class="pill-suffix">₴</span>
                            </div>
                        </td>
            `;
            
            for(const idx of loaded) {
                const isExcluded = window.scenarioExcludedActivities[idx] && window.scenarioExcludedActivities[idx].has(act.id);
                const isIncluded = !isExcluded;
                
                html += `<td style="padding: 0.5rem; text-align: center; cursor: pointer; vertical-align: middle;" onclick="window.toggleScenarioActivity(${idx}, ${act.id})" title="Натисніть щоб увімкнути/вимкнути">
                    ${isIncluded ? 
                        `<i class="fas fa-check-circle" style="font-size: 1.3rem; color: var(--success); transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.15)'" onmouseout="this.style.transform='scale(1)'"></i>` : 
                        `<i class="fas fa-times-circle" style="font-size: 1.3rem; color: var(--danger); transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.15)'" onmouseout="this.style.transform='scale(1)'"></i>`}
                </td>`;
            }
            
            html += `<td style="padding: 0.5rem; text-align: center; vertical-align: middle;">
                        <button class="btn btn-sm" onclick="window.deleteActivityGlobal(${act.id})" 
                                style="background: rgba(239, 68, 68, 0.1); color: var(--danger); border: 1px solid rgba(239, 68, 68, 0.2); border-radius: 6px; padding: 4px 8px; cursor: pointer; transition: all 0.2s;"
                                onmouseover="this.style.background='var(--danger)'; this.style.color='white'"
                                onmouseout="this.style.background='rgba(239, 68, 68, 0.1)'; this.style.color='var(--danger)'">
                            <i class="fas fa-trash"></i>
                        </button>
                     </td>`;
            
            html += `</tr>`;
        }
        
        // Add row for final balances
        html += `<tr style="border-top: 2px solid var(--border-color); font-weight: 600; background: rgba(255,255,255,0.03);">
            <td colspan="3" style="padding: 0.75rem; text-align: left; color: var(--text-primary); font-weight: 600; vertical-align: middle; font-size: 0.85rem;">
                Balance на кінець періоду
            </td>`;
        for(const idx of loaded) {
            const d = window.scenariosData[idx];
            const finalBalance = d ? d.finalBalance : 0;
            const balanceColor = finalBalance >= 0 ? 'var(--success)' : 'var(--danger)';
            html += `<td style="padding: 0.75rem; text-align: center; color: ${balanceColor}; font-weight: 700; vertical-align: middle; font-size: 0.85rem;">
                ${finalBalance >= 0 ? '+' : ''}${formatCurrency(finalBalance)} ₴
            </td>`;
        }
        html += `<td style="padding: 0.75rem; vertical-align: middle;"></td>`;
        html += `</tr>`;
        
        html += `</tbody></table>`;
        gridContainer.innerHTML = html;
    }
}

window.toggleScenarioActivity = async function(index, actId) {
    if (!window.scenarioExcludedActivities) window.scenarioExcludedActivities = {1: new Set(), 2: new Set(), 3: new Set()};
    if (window.scenarioExcludedActivities[index].has(actId)) {
        window.scenarioExcludedActivities[index].delete(actId);
    } else {
        window.scenarioExcludedActivities[index].add(actId);
    }
    await window.generateForecastScenario(index);
}

window.showAddActivityModalGlobal = function() {
    const now = new Date();
    const startMonth = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2, "0")}`;
    
    modalTitle.innerText = 'Add Initiative';
    modalBody.innerHTML = `
        <div class="form-group">
            <label>Назва ініціативи</label>
            <input type="text" id="global-act-name" class="form-control" style="width:100%;margin-bottom:1rem">
            <label>Amount (₴)</label>
            <input type="number" id="global-act-amount" class="form-control" style="width:100%;margin-bottom:1rem">
            <label>Місяць планування</label>
            <input type="month" id="global-act-month" class="form-control" style="width:100%" value="${startMonth}">
        </div>`;
    modal.style.display = 'flex';

    const submitBtn = document.getElementById('modal-submit');
    if (submitBtn) {
        submitBtn.onclick = async () => {
            const name = document.getElementById('global-act-name').value.trim();
            const amt = parseFloat(document.getElementById('global-act-amount').value);
            const month = document.getElementById('global-act-month').value;
            
            if (!name || !amt || !month) return alert('Заповніть всі поля');

            try {
                await fetch(`${API_BASE}/forecast/activities`, {
                    method: "POST", headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({ name: name, planned_month: month, planned_amount: amt, include_in_forecast: 1 })
                });
                closeModal();
                if (state.currentPage === 'dashboard') {
                    await renderDashboard();
                }
            } catch (e) {
                alert(e.message);
            }
        };
    }
};

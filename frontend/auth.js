// Authentication and Authorization logic

let currentUser = null;

// This function is called by Google Sign-In when the user successfully authenticates
async function handleGoogleLogin(response) {
    const googleToken = response.credential;
    const errorDiv = document.getElementById('login-error');
    errorDiv.style.display = 'none';
    
    try {
        const res = await fetch('/api/auth/login/google', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ token: googleToken })
        });
        
        const data = await res.json();
        
        if (!res.ok) {
            throw new Error(data.detail || 'Помилка авторизації');
        }
        
        // Save the internal JWT token and user info
        localStorage.setItem('zhbk_token', data.access_token);
        localStorage.setItem('zhbk_role', data.role);
        localStorage.setItem('zhbk_apartment_id', data.apartment_id || '');
        localStorage.setItem('zhbk_email', data.email);
        
        currentUser = data;
        
        // Setup UI for the current user
        applyRoleRestrictions();
        
        // Hide login overlay, show main app
        document.getElementById('login-overlay').style.display = 'none';
        document.getElementById('main-app').style.display = 'flex'; // It uses flex usually
        
        // Re-initialize or fetch initial data since app might have failed initial fetches without token
        if (typeof window.loadPage === 'function') {
            window.loadPage(currentUser.role === 'resident' ? 'charges' : 'reports');
        } else if (typeof window.loadDashboardData === 'function') {
            window.loadDashboardData();
        }
        
    } catch (error) {
        errorDiv.textContent = error.message;
        errorDiv.style.display = 'block';
        console.error('Login error:', error);
    }
}

function checkExistingLogin() {
    const token = localStorage.getItem('zhbk_token');
    const role = localStorage.getItem('zhbk_role');
    const email = localStorage.getItem('zhbk_email');
    const apartment_id = localStorage.getItem('zhbk_apartment_id');
    
    if (token && role && email) {
        currentUser = {
            access_token: token,
            role: role,
            email: email,
            apartment_id: apartment_id ? parseInt(apartment_id) : null
        };
        
        applyRoleRestrictions();
        document.getElementById('login-overlay').style.display = 'none';
        document.getElementById('main-app').style.display = 'flex';
        return true;
    }
    return false;
}

window.renderResidentSidebar = function(apt) {
    const resInfo = document.getElementById('resident-info-display');
    const userInfo = document.querySelector('.sidebar-footer .user-info');
    if (!resInfo) return;
    
    if (userInfo) userInfo.style.display = 'none';

    const isEn = (window.currentLang === 'en');
    const aptNum = (apt && apt.number) || (currentUser && currentUser.apartment_id) || '';
    const ownerName = (apt && apt.owner_name) || '';
    const area = (apt && apt.area_m2) ? `${apt.area_m2} ${isEn ? 'm²' : 'м²'}` : '—';
    const email = (apt && apt.email) || (currentUser && currentUser.email) || '—';

    resInfo.innerHTML = `
        <div class="resident-card-box">
            <div class="resident-header">
                <div class="resident-address-title">${isEn ? '14 Mykhailo Hrushevsky St.' : 'вул. Михайла Грушевського, 14'}</div>
                <div class="resident-apt-badge">${isEn ? 'Apt. #' : 'кв. №'}${aptNum}</div>
            </div>
            <div class="resident-details">
                <div class="resident-owner">${ownerName || (isEn ? 'Owner' : 'Власник')}</div>
                <div class="resident-meta">
                    <i class="fas fa-vector-square" style="font-size: 0.75rem; opacity: 0.8;"></i>
                    <span>${isEn ? 'Area:' : 'Площа:'} <b>${area}</b></span>
                </div>
                <div class="resident-email" title="${email}">
                    <i class="far fa-envelope" style="font-size: 0.75rem; opacity: 0.8;"></i>
                    <span>${email}</span>
                </div>
            </div>
            <button type="button" onclick="logout()" class="btn-resident-logout">
                <i class="fas fa-sign-out-alt"></i> ${isEn ? 'Sign out' : 'Вийти'}
            </button>
        </div>
    `;
    resInfo.style.display = 'block';
};

function applyRoleRestrictions() {
    if (!currentUser) return;
    
    const userInfo = document.querySelector('.sidebar-footer .user-info');
    const resInfo = document.getElementById('resident-info-display');
    const isEn = (window.currentLang === 'en');

    if (currentUser.role === 'admin') {
        if (resInfo) resInfo.style.display = 'none';
        if (userInfo) {
            userInfo.style.display = 'flex';
            userInfo.innerHTML = `
                <div style="display: flex; align-items: center; justify-content: space-between; width: 100%; gap: 8px;">
                    <div style="display: flex; align-items: center; gap: 8px; overflow: hidden;">
                        <div class="avatar" style="font-size: 1.2rem;">👤</div>
                        <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                            <div style="font-weight: 600; font-size: 0.875rem; color: var(--text-primary);">${isEn ? 'Admin' : 'Адміністратор'}</div>
                            <div style="font-size: 0.75rem; color: var(--text-secondary); text-overflow: ellipsis; overflow: hidden;" title="${currentUser.email}">${currentUser.email}</div>
                        </div>
                    </div>
                    <button type="button" onclick="logout()" title="${isEn ? 'Sign out' : 'Вийти'}" style="background: rgba(255,255,255,0.05); border: 1px solid var(--border-color); color: var(--text-secondary); cursor: pointer; padding: 5px 9px; font-size: 0.8125rem; border-radius: 6px; transition: all 0.2s;" onmouseover="this.style.color='#ef4444'; this.style.borderColor='rgba(239,68,68,0.4)'" onmouseout="this.style.color='var(--text-secondary)'; this.style.borderColor='var(--border-color)'">
                        <i class="fas fa-sign-out-alt"></i>
                    </button>
                </div>
            `;
        }
    } else if (currentUser.role === 'resident') {
        // Hide specific menu items for residents (transactions, receipts, settings)
        const hidePages = ['transactions', 'receipts', 'settings'];
        hidePages.forEach(page => {
            const el = document.querySelector(`.sidebar-nav li[data-page="${page}"]`);
            if (el) el.style.display = 'none';
        });

        // Ensure charges is the first item in sidebar for residents
        const navUl = document.querySelector('.sidebar-nav ul');
        const chargesLi = document.querySelector('.sidebar-nav li[data-page="charges"]');
        if (navUl && chargesLi && navUl.firstElementChild !== chargesLi) {
            navUl.prepend(chargesLi);
        }

        // Immediately render resident card or fetch apartment info
        if (currentUser.apartment_id) {
            fetch(`/api/apartments/${currentUser.apartment_id}`)
                .then(r => r.ok ? r.json() : null)
                .then(apt => {
                    window.renderResidentSidebar(apt);
                })
                .catch(() => {
                    window.renderResidentSidebar(null);
                });
        } else {
            window.renderResidentSidebar(null);
        }
    }
}

function logout() {
    localStorage.removeItem('zhbk_token');
    localStorage.removeItem('zhbk_role');
    localStorage.removeItem('zhbk_apartment_id');
    localStorage.removeItem('zhbk_email');
    currentUser = null;
    window.location.reload();
}

// Attach token to fetch requests globally (override fetch)
const originalFetch = window.fetch;
window.fetch = async function() {
    let [resource, config] = arguments;
    
    // Only intercept API calls
    if (typeof resource === 'string' && resource.startsWith('/api/')) {
        const token = localStorage.getItem('zhbk_token');
        if (token) {
            config = config || {};
            config.headers = config.headers || {};
            config.headers['Authorization'] = `Bearer ${token}`;
        }
    }
    
    const response = await originalFetch(resource, config);
    
    // If unauthorized, show login
    if (response.status === 401 && resource.startsWith('/api/')) {
        logout();
    }
    
    return response;
};

// Check login on load
document.addEventListener('DOMContentLoaded', () => {
    checkExistingLogin();
});

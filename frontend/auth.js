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
        if (typeof window.loadDashboardData === 'function') {
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

function applyRoleRestrictions() {
    if (!currentUser) return;
    
    // Update Sidebar User Info
    const userInfoSpan = document.querySelector('.sidebar-footer .user-info span');
    if (userInfoSpan) {
        if (currentUser.role === 'admin') {
            userInfoSpan.textContent = `Адміністратор (${currentUser.email})`;
        } else {
            userInfoSpan.textContent = `Мешканець Кв. ${currentUser.apartment_id}`;
        }
    }
    
    // Hide specific menu items for residents
    if (currentUser.role === 'resident') {
        const hidePages = ['transactions', 'reports', 'settings'];
        hidePages.forEach(page => {
            const el = document.querySelector(`.sidebar-nav li[data-page="${page}"]`);
            if (el) el.style.display = 'none';
        });
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

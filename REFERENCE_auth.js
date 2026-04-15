// Supabase Auth Client (shared across all pages)
// Include via <script src="/js/auth.js"></script>

var SUPABASE_URL = 'https://zrhussirvsgsoffmrkxb.supabase.co';
var SUPABASE_ANON_KEY = 'sb_publishable_MERSBCkwCzs880gVcz_J7Q_urxy9azM';
var ADMIN_EMAIL = 'nbamoment@gmail.com';

// Initialize Supabase client
const { createClient } = supabase;
const _supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// ── Auth helpers ────────────────────────────────────────

async function signUpWithEmail(email, password, displayName) {
    const { data, error } = await _supabase.auth.signUp({
        email,
        password,
        options: {
            data: { display_name: displayName || email.split('@')[0] }
        }
    });
    return { data, error };
}

async function signInWithEmail(email, password) {
    const { data, error } = await _supabase.auth.signInWithPassword({
        email,
        password
    });
    return { data, error };
}

async function signInWithGoogle() {
    const { data, error } = await _supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
            redirectTo: window.location.origin + '/index.html'
        }
    });
    return { data, error };
}

async function signOut() {
    const { error } = await _supabase.auth.signOut();
    if (!error) window.location.href = '/login.html';
    return { error };
}

async function getUser() {
    const { data: { session } } = await _supabase.auth.getSession();
    const { data: { user }, error } = await _supabase.auth.getUser();
    return { user, token: session?.access_token, error };
}

async function getSession() {
    const { data: { session }, error } = await _supabase.auth.getSession();
    return { session, error };
}

function isAdmin(user) {
    if (!user || !user.email) return false;
    const email = user.email.toLowerCase().trim();
    return email === 'nbamoment@gmail.com' || user.id === 'c337aaf8-b161-4d96-a6f4-35597dbdc4dd';
}

function getUserDisplayName(user) {
    if (!user) return 'Guest';
    return user.user_metadata?.display_name
        || user.user_metadata?.full_name
        || user.user_metadata?.name
        || user.email?.split('@')[0]
        || 'User';
}

function getUserAvatar(user) {
    if (!user) return null;
    return user.user_metadata?.avatar_url
        || user.user_metadata?.picture
        || null;
}

// ── Auth state listener ─────────────────────────────────

function onAuthStateChange(callback) {
    _supabase.auth.onAuthStateChange((event, session) => {
        callback(event, session);
    });
}

// ── Page guards ─────────────────────────────────────────

async function requireAuth() {
    const { session } = await getSession();
    if (!session) {
        window.location.href = '/login.html';
        return null;
    }
    return session;
}

async function requireAdmin() {
    const { user } = await getUser();
    if (!user || !isAdmin(user)) {
        window.location.href = '/index.html';
        return null;
    }
    return user;
}

// Update header UI based on auth state
async function updateHeaderAuth() {
    const { user } = await getUser();
    const authLink = document.getElementById('authLink');
    if (!authLink) return;

    if (user) {
        const name = getUserDisplayName(user);
        const avatar = getUserAvatar(user);
        const adminBadge = isAdmin(user) ? '<span class="ml-1 text-[9px] bg-primary text-black px-1 rounded font-bold">ADMIN</span>' : '';
        authLink.innerHTML = avatar
            ? `<img src="${avatar}" class="w-7 h-7 rounded-full border border-primary/30" alt="${name}" referrerpolicy="no-referrer"/>${adminBadge}`
            : `<span class="text-sm text-primary font-bold">${name}</span>${adminBadge}`;
        authLink.href = '/profile.html';

        // Trigger online status sync if not already active
        syncOnlineStatus(user.id);
    } else {
        authLink.innerHTML = '<span class="text-sm text-primary font-bold hover:underline">Login</span>';
        authLink.href = '/login.html';
    }
}

let _statusWs = null;
function syncOnlineStatus(userId) {
    if (_statusWs && _statusWs.readyState <= 1) return; // Already connecting or open

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${location.host}/ws/prices?userId=${userId}`);

    ws.onmessage = (e) => {
        try {
            const msg = JSON.parse(e.data);
            if (msg.type === 'prices' && typeof updatePriceTicker === 'function') {
                updatePriceTicker(msg.data);
            }
        } catch (err) { }
    };

    ws.onclose = () => {
        _statusWs = null;
        setTimeout(() => syncOnlineStatus(userId), 5000);
    };

    ws.onerror = () => {
        ws.close();
    };

    _statusWs = ws;
}

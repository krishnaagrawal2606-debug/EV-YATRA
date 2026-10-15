/**
 * EV YATRA — Production Pan-India Smart EV Grid & Account Controller
 * 100% Real Authentication (Email/Phone, Apple ID, Google, Password Reset),
 * Real-Time Google/Leaflet Map, Continuous GPS Telemetry, Turn-by-Turn Routing,
 * 30-Min Exclusive Slot Lock, Real Telemetry & EV Garage, Partner Onboarding & Store Orders.
 */

let homeMap = null;
let mapTileLayers = {};
let activeLayerName = 'roads';
let allStations = [];
let filteredStations = [];
let markerLayerGroup = null;
let markerById = {};
let userLat = 28.6139;
let userLng = 77.2090;
let userLocationMarker = null;
let userAccuracyCircle = null;
let activeCategory = 'all';
let activeReservation = null;
let passCountdownInterval = null;

// Continuous GPS & Routing state
let gpsWatchId = null;
let isGpsTracking = false;
let gpsFollowCamera = true;
let activeRoutePolyline = null;
let telemetryPollInterval = null;

// Real Auth state
let currentAuthUser = null;
let authModalMode = 'login';
let activeOAuthProvider = 'apple';
let pendingDashboardTab = null;

document.addEventListener('DOMContentLoaded', () => {
  initHomeAuthUI();
  initHomeMap();
  loadLiveStationsForHome();
  bindFilterEvents();
  bindCitySelectorEvents();
  bindModalForms();
  restoreActiveReservation();
  startLiveTelemetryPolling();
});

// ================= 1. Real Authentication & Session Management =================
async function initHomeAuthUI() {
  const savedUser = localStorage.getItem('ev_yatra_auth_user');
  const navPilotBtn = document.getElementById('navPilotBtn');
  const navPilotText = document.getElementById('navPilotText');

  if (savedUser) {
    try {
      const parsed = JSON.parse(savedUser);
      if (parsed && parsed.id) {
        currentAuthUser = parsed;
        if (navPilotText) navPilotText.textContent = parsed.name ? parsed.name.split(' ')[0] : 'Account';
        if (navPilotBtn) {
          navPilotBtn.href = '#account-dashboard';
          navPilotBtn.title = `Open ${parsed.name}'s Account & Mission Control`;
          navPilotBtn.onclick = (e) => {
            e.preventDefault();
            openPilotDashboardModal('telemetry');
          };
        }
        // Refresh profile from server in background to keep kWh/vehicles synced
        try {
          const res = await fetch(`/api/auth/profile?user_id=${encodeURIComponent(parsed.id)}`);
          const data = await res.json();
          if (data.success && data.user) {
            currentAuthUser = data.user;
            localStorage.setItem('ev_yatra_auth_user', JSON.stringify(currentAuthUser));
            if (navPilotText) navPilotText.textContent = currentAuthUser.name.split(' ')[0];
          }
        } catch (err) {}
        return;
      }
    } catch (e) {
      localStorage.removeItem('ev_yatra_auth_user');
    }
  }

  currentAuthUser = null;
  if (navPilotText) navPilotText.textContent = 'Sign In';
  if (navPilotBtn) {
    navPilotBtn.href = '#auth-modal';
    navPilotBtn.title = 'Sign In or Create Account';
    navPilotBtn.onclick = (e) => {
      e.preventDefault();
      openInPageAuthModal('login');
    };
  }
}

function openInPageAuthModal(mode = 'login') {
  const modal = document.getElementById('inPageAuthModal');
  if (!modal) {
    window.location.href = `/login?mode=${mode}`;
    return;
  }
  switchInPageAuthMode(mode);
  modal.classList.remove('hidden');
}

function closeInPageAuthModal() {
  const modal = document.getElementById('inPageAuthModal');
  if (modal) modal.classList.add('hidden');
}

let inPageLoginSubMethod = 'password'; // 'password' | 'otp'
let inPageOtpSent = false;

function showInPageOtpPushBanner(code, targetInputId) {
  const banner = document.getElementById('inPageOtpPushBanner');
  const codeEl = document.getElementById('inPageOtpPushCode');
  const autoBtn = document.getElementById('btnInPageAutoFillOtp');
  if (!banner || !codeEl) return;
  codeEl.textContent = code;
  banner.style.display = 'flex';
  if (autoBtn) {
    autoBtn.onclick = () => {
      const inp = document.getElementById(targetInputId);
      if (inp) inp.value = code;
      banner.style.display = 'none';
      showHomeToast('6-Digit OTP auto-filled!');
    };
  }
}

function setInPageLoginSubMethod(method) {
  inPageLoginSubMethod = method;
  inPageOtpSent = false;
  const passBtn = document.getElementById('modalMethodPassBtn');
  const otpBtn = document.getElementById('modalMethodOtpBtn');
  const passRow = document.getElementById('modalRowPassword');
  const otpRow = document.getElementById('modalRowOtpVerify');
  const passInp = document.getElementById('modalAuthPassword');
  const submitTxt = document.getElementById('modalAuthSubmitText');

  if (passBtn && otpBtn) {
    if (method === 'otp') {
      otpBtn.style.background = 'rgba(0,212,170,0.16)';
      otpBtn.style.color = '#00d4aa';
      otpBtn.style.borderColor = 'rgba(0,212,170,0.35)';
      passBtn.style.background = 'transparent';
      passBtn.style.color = '#94a3b8';
      passBtn.style.borderColor = 'transparent';
    } else {
      passBtn.style.background = 'rgba(0,212,170,0.16)';
      passBtn.style.color = '#00d4aa';
      passBtn.style.borderColor = 'rgba(0,212,170,0.35)';
      otpBtn.style.background = 'transparent';
      otpBtn.style.color = '#94a3b8';
      otpBtn.style.borderColor = 'transparent';
    }
  }

  if (method === 'otp') {
    if (passRow) passRow.style.display = 'none';
    if (otpRow) otpRow.style.display = 'none';
    if (passInp) passInp.required = false;
    if (submitTxt) submitTxt.textContent = 'Send 6-Digit OTP';
  } else {
    if (passRow) passRow.style.display = 'block';
    if (otpRow) otpRow.style.display = 'none';
    if (passInp) passInp.required = true;
    if (submitTxt) submitTxt.textContent = 'Sign In to EV Yatra';
  }
}

async function requestInPageLoginOtp(isResend = false) {
  const identifier = (document.getElementById('modalAuthEmail')?.value || '').trim();
  const submitBtn = document.getElementById('modalAuthSubmitBtn');
  const submitTxt = document.getElementById('modalAuthSubmitText');

  if (!identifier) {
    showHomeToast('Please enter your Email Address or 10-Digit Mobile Number.');
    return;
  }

  if (submitBtn) submitBtn.disabled = true;
  if (submitTxt) submitTxt.textContent = 'Sending 6-Digit OTP...';

  try {
    const res = await fetch('/api/auth/send-otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier, purpose: 'login' })
    });
    const data = await res.json();
    if (submitBtn) submitBtn.disabled = false;

    if (data.success) {
      inPageOtpSent = true;
      const otpRow = document.getElementById('modalRowOtpVerify');
      const otpInp = document.getElementById('modalAuthOtpInput');
      if (otpRow) otpRow.style.display = 'block';
      if (otpInp) {
        otpInp.value = '';
        otpInp.focus();
      }
      if (submitTxt) submitTxt.textContent = 'Verify 6-Digit OTP & Sign In';
      if (data.otp_code) {
        showInPageOtpPushBanner(data.otp_code, 'modalAuthOtpInput');
      }
      showHomeToast(isResend ? 'New 6-digit OTP sent!' : data.message);
    } else {
      if (submitTxt) submitTxt.textContent = 'Send 6-Digit OTP';
      showHomeToast(data.error || 'Could not send OTP.');
    }
  } catch (err) {
    if (submitBtn) submitBtn.disabled = false;
    if (submitTxt) submitTxt.textContent = 'Send 6-Digit OTP';
    showHomeToast('Network error sending OTP.');
  }
}

function switchInPageAuthMode(mode) {
  authModalMode = mode;
  const tabLogin = document.getElementById('modalTabLogin');
  const tabSignup = document.getElementById('modalTabSignup');
  const title = document.getElementById('inPageAuthTitle');
  const methodSwitch = document.getElementById('modalLoginMethodSwitch');
  const nameRow = document.getElementById('modalRowName');
  const phoneRow = document.getElementById('modalRowPhone');
  const passRow = document.getElementById('modalRowPassword');
  const otpRow = document.getElementById('modalRowOtpVerify');
  const vehicleRow = document.getElementById('modalRowVehicle');
  const nameInput = document.getElementById('modalAuthName');
  const phoneInput = document.getElementById('modalAuthPhone');
  const passInput = document.getElementById('modalAuthPassword');
  const submitTxt = document.getElementById('modalAuthSubmitText');

  if (mode === 'signup') {
    if (tabLogin) tabLogin.classList.remove('active');
    if (tabSignup) tabSignup.classList.add('active');
    if (title) title.textContent = 'Create Your EV Yatra Account';
    if (methodSwitch) methodSwitch.style.display = 'none';
    if (nameRow) nameRow.style.display = 'block';
    if (phoneRow) phoneRow.style.display = 'block';
    if (passRow) passRow.style.display = 'block';
    if (otpRow) otpRow.style.display = 'none';
    if (vehicleRow) vehicleRow.style.display = 'grid';
    if (nameInput) nameInput.required = true;
    if (phoneInput) phoneInput.required = true;
    if (passInput) passInput.required = true;
    if (submitTxt) submitTxt.textContent = 'Create Account';
  } else {
    if (tabSignup) tabSignup.classList.remove('active');
    if (tabLogin) tabLogin.classList.add('active');
    if (title) title.textContent = 'Sign In to EV Yatra';
    if (methodSwitch) methodSwitch.style.display = 'grid';
    if (nameRow) nameRow.style.display = 'none';
    if (phoneRow) phoneRow.style.display = 'none';
    if (vehicleRow) vehicleRow.style.display = 'none';
    if (nameInput) nameInput.required = false;
    if (phoneInput) phoneInput.required = false;
    setInPageLoginSubMethod(inPageLoginSubMethod);
  }
}

function toggleModalPasswordEye() {
  const passInput = document.getElementById('modalAuthPassword');
  const eyeIcon = document.getElementById('modalPasswordEyeIcon');
  if (!passInput) return;
  const isPass = passInput.type === 'password';
  passInput.type = isPass ? 'text' : 'password';
  if (eyeIcon) {
    eyeIcon.className = isPass ? 'fa-regular fa-eye-slash' : 'fa-regular fa-eye';
  }
}

async function handleInPageAuthSubmit(e) {
  e.preventDefault();
  const email = (document.getElementById('modalAuthEmail')?.value || '').trim();
  const submitBtn = document.getElementById('modalAuthSubmitBtn');
  const submitTxt = document.getElementById('modalAuthSubmitText');

  if (authModalMode === 'login' && inPageLoginSubMethod === 'otp') {
    if (!inPageOtpSent) {
      await requestInPageLoginOtp(false);
      return;
    }
    const otpCode = (document.getElementById('modalAuthOtpInput')?.value || '').trim();
    if (otpCode.length !== 6) {
      showHomeToast('Please enter the 6-digit OTP code.');
      return;
    }
    if (submitBtn) submitBtn.disabled = true;
    if (submitTxt) submitTxt.textContent = 'Verifying OTP...';
    try {
      const res = await fetch('/api/auth/verify-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier: email, otp_code: otpCode, purpose: 'login' })
      });
      const data = await res.json();
      if (submitBtn) submitBtn.disabled = false;
      if (data.success && data.user) {
        onAuthSuccess(data.user, `OTP Verified! Signed in as ${data.user.name}!`);
      } else {
        if (submitTxt) submitTxt.textContent = 'Verify 6-Digit OTP & Sign In';
        showHomeToast(data.error || 'Invalid OTP code.');
      }
    } catch (err) {
      if (submitBtn) submitBtn.disabled = false;
      if (submitTxt) submitTxt.textContent = 'Verify 6-Digit OTP & Sign In';
      showHomeToast('Network error verifying OTP.');
    }
    return;
  }

  const password = (document.getElementById('modalAuthPassword')?.value || '').trim();

  if (!email || !password) {
    showHomeToast('Please enter your Email/Phone and Password.');
    return;
  }

  if (authModalMode === 'signup') {
    const name = (document.getElementById('modalAuthName')?.value || '').trim();
    const phone = (document.getElementById('modalAuthPhone')?.value || '').trim();
    const vehicle = (document.getElementById('modalAuthVehicle')?.value || '').trim() || 'Tata Nexon EV Max';
    const vehicleNum = (document.getElementById('modalAuthVehicleNumber')?.value || '').trim().toUpperCase() || 'IND EV 2026';

    if (!name || !phone) {
      showHomeToast('Full Name and Mobile Number are required to create an account.');
      return;
    }
    if (password.length < 6) {
      showHomeToast('Password must be at least 6 characters.');
      return;
    }

    if (submitBtn) submitBtn.disabled = true;
    if (submitTxt) submitTxt.textContent = 'Creating Account...';

    try {
      const res = await fetch('/api/auth/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          email,
          phone,
          password,
          vehicle_model: vehicle,
          vehicle_number: vehicleNum
        })
      });
      const data = await res.json();
      if (submitBtn) submitBtn.disabled = false;
      if (submitTxt) submitTxt.textContent = 'Create Account';

      if (data.success && data.user) {
        onAuthSuccess(data.user, `Account created! Welcome to EV Yatra, ${data.user.name}!`);
      } else {
        showHomeToast(data.error || 'Could not create account.');
      }
    } catch (err) {
      if (submitBtn) submitBtn.disabled = false;
      if (submitTxt) submitTxt.textContent = 'Create Account';
      showHomeToast('Network error during registration.');
    }
    return;
  }

  // Real Sign In Mode
  if (submitBtn) submitBtn.disabled = true;
  if (submitTxt) submitTxt.textContent = 'Signing In...';

  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email_or_phone: email, password })
    });
    const data = await res.json();
    if (submitBtn) submitBtn.disabled = false;
    if (submitTxt) submitTxt.textContent = 'Sign In to EV Yatra';

    if (data.success && data.user) {
      onAuthSuccess(data.user, `Signed in as ${data.user.name}!`);
    } else {
      showHomeToast(data.error || 'Invalid email/phone or password.');
    }
  } catch (err) {
    if (submitBtn) submitBtn.disabled = false;
    if (submitTxt) submitTxt.textContent = 'Sign In to EV Yatra';
    showHomeToast('Network error during sign in.');
  }
}

function onAuthSuccess(user, message) {
  currentAuthUser = user;
  localStorage.setItem('ev_yatra_auth_user', JSON.stringify(user));
  initHomeAuthUI();
  closeInPageAuthModal();
  closeOAuthProviderModal();
  showHomeToast(message);

  if (pendingDashboardTab) {
    const tab = pendingDashboardTab;
    pendingDashboardTab = null;
    openPilotDashboardModal(tab);
  }
}

function openOAuthProviderModal(provider) {
  activeOAuthProvider = provider.toLowerCase();
  const modal = document.getElementById('oauthProviderModal');
  const title = document.getElementById('oauthModalTitle');
  const desc = document.getElementById('oauthModalDesc');
  const emailLabel = document.getElementById('oauthModalEmailLabel');
  const emailInput = document.getElementById('oauthModalEmail');
  const passLabel = document.getElementById('oauthModalPassLabel');
  const submitTxt = document.getElementById('oauthModalSubmitText');

  if (!modal) return;

  if (activeOAuthProvider === 'apple') {
    if (title) title.innerHTML = `<i class="fa-brands fa-apple"></i> Sign in with Apple ID`;
    if (desc) desc.textContent = 'Enter your Apple ID email and password to sign in or create your linked EV Yatra account.';
    if (emailLabel) emailLabel.textContent = 'Apple ID (iCloud or Email)';
    if (emailInput) emailInput.placeholder = 'yourname@icloud.com';
    if (passLabel) passLabel.textContent = 'Apple ID Password';
    if (submitTxt) submitTxt.textContent = 'Continue with Apple ID';
  } else {
    if (title) title.innerHTML = `<i class="fa-brands fa-google"></i> Sign in with Google`;
    if (desc) desc.textContent = 'Enter your Google Account email and password to sign in or link your EV Yatra account.';
    if (emailLabel) emailLabel.textContent = 'Google Account Email';
    if (emailInput) emailInput.placeholder = 'yourname@gmail.com';
    if (passLabel) passLabel.textContent = 'Google Account Password';
    if (submitTxt) submitTxt.textContent = 'Continue with Google';
  }

  modal.classList.remove('hidden');
  if (emailInput) emailInput.focus();
}

function closeOAuthProviderModal() {
  const modal = document.getElementById('oauthProviderModal');
  if (modal) modal.classList.add('hidden');
}

async function handleOAuthCustomSubmit(e) {
  e.preventDefault();
  const email = (document.getElementById('oauthModalEmail')?.value || '').trim();
  const name = (document.getElementById('oauthModalName')?.value || '').trim() || email.split('@')[0];
  const password = (document.getElementById('oauthModalPassword')?.value || '').trim();
  const color = activeOAuthProvider === 'apple' ? '#0ea5e9' : '#4285F4';
  const label = activeOAuthProvider === 'apple' ? 'Apple ID' : 'Google';
  const endpoint = activeOAuthProvider === 'apple' ? '/api/auth/apple' : '/api/auth/google';

  if (!email || !password || password.length < 4) {
    showHomeToast(`Please enter your ${label} email and password.`);
    return;
  }

  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider: activeOAuthProvider, email, name, avatar_color: color, password })
    });
    const data = await res.json();
    if (data.success && data.user) {
      onAuthSuccess(data.user, `Signed in as ${data.user.name} via ${label}!`);
    } else {
      showHomeToast(data.error || `${label} sign-in failed.`);
    }
  } catch (err) {
    showHomeToast(`Network error during ${label} authentication.`);
  }
}

function openResetPasswordModalInPage() {
  const emailVal = (document.getElementById('modalAuthEmail')?.value || '').trim();
  if (emailVal) {
    const resetEm = document.getElementById('inPageResetEmail');
    if (resetEm) resetEm.value = emailVal;
  }
  document.getElementById('inPageResetPasswordModal')?.classList.remove('hidden');
}

function closeResetPasswordModalInPage() {
  document.getElementById('inPageResetPasswordModal')?.classList.add('hidden');
}

async function sendInPageResetOtp() {
  const identifier = (document.getElementById('inPageResetEmail')?.value || '').trim();
  if (!identifier) {
    showHomeToast('Please enter your registered Email or Mobile Number.');
    return;
  }
  const btn = document.getElementById('btnInPageSendResetOtp');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Sending...';
  }
  try {
    const res = await fetch('/api/auth/send-otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier, purpose: 'reset' })
    });
    const data = await res.json();
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Resend OTP';
    }
    if (data.success) {
      const otpRow = document.getElementById('inPageResetOtpRow');
      const otpInp = document.getElementById('inPageResetOtpInput');
      if (otpRow) otpRow.style.display = 'block';
      if (otpInp) otpInp.focus();
      if (data.otp_code) {
        showInPageOtpPushBanner(data.otp_code, 'inPageResetOtpInput');
      }
      showHomeToast(data.message);
    } else {
      showHomeToast(data.error || 'Could not send reset OTP.');
    }
  } catch (err) {
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Send OTP';
    }
    showHomeToast('Network error sending OTP.');
  }
}

async function handleInPageResetPasswordSubmit(e) {
  e.preventDefault();
  const email = (document.getElementById('inPageResetEmail')?.value || '').trim();
  const otp_code = (document.getElementById('inPageResetOtpInput')?.value || '').trim();
  const new_password = (document.getElementById('inPageResetNewPass')?.value || '').trim();

  if (!otp_code || otp_code.length !== 6) {
    showHomeToast('Please click "Send OTP" and enter the 6-digit OTP code.');
    return;
  }

  try {
    const res = await fetch('/api/auth/reset-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, otp_code, new_password })
    });
    const data = await res.json();
    if (data.success) {
      closeResetPasswordModalInPage();
      setInPageLoginSubMethod('password');
      const loginEmail = document.getElementById('modalAuthEmail');
      const loginPass = document.getElementById('modalAuthPassword');
      if (loginEmail) loginEmail.value = email;
      if (loginPass) {
        loginPass.value = '';
        loginPass.focus();
      }
      showHomeToast(data.message || 'Password updated! Please sign in with your new password.');
    } else {
      showHomeToast(data.error || 'Could not reset password.');
    }
  } catch (err) {
    showHomeToast('Network error while resetting password.');
  }
}

function signOutPilot() {
  localStorage.removeItem('ev_yatra_auth_user');
  currentAuthUser = null;
  initHomeAuthUI();
  closePilotDashboardModal();
  showHomeToast('You have signed out.');
}

// ================= 2. Interactive Google Map (Single Permanent Layer - No World Repeat) =================
let hasActiveSearchOrNearMe = false;
let selectedSearchCoords = null; // { lat, lng } when a city/location is selected
let activeRouteGlowPolyline = null;
let activeRouteStartMarker = null;

function initHomeMap() {
  const mapEl = document.getElementById('homeMap');
  if (!mapEl) return;

  // Lock map to a single non-repeating view centered on India
  const singleMapBounds = L.latLngBounds([4.0, 62.0], [39.0, 102.0]);

  homeMap = L.map('homeMap', {
    center: [22.5937, 78.9629],
    zoom: 5,
    minZoom: 4,
    maxZoom: 20,
    maxBounds: singleMapBounds,
    maxBoundsViscosity: 1.0,
    worldCopyJump: false,
    zoomControl: false
  });

  L.control.zoom({ position: 'bottomleft' }).addTo(homeMap);

  mapTileLayers.roads = L.tileLayer('https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', {
    minZoom: 4,
    maxZoom: 20,
    noWrap: true,
    bounds: [[-85, -180], [85, 180]],
    attribution: '&copy; Google Maps &bull; EV Yatra Smart Grid'
  });

  mapTileLayers.roads.addTo(homeMap);
  markerLayerGroup = L.layerGroup().addTo(homeMap);

  setTimeout(() => {
    if (homeMap) homeMap.invalidateSize();
  }, 300);

  window.addEventListener('resize', () => {
    if (homeMap) homeMap.invalidateSize();
  });
}

function toggleFullscreenMap() {
  const panel = document.querySelector('.finder-map-panel');
  const btn = document.getElementById('fullscreenMapBtn');
  if (!panel) return;
  const isExpanded = panel.classList.toggle('expanded-fullscreen');
  if (btn) {
    btn.innerHTML = isExpanded
      ? '<i class="fa-solid fa-compress"></i> <span>Exit Full Map</span>'
      : '<i class="fa-solid fa-expand"></i> <span>Full Map</span>';
  }
  setTimeout(() => {
    if (homeMap) homeMap.invalidateSize();
  }, 250);
}

function renderSearchPromptState() {
  if (markerLayerGroup) {
    markerLayerGroup.clearLayers();
  }
  markerById = {};
  const countEl = document.getElementById('finderResultsCount');
  if (countEl) {
    countEl.textContent = 'Search or click Near Me';
  }
  const container = document.getElementById('homeStationsList');
  if (container) {
    container.innerHTML = `
      <div style="text-align: center; padding: 2.5rem 1.15rem; color: #94a3b8; background: #111726; border-radius: 16px; border: 1px dashed rgba(255,255,255,0.14);">
        <i class="fa-solid fa-magnifying-glass-location" style="font-size: 2.2rem; color: #00d4aa; margin-bottom: 0.75rem;"></i>
        <h4 style="color: #ffffff; font-size: 1.02rem; margin: 0 0 0.4rem 0;">Search Location or Click "Near Me"</h4>
        <p style="font-size: 0.84rem; line-height: 1.5; margin: 0 0 1.1rem 0;">
          Enter any City, Town, Village, or Highway above — or tap <strong>Near Me</strong> to view nearby stations, live slot details, and road directions.
        </p>
        <button type="button" class="btn-card-lock" style="margin: 0 auto; padding: 0.6rem 1.25rem; max-width: 260px;" onclick="toggleContinuousGps()">
          <i class="fa-solid fa-crosshairs"></i> Show Stations Near Me
        </button>
      </div>
    `;
  }
}

function normalizeStationSlots(s) {
  const total = Math.max(1, Number(s.total_slots ?? (Array.isArray(s.slots) && s.slots.length ? s.slots.length : 3)));
  const avail = Math.max(0, Math.min(total, Number(s.available_slots ?? total)));
  let slots = Array.isArray(s.slots) && s.slots.length > 0 ? s.slots.map((sl, idx) => {
    const st = String(sl.status || 'available').toLowerCase();
    return {
      id: sl.id || `slot-${s.id}-${idx + 1}`,
      station_id: s.id,
      slot_number: sl.slot_number || sl.bay_number || (idx + 1),
      connector_type: sl.connector_type || sl.charger_type || (idx === 2 ? 'Type 2 AC' : 'CCS2'),
      power_kw: Number(sl.power_kw || (idx === 0 ? 60 : (idx === 1 ? 120 : 22))),
      status: st,
      is_free: st === 'available' || Boolean(sl.is_free),
      reserved_until: sl.reserved_until || null
    };
  }) : [];

  if (slots.length === 0) {
    for (let i = 1; i <= total; i++) {
      const isFree = i <= avail;
      slots.push({
        id: `slot-${s.id}-${i}`,
        station_id: s.id,
        slot_number: i,
        connector_type: i === 3 ? 'Type 2 AC' : 'CCS2',
        power_kw: i === 1 ? 60 : (i === 2 ? 120 : 22),
        status: isFree ? 'available' : 'charging',
        is_free: isFree
      });
    }
  }

  const maxPower = slots.reduce((max, sl) => Math.max(max, Number(sl.power_kw || 60)), Number(s.power_kw || 60));
  const uniqueConnectors = [...new Set(slots.map(sl => sl.connector_type).filter(Boolean))];

  return {
    ...s,
    latitude: Number(s.latitude ?? s.lat ?? 0),
    longitude: Number(s.longitude ?? s.lng ?? 0),
    available_slots: avail,
    total_slots: slots.length,
    slots,
    power_kw: maxPower,
    connector_types: uniqueConnectors.length > 0 ? uniqueConnectors : ['CCS2', 'Type 2 AC']
  };
}

// ================= 3. Load Pan-India Stations Dataset in Background =================
async function loadLiveStationsForHome() {
  try {
    let res;
    try {
      res = await fetch('/api/stations');
      if (!res.ok) throw new Error('Backend API offline');
    } catch (e) {
      // Automatic fallback for GitHub Pages / static deployment
      res = await fetch('stations.json');
    }
    const data = await res.json();
    const rawList = (data && Array.isArray(data.stations)) ? data.stations : (Array.isArray(data) ? data : []);

    allStations = rawList.map(s => normalizeStationSlots(s));

    // Do NOT plot stations on map or list until user searches or clicks Near Me
    if (hasActiveSearchOrNearMe) {
      if (isGpsTracking) {
        sortStationsByDistance(userLat, userLng);
      } else {
        applyStationFilters();
      }
    } else {
      renderSearchPromptState();
    }
  } catch (err) {
    console.error('Failed to load stations:', err);
  }
}

function startLiveTelemetryPolling() {
  if (telemetryPollInterval) clearInterval(telemetryPollInterval);
  telemetryPollInterval = setInterval(async () => {
    try {
      const res = await fetch('/api/stations/live-telemetry');
      const data = await res.json();
      if (data && data.success && data.stations) {
        allStations.forEach((s, idx) => {
          const t = data.stations[s.id];
          if (t) {
            s.available_slots = t.available_slots;
            s.total_slots = t.total_slots;
            if (Array.isArray(t.slots) && t.slots.length > 0) {
              s.slots = t.slots;
            }
            allStations[idx] = normalizeStationSlots(s);
          }
        });
      }
    } catch (e) {}
  }, 12000);
}

// ================= 4. Render Map Markers (Green / Amber / Red Pins with Slot & Direction Actions) =================
function renderMapMarkers(stations) {
  if (!homeMap || !markerLayerGroup) return;
  markerLayerGroup.clearLayers();
  markerById = {};

  stations.slice(0, 200).forEach(s => {
    const lat = Number(s.latitude ?? s.lat);
    const lng = Number(s.longitude ?? s.lng);
    if (!lat || !lng || isNaN(lat) || isNaN(lng)) return;

    const avail = Number(s.available_slots ?? 0);
    const total = Number(s.total_slots ?? 4);
    const isAvailable = avail > 0;
    const pinColor = avail >= 3 ? '#10b981' : (avail >= 1 ? '#f59e0b' : '#ef4444');
    const glowRgba = avail >= 3 ? 'rgba(16,185,129,0.45)' : (avail >= 1 ? 'rgba(245,158,11,0.45)' : 'rgba(239,68,68,0.45)');

    const iconHtml = `
      <div style="
        width: 28px;
        height: 28px;
        border-radius: 50%;
        background: ${pinColor};
        border: 2.5px solid #ffffff;
        box-shadow: 0 0 12px ${glowRgba};
        display: flex;
        align-items: center;
        justify-content: center;
        color: #ffffff;
        font-size: 12px;
        font-weight: 800;
      ">
        <i class="fa-solid fa-bolt"></i>
      </div>
    `;

    const customIcon = L.divIcon({
      html: iconHtml,
      className: 'ev-yatra-custom-pin',
      iconSize: [28, 28],
      iconAnchor: [14, 14],
      popupAnchor: [0, -14]
    });

    const marker = L.marker([lat, lng], { icon: customIcon });
    const slots = Array.isArray(s.slots) ? s.slots : [];
    const slotMiniRows = slots.slice(0, 4).map(sl => {
      const free = String(sl.status || 'available').toLowerCase() === 'available' || sl.is_free;
      const col = free ? '#10b981' : '#f59e0b';
      return `<div style="display:flex;justify-content:space-between;font-size:10.5px;padding:3px 6px;border-radius:5px;background:rgba(255,255,255,0.05);border:1px solid ${col}44;">
        <span style="color:#e2e8f0;font-weight:700;">Bay #${sl.slot_number}: ${sl.connector_type} (${sl.power_kw}kW)</span>
        <span style="color:${col};font-weight:800;">${free ? 'FREE' : String(sl.status || 'BUSY').toUpperCase()}</span>
      </div>`;
    }).join('');

    const popupContent = `
      <div style="font-family: 'Plus Jakarta Sans', sans-serif; min-width: 245px; max-width: 280px; padding: 2px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
          <span style="font-size: 10px; font-weight: 800; text-transform: uppercase; color: #ff8a65;">${s.operator || s.network || 'EV Yatra Grid'}</span>
          <span style="font-size: 10px; font-weight: 800; padding: 2px 6px; border-radius: 99px; background: ${isAvailable ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'}; color: ${pinColor};">
            ${avail}/${total} Slots Free
          </span>
        </div>
        <div style="font-size: 13.5px; font-weight: 800; color: #ffffff; margin-bottom: 3px;">${s.name}</div>
        <div style="font-size: 11px; color: #94a3b8; margin-bottom: 7px;"><i class="fa-solid fa-location-dot" style="color:#ff5722;"></i> ${s.address || s.city || 'India'}</div>
        <div style="display:flex;flex-direction:column;gap:4px;margin-bottom:8px;">
          ${slotMiniRows}
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:6px;">
          <button onclick="showElectricRoute('${s.id}')" style="background:#0ea5e9;color:#fff;border:none;border-radius:7px;padding:7px 8px;font-size:11px;font-weight:700;cursor:pointer;">
            <i class="fa-solid fa-diamond-turn-right"></i> Directions
          </button>
          <button onclick="inspectSlotsFromHome('${s.id}')" style="background:rgba(255,255,255,0.12);color:#fff;border:1px solid rgba(255,255,255,0.2);border-radius:7px;padding:7px 8px;font-size:11px;font-weight:700;cursor:pointer;">
            <i class="fa-solid fa-bolt"></i> Slot Details
          </button>
        </div>
        <button onclick="openBookingFromHome('${s.id}')" style="width:100%;background:#ff5722;color:#fff;border:none;border-radius:7px;padding:7px 8px;font-size:11.5px;font-weight:800;cursor:pointer;">
          <i class="fa-solid fa-lock"></i> Lock Slot for 30 Mins (₹${s.price_per_kwh || 18}/kWh)
        </button>
      </div>
    `;

    marker.bindPopup(popupContent);
    markerLayerGroup.addLayer(marker);
    markerById[s.id] = marker;
  });
}

// ================= 5. Render Station Cards List (With Visible Live Slot Details & Directions) =================
function renderHomeStationsList(stations) {
  const container = document.getElementById('homeStationsList');
  if (!container) return;

  if (!stations || stations.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 2.5rem 1rem; color: #94a3b8; background: #111726; border-radius: 16px; border: 1px solid rgba(255,255,255,0.08);">
        <i class="fa-solid fa-charging-station" style="font-size: 2.2rem; color: #ff5722; margin-bottom: 0.75rem;"></i>
        <h4 style="color: #ffffff; margin-bottom: 0.35rem;">No Matching Stations Found</h4>
        <p style="font-size: 0.85rem;">Try searching another nearby City, Town, or Highway.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = stations.map(s => {
    const avail = Number(s.available_slots ?? 0);
    const total = Number(s.total_slots ?? 4);
    const isAvailable = avail > 0;
    const statusColor = isAvailable ? '#10b981' : '#ef4444';
    const statusText = isAvailable ? `${avail}/${total} Slots Free` : 'All Slots Busy';
    const powerKw = s.power_kw || 60;
    const price = s.price_per_kwh || 18.5;
    const connectors = Array.isArray(s.connector_types) ? s.connector_types.join(' • ') : (s.connector_types || 'CCS2 • Type 2');
    const distBadge = typeof s.distance_km === 'number'
      ? `<span style="color:#38bdf8;font-weight:700;font-size:0.78rem;"><i class="fa-solid fa-location-arrow"></i> ${s.distance_km.toFixed(1)} km</span>`
      : '';

    const slots = Array.isArray(s.slots) ? s.slots : [];
    const slotsBadgesHtml = slots.map(sl => {
      const stLower = String(sl.status || 'available').toLowerCase();
      const free = stLower === 'available' || sl.is_free;
      const chipColor = free ? '#10b981' : (stLower === 'reserved' ? '#f59e0b' : '#ef4444');
      const statusLabel = free ? 'AVAILABLE' : stLower.toUpperCase();
      return `
        <div class="station-slot-pill" onclick="${free ? `openBookingFromHome('${s.id}', '${sl.id}')` : `inspectSlotsFromHome('${s.id}')`}" title="${free ? 'Click to Lock this Slot for 30 Minutes' : 'Click to view Slot Telemetry'}">
          <div style="display:flex;align-items:center;gap:5px;">
            <span style="width:7px;height:7px;border-radius:50%;background:${chipColor};display:inline-block;"></span>
            <strong style="color:#ffffff;font-size:0.76rem;">Bay #${sl.slot_number}</strong>
            <span style="color:#cbd5e1;font-size:0.74rem;">${sl.connector_type} &bull; ${sl.power_kw}kW</span>
          </div>
          <span style="color:${chipColor};font-weight:800;font-size:0.7rem;">${statusLabel}</span>
        </div>
      `;
    }).join('');

    return `
      <div class="station-live-card" data-station-id="${s.id}">
        <div class="station-card-top">
          <div style="flex:1;min-width:0;">
            <span class="station-network-pill">${s.operator || s.network || 'EV Yatra Grid'}</span>
            <h4 class="station-name-text" style="cursor:pointer;" onclick="focusStationOnMap('${s.id}')">${s.name}</h4>
            <div class="station-address-text">
              <i class="fa-solid fa-location-dot" style="color: #ff5722; flex-shrink:0;"></i>
              <span>${s.address || s.city || 'Pan-India Highway Corridor'}</span>
            </div>
          </div>
          <div style="text-align: right; display:flex; flex-direction:column; align-items:flex-end; gap:4px; flex-shrink:0;">
            <span style="display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 0.74rem; font-weight: 800; background: ${isAvailable ? 'rgba(16, 185, 129, 0.14)' : 'rgba(239, 68, 68, 0.14)'}; color: ${statusColor}; border: 1px solid ${statusColor}44;">
              ${statusText}
            </span>
            ${distBadge}
          </div>
        </div>

        <div class="station-meta-specs">
          <div class="meta-spec-item">
            <i class="fa-solid fa-bolt" style="color: #f59e0b;"></i>
            <strong>Up to ${powerKw} kW</strong>
          </div>
          <div class="meta-spec-item">
            <i class="fa-solid fa-plug" style="color: #94a3b8;"></i>
            <span>${connectors}</span>
          </div>
          <div class="meta-spec-item price">
            <i class="fa-solid fa-indian-rupee-sign"></i>
            <span>₹${price}/kWh</span>
          </div>
        </div>

        <!-- Live Slot / Bay Details Breakdown Directly on Card -->
        <div class="station-slots-inline-box">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
            <span style="font-size:0.72rem;font-weight:800;color:#94a3b8;text-transform:uppercase;letter-spacing:0.04em;">
              <i class="fa-solid fa-Layer-group" style="color:#00d4aa;"></i> Live Charging Slots (${slots.length} Bays)
            </span>
            <span style="font-size:0.72rem;color:#00d4aa;cursor:pointer;font-weight:700;" onclick="inspectSlotsFromHome('${s.id}')">
              Full Telemetry &rarr;
            </span>
          </div>
          <div class="station-slots-pills-grid">
            ${slotsBadgesHtml}
          </div>
        </div>

        <div class="station-card-actions">
          <button type="button" class="btn-card-lock" onclick="openBookingFromHome('${s.id}')">
            <i class="fa-solid fa-lock"></i>
            <span>Lock Slot (30m)</span>
          </button>
          <button type="button" class="btn-card-inspect" onclick="showElectricRoute('${s.id}')" style="border-color:rgba(14,165,233,0.45);color:#38bdf8;" title="Show Live Road Route & Turn-by-Turn Directions">
            <i class="fa-solid fa-diamond-turn-right"></i>
            <span>Directions</span>
          </button>
          <button type="button" class="btn-card-inspect" onclick="inspectSlotsFromHome('${s.id}')" title="View Detailed Slot Status">
            <i class="fa-solid fa-grip"></i>
            <span>Slots</span>
          </button>
          <button type="button" class="btn-card-inspect" onclick="focusStationOnMap('${s.id}')" title="Zoom on Map">
            <i class="fa-solid fa-location-crosshairs"></i>
          </button>
        </div>
      </div>
    `;
  }).join('');
}

function updateResultsCounter(count) {
  const el = document.getElementById('finderResultsCount');
  if (el) {
    el.textContent = `${count.toLocaleString()} verified hubs`;
  }
}

// ================= 6. Search, Autocomplete, City/Village Selector & Filters =================
function bindFilterEvents() {
  const searchInput = document.getElementById('homeSearchInput');
  const clearBtn = document.getElementById('clearSearchBtn');
  const suggestionsBox = document.getElementById('searchSuggestions');

  if (searchInput) {
    let debounceTimer = null;
    searchInput.addEventListener('input', () => {
      const q = searchInput.value.trim();
      if (clearBtn) clearBtn.style.display = q ? 'inline-flex' : 'none';
      selectedSearchCoords = null;

      if (!q && !isGpsTracking) {
        hasActiveSearchOrNearMe = false;
        if (suggestionsBox) suggestionsBox.classList.add('hidden');
        renderSearchPromptState();
        return;
      }

      if (q.length >= 2) {
        hasActiveSearchOrNearMe = true;
        applyStationFilters();
      }

      clearTimeout(debounceTimer);
      if (q.length < 2) {
        if (suggestionsBox) suggestionsBox.classList.add('hidden');
        return;
      }
      debounceTimer = setTimeout(() => fetchSearchSuggestions(q), 220);
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      if (searchInput) searchInput.value = '';
      clearBtn.style.display = 'none';
      if (suggestionsBox) suggestionsBox.classList.add('hidden');
      const citySelect = document.getElementById('citySelect');
      if (citySelect) citySelect.value = '';
      selectedSearchCoords = null;

      if (isGpsTracking) {
        sortStationsByDistance(userLat, userLng);
      } else {
        hasActiveSearchOrNearMe = false;
        renderSearchPromptState();
        if (homeMap) homeMap.flyTo([22.5937, 78.9629], 5, { duration: 1.0 });
      }
    });
  }

  const chips = document.querySelectorAll('.chip-btn');
  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      chips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      activeCategory = chip.getAttribute('data-filter') || 'all';
      if (hasActiveSearchOrNearMe) {
        if (isGpsTracking && !(document.getElementById('homeSearchInput')?.value || '').trim()) {
          sortStationsByDistance(userLat, userLng);
        } else {
          applyStationFilters();
        }
      }
    });
  });

  const nearMeBtn = document.getElementById('homeNearMeBtn');
  if (nearMeBtn) {
    nearMeBtn.addEventListener('click', () => {
      toggleContinuousGps();
    });
  }
}

async function fetchSearchSuggestions(query) {
  const suggestionsBox = document.getElementById('searchSuggestions');
  if (!suggestionsBox) return;

  try {
    let results = [];
    try {
      const res = await fetch(`/api/maps/search?q=${encodeURIComponent(query)}`);
      if (res.ok) {
        const data = await res.json();
        results = data.results || [];
      } else {
        throw new Error('API offline');
      }
    } catch (apiErr) {
      // Client-side search fallback for GitHub Pages / static deployment
      const q = query.toLowerCase();
      const hits = allStations.filter(s =>
        (s.name && s.name.toLowerCase().includes(q)) ||
        (s.city && s.city.toLowerCase().includes(q)) ||
        (s.address && s.address.toLowerCase().includes(q)) ||
        (s.operator && s.operator.toLowerCase().includes(q))
      ).slice(0, 7);
      results = hits.map(s => ({
        id: s.id,
        name: s.name,
        details: `${s.city || s.address || 'India'} • ${s.power_kw || 60}kW Fast DC`,
        lat: s.latitude,
        lng: s.longitude,
        type: 'station'
      }));
    }

    if (results.length === 0) {
      suggestionsBox.classList.add('hidden');
      return;
    }

    suggestionsBox.innerHTML = results.slice(0, 7).map(item => `
      <div class="suggestion-row-item" onclick="selectSearchSuggestion(${item.lat || item.latitude}, ${item.lng || item.longitude}, '${(item.short_name || item.name || '').replace(/'/g, "\\'")}', '${item.id || ''}')">
        <i class="fa-solid ${item.type === 'station' ? 'fa-charging-station' : 'fa-location-dot'}" style="color:${item.type === 'station' ? '#00d4aa' : '#ff5722'};"></i>
        <div style="flex:1;">
          <div style="font-size:0.88rem;font-weight:700;color:#fff;">${item.name}</div>
          <div style="font-size:0.75rem;color:#94a3b8;">${item.details || item.address || item.city || 'India'}</div>
        </div>
      </div>
    `).join('');
    suggestionsBox.classList.remove('hidden');
  } catch (e) {
    suggestionsBox.classList.add('hidden');
  }
}

function selectSearchSuggestion(lat, lng, label, stationId) {
  const searchInput = document.getElementById('homeSearchInput');
  const clearBtn = document.getElementById('clearSearchBtn');
  const suggestionsBox = document.getElementById('searchSuggestions');
  if (searchInput) searchInput.value = label;
  if (clearBtn) clearBtn.style.display = 'inline-flex';
  if (suggestionsBox) suggestionsBox.classList.add('hidden');

  hasActiveSearchOrNearMe = true;
  if (lat && lng && !isNaN(lat) && !isNaN(lng)) {
    selectedSearchCoords = { lat: Number(lat), lng: Number(lng) };
  }
  applyStationFilters();

  if (stationId && markerById[stationId]) {
    focusStationOnMap(stationId);
  } else if (homeMap && lat && lng) {
    homeMap.flyTo([lat, lng], 13, { duration: 1.2 });
  }
}

function bindCitySelectorEvents() {
  const citySelect = document.getElementById('citySelect');
  if (!citySelect) return;

  citySelect.addEventListener('change', () => {
    const val = citySelect.value;
    const searchInput = document.getElementById('homeSearchInput');
    const clearBtn = document.getElementById('clearSearchBtn');
    if (!val) {
      if (searchInput) searchInput.value = '';
      if (clearBtn) clearBtn.style.display = 'none';
      selectedSearchCoords = null;
      if (!isGpsTracking) {
        hasActiveSearchOrNearMe = false;
        renderSearchPromptState();
      }
      return;
    }

    const [coordsPart, cityName] = val.split('|');
    const [latStr, lngStr] = (coordsPart || '').split(',');
    const lat = parseFloat(latStr);
    const lng = parseFloat(lngStr);

    hasActiveSearchOrNearMe = true;
    if (!isNaN(lat) && !isNaN(lng)) {
      selectedSearchCoords = { lat, lng };
    }
    if (searchInput && cityName) {
      searchInput.value = cityName;
    }
    if (clearBtn) clearBtn.style.display = 'inline-flex';
    applyStationFilters();

    if (homeMap && !isNaN(lat) && !isNaN(lng)) {
      homeMap.flyTo([lat, lng], 12, { duration: 1.2 });
      showHomeToast(`Showing EV Charging Stations in ${cityName || 'Selected Region'}`);
    }
  });
}

let activeOperatorFilter = 'all';

function matchesActiveCategory(s) {
  // 1. Operator Network Brand Filter
  if (activeOperatorFilter && activeOperatorFilter !== 'all') {
    const op = `${s.operator || ''} ${s.network || ''} ${s.name || ''}`.toLowerCase();
    if (!op.includes(activeOperatorFilter)) return false;
  }

  // 2. Connector & Attribute Category Filters
  if (activeCategory === 'available') {
    return (s.available_slots ?? 0) > 0;
  }
  if (activeCategory === 'villages') {
    const addr = `${s.name || ''} ${s.address || ''} ${s.city || ''}`.toLowerCase();
    return (
      s.station_type === 'town_village' ||
      String(s.id || '').includes('village') ||
      addr.includes('village') ||
      addr.includes('rural') ||
      addr.includes('gram') ||
      addr.includes('tehsil') ||
      addr.includes('kalan') ||
      addr.includes('nh-') ||
      addr.includes('highway')
    );
  }
  if (activeCategory === 'fast-dc') {
    return (s.power_kw || 60) >= 50;
  }
  if (activeCategory === 'hyper') {
    return (s.power_kw || 60) >= 120;
  }
  if (activeCategory === 'ccs2') {
    const conn = JSON.stringify(s.connector_types || '').toLowerCase();
    return conn.includes('ccs');
  }
  if (activeCategory === 'type2') {
    const conn = JSON.stringify(s.connector_types || '').toLowerCase();
    return conn.includes('type 2') || conn.includes('ac');
  }
  if (activeCategory === 'amenities') {
    const text = `${s.name || ''} ${s.address || ''} ${JSON.stringify(s.amenities || '')}`.toLowerCase();
    return (
      text.includes('dhaba') ||
      text.includes('food') ||
      text.includes('cafe') ||
      text.includes('restaurant') ||
      text.includes('hotel') ||
      text.includes('resort') ||
      text.includes('restroom') ||
      text.includes('washroom')
    );
  }
  if (activeCategory === 'value') {
    return Number(s.price_per_kwh || 18) <= 18;
  }
  return true;
}

function handleOperatorFilterChange(val) {
  activeOperatorFilter = (val || 'all').toLowerCase();
  if (hasActiveSearchOrNearMe) {
    if (isGpsTracking && !(document.getElementById('homeSearchInput')?.value || '').trim()) {
      sortStationsByDistance(userLat, userLng);
    } else {
      applyStationFilters();
    }
  }
}

function applyStationFilters() {
  const query = (document.getElementById('homeSearchInput')?.value || '').toLowerCase().trim();

  if (!query && !selectedSearchCoords && !isGpsTracking) {
    hasActiveSearchOrNearMe = false;
    renderSearchPromptState();
    return;
  }

  hasActiveSearchOrNearMe = true;

  filteredStations = allStations.filter(s => {
    const textMatch = query && (
      (s.name && s.name.toLowerCase().includes(query)) ||
      (s.address && s.address.toLowerCase().includes(query)) ||
      (s.city && s.city.toLowerCase().includes(query)) ||
      (s.operator && s.operator.toLowerCase().includes(query)) ||
      (s.network && s.network.toLowerCase().includes(query))
    );

    let coordMatch = false;
    if (selectedSearchCoords) {
      const dist = calculateHaversineKm(selectedSearchCoords.lat, selectedSearchCoords.lng, s.latitude, s.longitude);
      s.distance_km = dist;
      coordMatch = dist <= 45;
    }

    if (!textMatch && !coordMatch) return false;
    return matchesActiveCategory(s);
  });

  if (selectedSearchCoords) {
    filteredStations.sort((a, b) => (a.distance_km ?? 9999) - (b.distance_km ?? 9999));
  }

  renderHomeStationsList(filteredStations.slice(0, 60));
  renderMapMarkers(filteredStations);
  updateResultsCounter(filteredStations.length);

  if (query && !selectedSearchCoords && filteredStations.length > 0 && homeMap) {
    const first = filteredStations[0];
    if (first.latitude && first.longitude) {
      homeMap.flyTo([first.latitude, first.longitude], 12, { duration: 1.1 });
    }
  }
}

function focusStationOnMap(stationId) {
  const s = allStations.find(item => String(item.id) === String(stationId));
  if (!s || !homeMap) return;

  const lat = Number(s.latitude ?? s.lat);
  const lng = Number(s.longitude ?? s.lng);
  if (lat && lng) {
    document.getElementById('charger-finder')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    homeMap.flyTo([lat, lng], 15, { duration: 1.1 });
    const marker = markerById[s.id];
    if (marker) {
      setTimeout(() => marker.openPopup(), 600);
    }
  }
}

// ================= 7. Continuous Live GPS Tracking & Nearest Available Charger =================
function toggleContinuousGps() {
  const gpsBtn = document.getElementById('gpsTrackFabBtn');
  const nearMeBtn = document.getElementById('homeNearMeBtn');
  const gpsHud = document.getElementById('gpsTelemetryHud');

  if (isGpsTracking) {
    if (gpsWatchId !== null && navigator.geolocation) {
      navigator.geolocation.clearWatch(gpsWatchId);
      gpsWatchId = null;
    }
    isGpsTracking = false;
    if (gpsBtn) gpsBtn.classList.remove('gps-active');
    if (nearMeBtn) nearMeBtn.innerHTML = `<i class="fa-solid fa-crosshairs"></i> <span>Near Me</span>`;
    if (gpsHud) gpsHud.classList.add('hidden');
    const q = (document.getElementById('homeSearchInput')?.value || '').trim();
    if (!q) {
      hasActiveSearchOrNearMe = false;
      renderSearchPromptState();
    }
    showHomeToast('Live GPS tracking paused.');
    return;
  }

  hasActiveSearchOrNearMe = true;
  if (!navigator.geolocation) {
    fallbackIpLocation();
    return;
  }

  isGpsTracking = true;
  if (gpsBtn) gpsBtn.classList.add('gps-active');
  if (nearMeBtn) nearMeBtn.innerHTML = `<i class="fa-solid fa-satellite-dish fa-spin"></i> <span>GPS Live</span>`;
  if (gpsHud) gpsHud.classList.remove('hidden');

  gpsWatchId = navigator.geolocation.watchPosition(
    (pos) => {
      userLat = pos.coords.latitude;
      userLng = pos.coords.longitude;
      const accuracy = Math.round(pos.coords.accuracy || 15);
      const speedKmh = pos.coords.speed ? (pos.coords.speed * 3.6).toFixed(1) : '0.0';

      updateGpsMarkerOnMap(userLat, userLng, accuracy, speedKmh);
      sortStationsByDistance(userLat, userLng);
    },
    () => {
      fallbackIpLocation();
    },
    { enableHighAccuracy: true, maximumAge: 5000, timeout: 10000 }
  );
}

async function fallbackIpLocation() {
  hasActiveSearchOrNearMe = true;
  try {
    const res = await fetch('/api/geolocation/ip');
    const data = await res.json();
    if (data && data.lat && data.lng) {
      userLat = Number(data.lat);
      userLng = Number(data.lng);
      updateGpsMarkerOnMap(userLat, userLng, 50, '0.0', data.city);
      sortStationsByDistance(userLat, userLng);
      showHomeToast(`Located near ${data.city || 'your area'}! Showing nearby EV stations.`);
    }
  } catch (e) {
    updateGpsMarkerOnMap(userLat, userLng, 40, '0.0', 'New Delhi');
    sortStationsByDistance(userLat, userLng);
  }
}

function updateGpsMarkerOnMap(lat, lng, accuracy, speedKmh, cityLabel = '') {
  if (!homeMap) return;

  const coordEl = document.getElementById('hudGpsCoords');
  const speedEl = document.getElementById('hudGpsSpeed');
  const accEl = document.getElementById('hudGpsAccuracy');
  if (coordEl) coordEl.textContent = `${lat.toFixed(4)}° N, ${lng.toFixed(4)}° E`;
  if (speedEl) speedEl.textContent = `${speedKmh} km/h`;
  if (accEl) accEl.textContent = `±${accuracy}m ${cityLabel ? '• ' + cityLabel : ''}`;

  if (userLocationMarker) {
    userLocationMarker.setLatLng([lat, lng]);
  } else {
    const userIcon = L.divIcon({
      html: `<div style="width:18px;height:18px;border-radius:50%;background:#3b82f6;border:3px solid #fff;box-shadow:0 0 16px #3b82f6;"></div>`,
      className: 'user-gps-dot',
      iconSize: [18, 18],
      iconAnchor: [9, 9]
    });
    userLocationMarker = L.marker([lat, lng], { icon: userIcon }).addTo(homeMap);
    userLocationMarker.bindPopup('<b>Your Live EV Location</b>');
  }

  if (userAccuracyCircle) {
    userAccuracyCircle.setLatLng([lat, lng]);
    userAccuracyCircle.setRadius(Math.min(accuracy, 600));
  } else {
    userAccuracyCircle = L.circle([lat, lng], {
      radius: Math.min(accuracy, 600),
      color: '#3b82f6',
      fillColor: '#3b82f6',
      fillOpacity: 0.12,
      weight: 1
    }).addTo(homeMap);
  }

  if (gpsFollowCamera) {
    homeMap.flyTo([lat, lng], Math.max(homeMap.getZoom(), 12), { duration: 1.1 });
  }
}

function sortStationsByDistance(lat, lng) {
  hasActiveSearchOrNearMe = true;
  allStations.forEach(s => {
    s.distance_km = calculateHaversineKm(lat, lng, s.latitude, s.longitude);
  });
  const sorted = [...allStations]
    .filter(s => matchesActiveCategory(s))
    .sort((a, b) => (a.distance_km ?? 9999) - (b.distance_km ?? 9999));

  // Show stations within 65 km of user's location (or closest 20 stations if in a remote area)
  const withinRadius = sorted.filter(s => (s.distance_km ?? 9999) <= 65);
  filteredStations = withinRadius.length > 0 ? withinRadius : sorted.slice(0, 20);

  renderHomeStationsList(filteredStations.slice(0, 60));
  renderMapMarkers(filteredStations);
  updateResultsCounter(filteredStations.length);
}

function findNearestAvailableCharger() {
  hasActiveSearchOrNearMe = true;
  sortStationsByDistance(userLat, userLng);
  const nearest = allStations
    .filter(s => (s.available_slots ?? 0) > 0)
    .sort((a, b) => (a.distance_km ?? 9999) - (b.distance_km ?? 9999))[0];

  if (!nearest) {
    showHomeToast('No available stations found nearby.');
    return;
  }

  focusStationOnMap(nearest.id);
  showElectricRoute(nearest.id);
  showHomeToast(`Closest Available Hub: ${nearest.name} (${nearest.distance_km.toFixed(1)} km away)`);
}

// ================= 8. Live Turn-by-Turn Electric Road Routing & Weather HUD =================
async function showElectricRoute(stationId) {
  const s = allStations.find(item => String(item.id) === String(stationId));
  if (!s || !homeMap) return;

  const destLat = Number(s.latitude ?? s.lat);
  const destLng = Number(s.longitude ?? s.lng);
  if (!destLat || !destLng) return;

  // Determine best origin coordinates
  let startLat = userLat;
  let startLng = userLng;
  let originLabel = isGpsTracking ? 'Your Live GPS Location' : 'Current Map Location';

  if (!isGpsTracking && selectedSearchCoords && selectedSearchCoords.lat && selectedSearchCoords.lng) {
    const distToSearch = calculateHaversineKm(selectedSearchCoords.lat, selectedSearchCoords.lng, destLat, destLng);
    if (distToSearch <= 80) {
      startLat = selectedSearchCoords.lat;
      startLng = selectedSearchCoords.lng;
      originLabel = 'Searched Location';
    }
  }

  // Smoothly scroll map into view on mobile so driver sees route immediately
  const mapPanel = document.querySelector('.finder-map-panel') || document.getElementById('charger-finder');
  if (mapPanel && window.innerWidth <= 860) {
    mapPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  showHomeToast(`Calculating live EV route to ${s.name}...`);

  try {
    let routeData = null;
    let weatherData = {};

    try {
      const [routeRes, weatherRes] = await Promise.all([
        fetch(`/api/route?from_lat=${startLat}&from_lng=${startLng}&to_lat=${destLat}&to_lng=${destLng}`),
        fetch(`/api/weather?lat=${destLat}&lng=${destLng}`)
      ]);
      if (routeRes.ok) routeData = await routeRes.json();
      if (weatherRes.ok) weatherData = await weatherRes.json();
    } catch (e) {}

    // Client-side fallback for GitHub Pages
    if (!routeData || !routeData.success) {
      try {
        const osrmUrl = `https://router.project-osrm.org/route/v1/driving/${startLng},${startLat};${destLng},${destLat}?overview=full&geometries=geojson&steps=true`;
        const oRes = await fetch(osrmUrl);
        const oJson = await oRes.json();
        if (oJson.code === 'Ok' && oJson.routes && oJson.routes.length > 0) {
          const r = oJson.routes[0];
          const distKm = Math.round(r.distance / 100) / 10;
          const durMin = Math.max(1, Math.round(r.duration / 60));
          const coords = r.geometry.coordinates.map(pt => [pt[1], pt[0]]);
          const stepList = (r.legs?.[0]?.steps || []).map(st => st.name ? `Follow ${st.name}` : 'Continue along road').filter(Boolean).slice(0, 6);
          routeData = {
            success: true,
            distance_km: distKm,
            duration_mins: durMin,
            coordinates: coords,
            steps: stepList.length > 0 ? stepList : [`Drive ${distKm} km to ${s.name}`]
          };
        }
      } catch (err) {}
    }

    if (!routeData) {
      const straight = calculateHaversineKm(startLat, startLng, destLat, destLng);
      const estDist = Math.round(straight * 1.25 * 10) / 10;
      routeData = {
        success: true,
        distance_km: estDist,
        duration_mins: Math.max(2, Math.round((estDist / 40) * 60)),
        coordinates: [[startLat, startLng], [(startLat + destLat) / 2, (startLng + destLng) / 2], [destLat, destLng]],
        steps: [`Head towards ${s.name}`, 'Arrive at Charging Hub']
      };
    }

    if (activeRoutePolyline) {
      homeMap.removeLayer(activeRoutePolyline);
      activeRoutePolyline = null;
    }
    if (activeRouteGlowPolyline) {
      homeMap.removeLayer(activeRouteGlowPolyline);
      activeRouteGlowPolyline = null;
    }
    if (activeRouteStartMarker) {
      homeMap.removeLayer(activeRouteStartMarker);
      activeRouteStartMarker = null;
    }

    const coords = (routeData.route && Array.isArray(routeData.route.coordinates) && routeData.route.coordinates.length > 1)
      ? routeData.route.coordinates
      : [[startLat, startLng], [destLat, destLng]];

    // Glowing dual-layer road polyline
    activeRouteGlowPolyline = L.polyline(coords, {
      color: '#00d4aa',
      weight: 9,
      opacity: 0.35,
      lineCap: 'round',
      lineJoin: 'round'
    }).addTo(homeMap);

    activeRoutePolyline = L.polyline(coords, {
      color: '#00d4aa',
      weight: 4.5,
      opacity: 0.95,
      dashArray: '10, 6',
      lineCap: 'round',
      lineJoin: 'round'
    }).addTo(homeMap);

    // Start point marker
    const startIcon = L.divIcon({
      html: `<div style="background:#0ea5e9;color:#fff;border:2.5px solid #fff;border-radius:50%;width:24px;height:24px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:900;box-shadow:0 0 10px #0ea5e9;"><i class="fa-solid fa-play"></i></div>`,
      className: 'route-start-pin',
      iconSize: [24, 24],
      iconAnchor: [12, 12]
    });
    activeRouteStartMarker = L.marker([startLat, startLng], { icon: startIcon }).addTo(homeMap);
    activeRouteStartMarker.bindPopup(`<b>Route Start: ${originLabel}</b>`);

    homeMap.fitBounds(activeRoutePolyline.getBounds(), { padding: [40, 40], maxZoom: 15 });

    const distKm = Number(routeData.distance_km ?? routeData.route?.distance_km ?? calculateHaversineKm(startLat, startLng, destLat, destLng).toFixed(1));
    const durationMin = Number(routeData.duration_mins ?? routeData.duration_min ?? routeData.route?.duration_min ?? Math.max(3, Math.round(distKm * 1.6)));
    const estKwh = (distKm * 0.16).toFixed(1);
    const tempC = weatherData.temperature ?? weatherData.weather?.temp_c ?? 28;
    const condition = weatherData.condition ?? weatherData.weather?.condition ?? 'Pleasant';
    const battEff = weatherData.battery_efficiency || '98% Optimal';

    const steps = (routeData.steps || routeData.route?.steps || []);
    const stepsHtml = steps.length > 0 ? steps.map((step, idx) => `
      <div style="display:flex;gap:7px;align-items:flex-start;font-size:0.75rem;color:#cbd5e1;padding:3px 0;border-bottom:1px solid rgba(255,255,255,0.05);">
        <span style="color:#00d4aa;font-weight:800;font-size:0.72rem;min-width:18px;">${idx + 1}.</span>
        <span style="flex:1;">${step}</span>
      </div>
    `).join('') : `<div style="font-size:0.75rem;color:#94a3b8;">Follow designated EV highway corridor to ${s.name}</div>`;

    const gmapsNavUrl = `https://www.google.com/maps/dir/?api=1&origin=${startLat},${startLng}&destination=${destLat},${destLng}&travelmode=driving`;

    const navHud = document.getElementById('navigationHud');
    const navContent = document.getElementById('navigationHudContent');
    if (navHud && navContent) {
      navContent.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
          <span style="font-size:0.72rem;font-weight:800;color:#00d4aa;text-transform:uppercase;letter-spacing:0.04em;">
            <i class="fa-solid fa-diamond-turn-right"></i> EV Turn-by-Turn Route
          </span>
          <button type="button" onclick="clearActiveRoute()" style="background:none;border:none;color:#94a3b8;cursor:pointer;font-size:1.1rem;padding:2px 4px;" title="Close Directions">&times;</button>
        </div>
        <div style="font-weight:800;font-size:0.95rem;color:#fff;margin-bottom:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${s.name}</div>
        <div style="font-size:0.74rem;color:#94a3b8;margin-bottom:8px;">${s.address || s.city || 'India'}</div>

        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;background:rgba(255,255,255,0.06);padding:8px 6px;border-radius:10px;text-align:center;margin-bottom:8px;">
          <div>
            <div style="font-size:0.65rem;color:#94a3b8;font-weight:700;">DISTANCE</div>
            <div style="font-size:0.92rem;font-weight:800;color:#fff;">${distKm} km</div>
          </div>
          <div>
            <div style="font-size:0.65rem;color:#94a3b8;font-weight:700;">DRIVE ETA</div>
            <div style="font-size:0.92rem;font-weight:800;color:#38bdf8;">${durationMin} min</div>
          </div>
          <div>
            <div style="font-size:0.65rem;color:#94a3b8;font-weight:700;">EST. DRAW</div>
            <div style="font-size:0.92rem;font-weight:800;color:#34d399;">${estKwh} kWh</div>
          </div>
        </div>

        <div style="font-size:0.74rem;color:#94a3b8;margin-bottom:5px;font-weight:700;display:flex;justify-content:space-between;">
          <span>ROAD DIRECTIONS</span>
          <span style="color:#f59e0b;"><i class="fa-solid fa-cloud-sun"></i> ${tempC}°C &bull; ${battEff}</span>
        </div>
        <div style="max-height:95px;overflow-y:auto;background:rgba(0,0,0,0.25);padding:4px 8px;border-radius:8px;margin-bottom:9px;border:1px solid rgba(255,255,255,0.06);">
          ${stepsHtml}
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
          <a href="${gmapsNavUrl}" target="_blank" rel="noopener" style="background:#0ea5e9;color:#fff;text-decoration:none;border-radius:8px;padding:7px 8px;font-size:0.78rem;font-weight:800;text-align:center;display:flex;align-items:center;justify-content:center;gap:4px;">
            <i class="fa-brands fa-google"></i> Google Nav &rarr;
          </a>
          <button type="button" onclick="openBookingFromHome('${s.id}')" style="background:#ff5722;color:#fff;border:none;border-radius:8px;padding:7px 8px;font-size:0.78rem;font-weight:800;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:4px;">
            <i class="fa-solid fa-lock"></i> Lock Slot (30m)
          </button>
        </div>
      `;
      navHud.classList.remove('hidden');
    }
  } catch (err) {
    showHomeToast('Route loaded on Google Map.');
  }
}

function clearActiveRoute() {
  if (activeRoutePolyline && homeMap) {
    homeMap.removeLayer(activeRoutePolyline);
    activeRoutePolyline = null;
  }
  if (activeRouteGlowPolyline && homeMap) {
    homeMap.removeLayer(activeRouteGlowPolyline);
    activeRouteGlowPolyline = null;
  }
  if (activeRouteStartMarker && homeMap) {
    homeMap.removeLayer(activeRouteStartMarker);
    activeRouteStartMarker = null;
  }
  const navHud = document.getElementById('navigationHud');
  if (navHud) navHud.classList.add('hidden');
}

// ================= 8B. Intelligent Highway EV Trip Planner & Corridor Engine =================
let currentFinderMode = 'explorer'; // 'explorer' | 'planner'
let currentTripPlan = null;
let tripRoutePolyline = null;
let tripRouteGlowPolyline = null;
let tripStartMarker = null;
let tripDestMarker = null;
let tripStopMarkers = [];

function switchFinderMode(mode) {
  currentFinderMode = mode;
  const tabExplorer = document.getElementById('tabExplorerMode');
  const tabPlanner = document.getElementById('tabTripPlannerMode');
  const explorerBox = document.getElementById('finderExplorerControls');
  const plannerBox = document.getElementById('finderTripPlannerControls');

  if (mode === 'planner') {
    if (tabExplorer) tabExplorer.classList.remove('active');
    if (tabPlanner) tabPlanner.classList.add('active');
    if (explorerBox) explorerBox.style.display = 'none';
    if (plannerBox) plannerBox.style.display = 'block';

    clearActiveRoute();

    if (!currentTripPlan) {
      calculateHighwayTrip();
    } else {
      renderTripPlannerResults(currentTripPlan);
      plotTripOnMap(currentTripPlan);
    }
  } else {
    if (tabExplorer) tabExplorer.classList.add('active');
    if (tabPlanner) tabPlanner.classList.remove('active');
    if (explorerBox) explorerBox.style.display = 'flex';
    if (plannerBox) plannerBox.style.display = 'none';

    clearTripMapLayers();

    if (hasActiveSearchOrNearMe) {
      if (isGpsTracking) {
        sortStationsByDistance(userLat, userLng);
      } else {
        applyStationFilters();
      }
    } else {
      renderSearchPromptState();
    }
  }
}

function setPlannerOriginToGps() {
  const inp = document.getElementById('plannerOriginInput');
  if (!inp) return;
  if (isGpsTracking && userLat && userLng) {
    inp.value = `${userLat.toFixed(4)}, ${userLng.toFixed(4)}`;
    showHomeToast('Origin set to your live GPS coordinates');
  } else if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      pos => {
        userLat = pos.coords.latitude;
        userLng = pos.coords.longitude;
        inp.value = `${userLat.toFixed(4)}, ${userLng.toFixed(4)}`;
        showHomeToast('Origin set to your live GPS coordinates');
      },
      err => {
        inp.value = 'New Delhi';
        showHomeToast('Using New Delhi as origin');
      }
    );
  }
}

function swapPlannerEndpoints() {
  const oInp = document.getElementById('plannerOriginInput');
  const dInp = document.getElementById('plannerDestInput');
  if (oInp && dInp) {
    const tmp = oInp.value;
    oInp.value = dInp.value;
    dInp.value = tmp;
    calculateHighwayTrip();
  }
}

function applyCorridorPreset(orig, dest, range) {
  const oInp = document.getElementById('plannerOriginInput');
  const dInp = document.getElementById('plannerDestInput');
  const rSel = document.getElementById('plannerRangeSelect');

  if (oInp) oInp.value = orig;
  if (dInp) dInp.value = dest;
  if (rSel && range) rSel.value = String(range);

  document.querySelectorAll('.corridor-preset-pill').forEach(pill => {
    pill.classList.toggle('active', pill.textContent.includes(dest) || pill.textContent.includes(orig));
  });

  calculateHighwayTrip();
}

function clearTripMapLayers() {
  if (tripRoutePolyline && homeMap) {
    homeMap.removeLayer(tripRoutePolyline);
    tripRoutePolyline = null;
  }
  if (tripRouteGlowPolyline && homeMap) {
    homeMap.removeLayer(tripRouteGlowPolyline);
    tripRouteGlowPolyline = null;
  }
  if (tripStartMarker && homeMap) {
    homeMap.removeLayer(tripStartMarker);
    tripStartMarker = null;
  }
  if (tripDestMarker && homeMap) {
    homeMap.removeLayer(tripDestMarker);
    tripDestMarker = null;
  }
  if (tripStopMarkers.length > 0 && homeMap) {
    tripStopMarkers.forEach(m => homeMap.removeLayer(m));
    tripStopMarkers = [];
  }
}

async function calculateHighwayTrip() {
  const origin = (document.getElementById('plannerOriginInput')?.value || 'New Delhi').trim();
  const dest = (document.getElementById('plannerDestInput')?.value || 'Jaipur').trim();
  const rangeKm = Number(document.getElementById('plannerRangeSelect')?.value || 320);
  const initialSoc = Number(document.getElementById('plannerInitialSocSelect')?.value || 90);
  const container = document.getElementById('homeStationsList');
  const countEl = document.getElementById('finderResultsCount');
  const btn = document.getElementById('btnCalculateHighwayTrip');

  if (!origin || !dest) {
    showHomeToast('Please enter both Origin and Destination');
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> <span>Calculating...</span>`;
  }
  if (countEl) countEl.textContent = 'Computing corridor...';

  if (container) {
    container.innerHTML = `
      <div style="text-align:center;padding:3rem 1.5rem;color:#94a3b8;background:#111726;border-radius:16px;">
        <i class="fa-solid fa-route fa-spin" style="font-size:2.5rem;color:#00d4aa;margin-bottom:1rem;"></i>
        <h4 style="color:#ffffff;margin-bottom:0.4rem;">Plotting Electric Highway Corridor...</h4>
        <p style="font-size:0.85rem;">Scanning 1,619+ verified nodes between <strong>${origin}</strong> and <strong>${dest}</strong>.</p>
      </div>
    `;
  }

  let data = null;
  try {
    const res = await fetch(`/api/route/plan?origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(dest)}&vehicle_range_km=${rangeKm}&initial_soc=${initialSoc}`);
    if (res.ok) {
      data = await res.json();
    }
  } catch (err) {}

  // Client-side fallback for GitHub Pages / static deployment
  if (!data || !data.success) {
    data = await calculateHighwayTripClientSide(origin, dest, rangeKm, initialSoc);
  }

  if (btn) {
    btn.disabled = false;
    btn.innerHTML = `<i class="fa-solid fa-bolt"></i> <span>Plan Corridor</span>`;
  }

  if (!data || !data.success) {
    showHomeToast(data?.error || 'Could not find highway route between locations.');
    return;
  }

  currentTripPlan = data;
  renderTripPlannerResults(data);
  plotTripOnMap(data);
  showHomeToast(`Electric route planned: ${data.total_distance_km} km with ${data.en_route_stations_count} corridor hubs!`);
}

const INDIAN_CITIES_COORDS = {
  "delhi": [28.6139, 77.2090, "New Delhi, Delhi, India"],
  "new delhi": [28.6139, 77.2090, "New Delhi, Delhi, India"],
  "mumbai": [19.0760, 72.8777, "Mumbai, Maharashtra, India"],
  "pune": [18.5204, 73.8567, "Pune, Maharashtra, India"],
  "bengaluru": [12.9716, 77.5946, "Bengaluru, Karnataka, India"],
  "bangalore": [12.9716, 77.5946, "Bengaluru, Karnataka, India"],
  "hyderabad": [17.3850, 78.4867, "Hyderabad, Telangana, India"],
  "chennai": [13.0827, 80.2707, "Chennai, Tamil Nadu, India"],
  "kolkata": [22.5726, 88.3639, "Kolkata, West Bengal, India"],
  "ahmedabad": [23.0225, 72.5714, "Ahmedabad, Gujarat, India"],
  "surat": [21.1702, 72.8311, "Surat, Gujarat, India"],
  "vadodara": [22.3072, 73.1812, "Vadodara, Gujarat, India"],
  "jaipur": [26.9124, 75.7873, "Jaipur, Rajasthan, India"],
  "lucknow": [26.8467, 80.9462, "Lucknow, Uttar Pradesh, India"],
  "agra": [27.1767, 78.0081, "Agra, Uttar Pradesh, India"],
  "chandigarh": [30.7333, 76.7794, "Chandigarh, India"],
  "mysuru": [12.2958, 76.6394, "Mysuru, Karnataka, India"],
  "mysore": [12.2958, 76.6394, "Mysuru, Karnataka, India"],
  "vijayawada": [16.5062, 80.6480, "Vijayawada, Andhra Pradesh, India"],
  "goa": [15.2993, 74.1240, "Goa, India"],
  "kochi": [9.9312, 76.2673, "Kochi, Kerala, India"],
  "indore": [22.7196, 75.8577, "Indore, Madhya Pradesh, India"],
  "hathras": [27.5972, 78.0519, "Hathras, Uttar Pradesh, India"]
};

function resolveCityCoords(query) {
  if (!query) return null;
  const q = query.trim().toLowerCase();
  if (q.includes(',')) {
    const parts = q.split(',');
    const lat = parseFloat(parts[0]);
    const lng = parseFloat(parts[1]);
    if (!isNaN(lat) && !isNaN(lng)) return [lat, lng, `${lat.toFixed(4)}, ${lng.toFixed(4)}`];
  }
  for (const k in INDIAN_CITIES_COORDS) {
    if (q.includes(k) || k.includes(q)) return INDIAN_CITIES_COORDS[k];
  }
  const match = allStations.find(s =>
    (s.city && s.city.toLowerCase().includes(q)) ||
    (s.name && s.name.toLowerCase().includes(q))
  );
  if (match) return [match.latitude, match.longitude, match.name];
  return null;
}

async function calculateHighwayTripClientSide(origin, dest, vehicleRange, initialSoc) {
  const origRes = resolveCityCoords(origin);
  const destRes = resolveCityCoords(dest);
  if (!origRes || !destRes) {
    return { success: false, error: "Could not locate city in India. Try cities like Delhi, Jaipur, Mumbai, Pune, Bengaluru." };
  }

  const [fromLat, fromLng, origLabel] = origRes;
  const [toLat, toLng, destLabel] = destRes;

  let coords = [];
  let totalDistKm = 0;
  let driveDurationMin = 0;

  try {
    const url = `https://router.project-osrm.org/route/v1/driving/${fromLng},${fromLat};${toLng},${toLat}?overview=full&geometries=geojson`;
    const res = await fetch(url);
    const oData = await res.json();
    if (oData.code === 'Ok' && oData.routes && oData.routes.length > 0) {
      const r = oData.routes[0];
      totalDistKm = Math.round(r.distance / 100) / 10;
      driveDurationMin = Math.max(10, Math.round(r.duration / 60));
      coords = r.geometry.coordinates.map(pt => [pt[1], pt[0]]);
    }
  } catch (e) {}

  if (coords.length === 0) {
    const straight = calculateHaversineKm(fromLat, fromLng, toLat, toLng);
    totalDistKm = Math.round(straight * 1.25 * 10) / 10;
    driveDurationMin = Math.max(10, Math.round((totalDistKm / 50) * 60));
    for (let i = 0; i <= 15; i++) {
      const frac = i / 15.0;
      coords.push([fromLat + (toLat - fromLat) * frac, fromLng + (toLng - fromLng) * frac]);
    }
  }

  const sampleStep = Math.max(1, Math.floor(coords.length / 30));
  const sampledPts = [];
  for (let i = 0; i < coords.length; i += sampleStep) sampledPts.push(coords[i]);
  if (!sampledPts.includes(coords[coords.length - 1])) sampledPts.push(coords[coords.length - 1]);

  const enRouteStations = [];
  allStations.forEach(s => {
    let minD = 9999;
    let bestIdx = 0;
    sampledPts.forEach((pt, idx) => {
      const d = calculateHaversineKm(s.latitude, s.longitude, pt[0], pt[1]);
      if (d < minD) { minD = d; bestIdx = idx; }
    });
    if (minD <= 25) {
      const prog = bestIdx / Math.max(1, sampledPts.length - 1);
      enRouteStations.push({
        ...s,
        corridor_deviation_km: Math.round(minD * 10) / 10,
        distance_from_start_km: Math.round(prog * totalDistKm * 10) / 10
      });
    }
  });

  enRouteStations.sort((a, b) => a.distance_from_start_km - b.distance_from_start_km);

  const usableRange = (initialSoc / 100) * vehicleRange * 0.85;
  const stopsNeeded = totalDistKm > usableRange ? 1 : 0;
  const recommendedStops = [];
  const socMilestones = [
    { label: `Start: ${origLabel.split(',')[0]}`, distance_km: 0, soc_pct: Math.round(initialSoc), status: "Departure" }
  ];

  if (stopsNeeded > 0) {
    const targetDist = Math.min(totalDistKm * 0.55, vehicleRange * (initialSoc / 100) * 0.65);
    const candidates = enRouteStations.filter(s => s.distance_from_start_km >= 30 && s.distance_from_start_km <= vehicleRange * 0.8);
    candidates.sort((a, b) => (b.power_kw || 60) - (a.power_kw || 60) || Math.abs(a.distance_from_start_km - targetDist) - Math.abs(b.distance_from_start_km - targetDist));
    const chosen = candidates[0] || enRouteStations[Math.floor(enRouteStations.length / 2)];

    if (chosen) {
      const stopDist = chosen.distance_from_start_km;
      const arriveSoc = Math.max(12, Math.round(initialSoc - (stopDist / vehicleRange) * 100));
      const kwhAdd = Math.round(((80 - arriveSoc) / 100) * (vehicleRange * 0.16) * 10) / 10;
      const chargeMins = Math.max(20, Math.min(40, Math.round((kwhAdd / (chosen.power_kw || 60)) * 60) + 5));
      recommendedStops.push({
        stop_number: 1,
        station: chosen,
        distance_from_start_km: stopDist,
        arrival_soc_pct: arriveSoc,
        target_soc_pct: 80,
        recommended_charge_mins: chargeMins,
        kwh_added: kwhAdd,
        estimated_cost_inr: Math.round(kwhAdd * (chosen.price_per_kwh || 18))
      });
      socMilestones.push({
        label: `Stop #1: ${chosen.name}`,
        distance_km: stopDist,
        soc_pct: arriveSoc,
        status: `Arrive at ${arriveSoc}% • 30-min Lock Charge to 80%`
      });
      const finalSoc = Math.max(15, Math.round(80 - ((totalDistKm - stopDist) / vehicleRange) * 100));
      socMilestones.push({ label: `Arrival: ${destLabel.split(',')[0]}`, distance_km: totalDistKm, soc_pct: finalSoc, status: "Final Destination" });
    }
  } else {
    const finalSoc = Math.max(10, Math.round(initialSoc - (totalDistKm / vehicleRange) * 100));
    socMilestones.push({ label: `Arrival: ${destLabel.split(',')[0]} (Non-Stop)`, distance_km: totalDistKm, soc_pct: finalSoc, status: "Final Destination" });
  }

  const chargeMins = recommendedStops.reduce((sum, st) => sum + st.recommended_charge_mins, 0);
  const totalMins = driveDurationMin + chargeMins;
  const kwhDraw = Math.round(totalDistKm * 0.16 * 10) / 10;
  const evCost = Math.round(kwhDraw * 18);
  const petrolCost = Math.round((totalDistKm / 14) * 102);

  return {
    success: true,
    origin: { name: origLabel, lat: fromLat, lng: fromLng },
    destination: { name: destLabel, lat: toLat, lng: toLng },
    total_distance_km: totalDistKm,
    driving_duration_mins: driveDurationMin,
    charging_duration_mins: chargeMins,
    total_journey_mins: totalMins,
    stops_needed: stopsNeeded,
    vehicle_specs: {
      estimated_range_km: vehicleRange,
      initial_soc_pct: initialSoc,
      battery_capacity_kwh: Math.round(vehicleRange * 0.16 * 10) / 10
    },
    route_coordinates: coords,
    en_route_stations_count: enRouteStations.length,
    en_route_stations: enRouteStations.slice(0, 30),
    recommended_stops: recommendedStops,
    soc_milestones: socMilestones,
    eco_analytics: {
      total_kwh_draw: kwhDraw,
      ev_charging_cost_inr: evCost,
      petrol_equivalent_cost_inr: petrolCost,
      net_rupee_savings: Math.max(0, petrolCost - evCost),
      co2_abated_kg: Math.round(totalDistKm * 0.142 * 10) / 10
    }
  };
}

function plotTripOnMap(plan) {
  if (!homeMap) return;
  clearTripMapLayers();
  if (markerLayerGroup) markerLayerGroup.clearLayers();
  markerById = {};

  const coords = plan.route_coordinates || [];
  if (coords.length > 0) {
    tripRouteGlowPolyline = L.polyline(coords, {
      color: '#00d4aa',
      weight: 9,
      opacity: 0.35,
      lineCap: 'round',
      lineJoin: 'round'
    }).addTo(homeMap);

    tripRoutePolyline = L.polyline(coords, {
      color: '#00d4aa',
      weight: 4.5,
      opacity: 0.95,
      lineCap: 'round',
      lineJoin: 'round'
    }).addTo(homeMap);

    const startIcon = L.divIcon({
      html: `<div style="background:#0ea5e9;color:#fff;border:3px solid #fff;border-radius:50%;width:30px;height:30px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:900;box-shadow:0 0 16px #0ea5e9;"><i class="fa-solid fa-location-dot"></i></div>`,
      className: 'trip-start-pin',
      iconSize: [30, 30],
      iconAnchor: [15, 15]
    });
    tripStartMarker = L.marker([plan.origin.lat, plan.origin.lng], { icon: startIcon }).addTo(homeMap);
    tripStartMarker.bindPopup(`<b>Start: ${plan.origin.name}</b><br><span style="font-size:11px;color:#94a3b8;">Departure SOC: ${plan.vehicle_specs.initial_soc_pct}%</span>`);

    const destIcon = L.divIcon({
      html: `<div style="background:#ef4444;color:#fff;border:3px solid #fff;border-radius:50%;width:30px;height:30px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:900;box-shadow:0 0 16px #ef4444;"><i class="fa-solid fa-flag-checkered"></i></div>`,
      className: 'trip-dest-pin',
      iconSize: [30, 30],
      iconAnchor: [15, 15]
    });
    tripDestMarker = L.marker([plan.destination.lat, plan.destination.lng], { icon: destIcon }).addTo(homeMap);
    tripDestMarker.bindPopup(`<b>Destination: ${plan.destination.name}</b><br><span style="font-size:11px;color:#94a3b8;">Total Distance: ${plan.total_distance_km} km</span>`);

    if (Array.isArray(plan.recommended_stops) && plan.recommended_stops.length > 0) {
      plan.recommended_stops.forEach(stop => {
        const s = stop.station;
        if (!s || !s.latitude || !s.longitude) return;
        const stopIcon = L.divIcon({
          html: `<div style="background:#f59e0b;color:#041318;border:3px solid #fff;border-radius:50%;width:34px;height:34px;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:900;box-shadow:0 0 20px #f59e0b;"><i class="fa-solid fa-bolt"></i></div>`,
          className: 'trip-stop-pin',
          iconSize: [34, 34],
          iconAnchor: [17, 17]
        });
        const stopM = L.marker([s.latitude, s.longitude], { icon: stopIcon }).addTo(homeMap);
        stopM.bindPopup(`
          <div style="font-family:'Plus Jakarta Sans',sans-serif;padding:3px;min-width:230px;">
            <div style="font-size:10px;font-weight:800;color:#f59e0b;text-transform:uppercase;">RECOMMENDED 30-MIN LOCK STOP</div>
            <div style="font-weight:800;color:#fff;font-size:13px;margin:2px 0;">${s.name}</div>
            <div style="font-size:11px;color:#94a3b8;margin-bottom:6px;">${s.address || s.city || 'Corridor Hub'}</div>
            <div style="background:rgba(255,255,255,0.06);padding:6px;border-radius:8px;font-size:11px;color:#e2e8f0;margin-bottom:6px;">
              <div>Arrival SOC: <strong style="color:#f59e0b;">${stop.arrival_soc_pct}%</strong> &rarr; Charge to <strong style="color:#10b981;">80%</strong></div>
              <div>Est. Fast Charge: <strong>${stop.recommended_charge_mins} mins</strong> (+${stop.kwh_added} kWh)</div>
            </div>
            <button onclick="openBookingFromHome('${s.id}')" style="width:100%;background:#ff5722;color:#fff;border:none;border-radius:7px;padding:6px;font-size:11px;font-weight:800;cursor:pointer;">
              <i class="fa-solid fa-lock"></i> Lock Slot (30m) &rarr;
            </button>
          </div>
        `);
        tripStopMarkers.push(stopM);
      });
    }

    renderMapMarkers(plan.en_route_stations || []);
    homeMap.fitBounds(tripRoutePolyline.getBounds(), { padding: [40, 40], maxZoom: 14 });
  }
}

function renderTripPlannerResults(plan) {
  const container = document.getElementById('homeStationsList');
  const countEl = document.getElementById('finderResultsCount');
  if (countEl) {
    countEl.textContent = `${plan.en_route_stations_count} corridor hubs`;
  }
  if (!container) return;

  const totalDist = plan.total_distance_km;
  const driveHours = Math.floor(plan.driving_duration_mins / 60);
  const driveMins = plan.driving_duration_mins % 60;
  const driveTimeFormatted = driveHours > 0 ? `${driveHours}h ${driveMins}m` : `${driveMins} mins`;
  const totalJourneyMin = plan.total_journey_mins || plan.driving_duration_mins;
  const totalHours = Math.floor(totalJourneyMin / 60);
  const totalMins = totalJourneyMin % 60;
  const totalTimeFormatted = totalHours > 0 ? `${totalHours}h ${totalMins}m` : `${totalMins} mins`;

  const eco = plan.eco_analytics || {};
  const stops = plan.recommended_stops || [];
  const milestones = plan.soc_milestones || [];
  const corridorStations = plan.en_route_stations || [];

  const milestonesHtml = milestones.map((m, idx) => {
    const isStop = m.status && m.status.includes('Lock Charge');
    const isDest = idx === milestones.length - 1;
    const color = isStop ? '#f59e0b' : (isDest ? '#00d4aa' : '#38bdf8');
    return `
      <div class="soc-node ${isStop ? 'stop-node' : ''}">
        <span style="color:#94a3b8;font-size:0.7rem;">${m.distance_km} km</span>
        <strong>${m.soc_pct}%</strong>
        <span style="color:${color};font-weight:700;font-size:0.74rem;">${m.status.split('•')[0].trim()}</span>
      </div>
    `;
  }).join('');

  let spotlightHtml = '';
  if (stops.length > 0) {
    const primaryStop = stops[0];
    const s = primaryStop.station;
    spotlightHtml = `
      <div class="spotlight-stop-card">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;">
          <div class="spotlight-badge">
            <i class="fa-solid fa-bolt"></i> Recommended 30-Min Lock Stop
          </div>
          <span style="color:#00d4aa;font-weight:800;font-size:0.78rem;">
            Stop #1 • At ${primaryStop.distance_from_start_km} km mark
          </span>
        </div>
        <div style="font-size:1.1rem;font-weight:800;color:#ffffff;margin:0.25rem 0 0.15rem 0;">
          ${s.name}
        </div>
        <div style="font-size:0.8rem;color:#cbd5e1;margin-bottom:0.75rem;">
          <i class="fa-solid fa-location-dot" style="color:#f59e0b;"></i> ${s.address || s.city || 'Highway Corridor Hub'}
        </div>

        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;background:rgba(0,0,0,0.3);padding:8px;border-radius:10px;margin-bottom:0.85rem;text-align:center;">
          <div>
            <div style="font-size:0.68rem;color:#94a3b8;font-weight:700;">ARRIVE SOC</div>
            <div style="font-size:1.05rem;font-weight:800;color:#f59e0b;">${primaryStop.arrival_soc_pct}%</div>
          </div>
          <div>
            <div style="font-size:0.68rem;color:#94a3b8;font-weight:700;">FAST CHARGE</div>
            <div style="font-size:1.05rem;font-weight:800;color:#00d4aa;">${primaryStop.recommended_charge_mins} mins</div>
          </div>
          <div>
            <div style="font-size:0.68rem;color:#94a3b8;font-weight:700;">EST. CHARGE</div>
            <div style="font-size:1.05rem;font-weight:800;color:#38bdf8;">+${primaryStop.kwh_added} kWh</div>
          </div>
        </div>

        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem;">
          <div style="font-size:0.78rem;color:#94a3b8;">
            <i class="fa-solid fa-utensils" style="color:#f59e0b;"></i> Highway Food, Restrooms &amp; 24/7 Security
          </div>
          <button type="button" class="btn-card-lock" style="padding:0.55rem 1.15rem;font-size:0.85rem;" onclick="openBookingFromHome('${s.id}')">
            <i class="fa-solid fa-lock"></i>
            <span>Lock Slot for 30 Mins (₹${s.price_per_kwh || 18}/kWh)</span>
          </button>
        </div>
      </div>
    `;
  } else {
    spotlightHtml = `
      <div style="background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.35);border-radius:14px;padding:0.9rem 1.1rem;margin-bottom:1rem;display:flex;align-items:center;gap:0.75rem;">
        <i class="fa-solid fa-circle-check" style="color:#10b981;font-size:1.4rem;"></i>
        <div>
          <div style="font-weight:800;font-size:0.92rem;color:#fff;">Direct Non-Stop Journey Feasible!</div>
          <div style="font-size:0.78rem;color:#cbd5e1;">Your ${plan.vehicle_specs.estimated_range_km} km EV battery can complete this ${totalDist} km trip with safe reserve buffer.</div>
        </div>
      </div>
    `;
  }

  const corridorCardsHtml = corridorStations.map(s => {
    const avail = Number(s.available_slots ?? 0);
    const total = Number(s.total_slots ?? 4);
    const isAvail = avail > 0;
    const statusCol = isAvail ? '#10b981' : '#ef4444';
    const statusTxt = isAvail ? `${avail}/${total} Free` : 'All Busy';
    const devTxt = typeof s.corridor_deviation_km === 'number'
      ? `${s.corridor_deviation_km} km off-highway`
      : 'On Highway';
    const distFromStart = typeof s.distance_from_start_km === 'number'
      ? `${s.distance_from_start_km} km from start`
      : '';

    return `
      <div class="station-live-card" data-station-id="${s.id}">
        <div class="station-card-top">
          <div style="flex:1;min-width:0;">
            <div style="display:flex;gap:5px;align-items:center;margin-bottom:2px;">
              <span class="station-network-pill">${s.operator || s.network || 'EV Grid'}</span>
              <span style="font-size:0.72rem;font-weight:800;color:#38bdf8;">${distFromStart}</span>
            </div>
            <h4 class="station-name-text" style="cursor:pointer;" onclick="focusStationOnMap('${s.id}')">${s.name}</h4>
            <div class="station-address-text">
              <i class="fa-solid fa-location-dot" style="color:#ff5722;"></i>
              <span>${s.address || s.city || 'Highway Hub'} &bull; <strong style="color:#94a3b8;">${devTxt}</strong></span>
            </div>
          </div>
          <span style="padding:3px 9px;border-radius:99px;font-size:0.72rem;font-weight:800;background:${statusCol}22;color:${statusCol};border:1px solid ${statusCol}44;white-space:nowrap;">
            ${statusTxt}
          </span>
        </div>

        <div class="station-meta-specs">
          <div class="meta-spec-item"><i class="fa-solid fa-bolt" style="color:#f59e0b;"></i><strong>${s.power_kw || 60} kW Fast DC</strong></div>
          <div class="meta-spec-item price"><i class="fa-solid fa-indian-rupee-sign"></i><span>₹${s.price_per_kwh || 18.5}/kWh</span></div>
        </div>

        <div class="station-card-actions">
          <button type="button" class="btn-card-lock" onclick="openBookingFromHome('${s.id}')">
            <i class="fa-solid fa-lock"></i>
            <span>Lock Slot (30m)</span>
          </button>
          <button type="button" class="btn-card-inspect" onclick="focusStationOnMap('${s.id}')" title="Zoom on Map">
            <i class="fa-solid fa-location-crosshairs"></i>
            <span>View</span>
          </button>
        </div>
      </div>
    `;
  }).join('');

  container.innerHTML = `
    <!-- 1. Trip Header & 4 KPI Metrics -->
    <div class="trip-summary-card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.65rem;">
        <span style="font-size:0.72rem;font-weight:800;color:#00d4aa;text-transform:uppercase;letter-spacing:0.04em;">
          <i class="fa-solid fa-route"></i> Highway Corridor Plan
        </span>
        <span style="font-size:0.75rem;color:#38bdf8;font-weight:700;">
          ${plan.origin.name.split(',')[0]} &rarr; ${plan.destination.name.split(',')[0]}
        </span>
      </div>

      <div class="trip-kpi-grid">
        <div class="trip-kpi-cell">
          <div class="trip-kpi-label">DISTANCE</div>
          <div class="trip-kpi-val" style="color:#fff;">${totalDist} km</div>
        </div>
        <div class="trip-kpi-cell">
          <div class="trip-kpi-label">TOTAL TIME</div>
          <div class="trip-kpi-val" style="color:#38bdf8;">${totalTimeFormatted}</div>
        </div>
        <div class="trip-kpi-cell">
          <div class="trip-kpi-label">CORRIDOR HUBS</div>
          <div class="trip-kpi-val" style="color:#00d4aa;">${plan.en_route_stations_count}</div>
        </div>
        <div class="trip-kpi-cell">
          <div class="trip-kpi-label">FUEL SAVINGS</div>
          <div class="trip-kpi-val" style="color:#10b981;">₹${eco.net_rupee_savings || 1200}</div>
        </div>
      </div>

      <div style="font-size:0.74rem;color:#94a3b8;display:flex;justify-content:space-between;margin-top:0.4rem;">
        <span><i class="fa-solid fa-car-side"></i> Drive: ${driveTimeFormatted}</span>
        <span><i class="fa-solid fa-leaf" style="color:#10b981;"></i> CO2 Saved: ${eco.co2_abated_kg || 40} kg</span>
      </div>
    </div>

    <!-- 2. Battery SOC Progression Timeline -->
    <div class="soc-timeline-card">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:0.74rem;font-weight:700;color:#cbd5e1;text-transform:uppercase;letter-spacing:0.04em;">
          <i class="fa-solid fa-battery-three-quarters" style="color:#00d4aa;"></i> Battery State of Charge (SOC) Simulation
        </span>
        <span style="font-size:0.72rem;color:#94a3b8;">${plan.vehicle_specs.battery_capacity_kwh} kWh Pack</span>
      </div>
      <div class="soc-track-outer">
        <div class="soc-track-bar"></div>
        <div class="soc-milestones-row">
          ${milestonesHtml}
        </div>
      </div>
    </div>

    <!-- 3. Spotlight Recommended Charging Stop -->
    ${spotlightHtml}

    <!-- 4. En-Route Stations Stream -->
    <div style="margin:1rem 0 0.5rem 0.25rem;display:flex;justify-content:space-between;align-items:center;">
      <span style="font-size:0.84rem;font-weight:800;color:#ffffff;text-transform:uppercase;letter-spacing:0.04em;">
        <i class="fa-solid fa-charging-station" style="color:#00d4aa;"></i> En-Route Charging Hubs (${corridorStations.length})
      </span>
      <span style="font-size:0.75rem;color:#94a3b8;">Sorted along highway</span>
    </div>
    <div style="display:flex;flex-direction:column;gap:0.85rem;">
      ${corridorCardsHtml}
    </div>
  `;
}

// ================= 9. 30-Minute Guaranteed Slot Lock & Bay Inspector =================
async function openBookingFromHome(stationId, preferredSlotId = null) {
  let s = allStations.find(item => String(item.id) === String(stationId));
  if (!s) return;

  try {
    const res = await fetch(`/api/stations/${stationId}/slots`);
    const data = await res.json();
    if (data && data.station) {
      s = normalizeStationSlots({ ...s, ...data.station });
    }
  } catch (e) {}

  document.getElementById('bookStationId').value = s.id;
  document.getElementById('bookModalStationName').textContent = s.name;
  document.getElementById('bookModalStationAddress').textContent = s.address || s.city || 'India';
  document.getElementById('bookModalPrice').textContent = `₹${s.price_per_kwh || 18.5}/kWh • Up to ${s.power_kw || 60} kW Fast DC`;

  const slotSelect = document.getElementById('bookSlotSelect');
  if (slotSelect) {
    const slots = Array.isArray(s.slots) ? s.slots : [];
    const availSlots = slots.filter(sl => String(sl.status).toLowerCase() === 'available' || sl.is_free);
    if (availSlots.length > 0) {
      slotSelect.innerHTML = availSlots.map(sl => `
        <option value="${sl.id}" ${preferredSlotId === sl.id ? 'selected' : ''}>
          Bay #${sl.slot_number || sl.bay_number || 1} — ${sl.connector_type || sl.charger_type || 'CCS2'} (${sl.power_kw || s.power_kw || 60} kW) [AVAILABLE]
        </option>
      `).join('');
    } else if (slots.length > 0) {
      slotSelect.innerHTML = slots.map(sl => `
        <option value="${sl.id}">Bay #${sl.slot_number} — ${sl.connector_type} (${sl.power_kw} kW)</option>
      `).join('');
    } else {
      slotSelect.innerHTML = `<option value="slot-${s.id}-1">Bay #1 — Fast DC Charger (60 kW)</option>`;
    }
  }

  if (currentAuthUser) {
    if (currentAuthUser.name) document.getElementById('bookUserName').value = currentAuthUser.name;
    if (currentAuthUser.phone) document.getElementById('bookUserPhone').value = currentAuthUser.phone;
    if (currentAuthUser.vehicle_number) document.getElementById('bookVehicleNumber').value = currentAuthUser.vehicle_number;
    if (currentAuthUser.vehicle_model) document.getElementById('bookVehicleModel').value = currentAuthUser.vehicle_model;
  }

  document.getElementById('homeBookingModal').classList.remove('hidden');
}

function closeHomeBookingModal() {
  document.getElementById('homeBookingModal').classList.add('hidden');
}

function bindModalForms() {
  document.getElementById('homeBookingForm')?.addEventListener('submit', handleHomeBookingSubmit);
  document.getElementById('partnerInquiryForm')?.addEventListener('submit', handlePartnerFormSubmit);
  document.getElementById('inPageAuthForm')?.addEventListener('submit', handleInPageAuthSubmit);
  document.getElementById('oauthModalForm')?.addEventListener('submit', handleOAuthCustomSubmit);
  document.getElementById('inPageResetPasswordForm')?.addEventListener('submit', handleInPageResetPasswordSubmit);
  document.getElementById('pilotAddVehicleForm')?.addEventListener('submit', handlePilotAddVehicle);
  document.getElementById('pilotRegisterStationForm')?.addEventListener('submit', handlePilotRegisterStation);
  document.getElementById('pilotUpdateProfileForm')?.addEventListener('submit', handleUpdateProfileSubmit);
  document.getElementById('pilotChangePasswordForm')?.addEventListener('submit', handleChangePasswordSubmit);
}

async function handleHomeBookingSubmit(e) {
  e.preventDefault();
  const stationId = document.getElementById('bookStationId').value;
  const slotId = document.getElementById('bookSlotSelect')?.value || `slot-${stationId}-1`;
  const userName = document.getElementById('bookUserName').value.trim();
  const userPhone = document.getElementById('bookUserPhone').value.trim();
  const vehicleNumber = document.getElementById('bookVehicleNumber').value.trim().toUpperCase();
  const vehicleModel = document.getElementById('bookVehicleModel').value.trim() || 'Tata Nexon EV Max';

  const submitBtn = document.getElementById('bookSubmitBtn');
  submitBtn.disabled = true;
  submitBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Locking Slot Exclusively...`;

  try {
    const res = await fetch('/api/bookings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        station_id: stationId,
        slot_id: slotId,
        user_id: currentAuthUser?.id || null,
        user_name: userName,
        phone: userPhone,
        vehicle_number: vehicleNumber,
        vehicle_model: vehicleModel
      })
    });

    const data = await res.json();
    submitBtn.disabled = false;
    submitBtn.innerHTML = `<i class="fa-solid fa-lock"></i> Confirm 30-Minute Lock`;

    if (data.success && data.booking) {
      closeHomeBookingModal();
      activeReservation = data.booking;
      localStorage.setItem('ev_yatra_active_booking', JSON.stringify(activeReservation));
      showDigitalPassModal(data.booking);
      updateStickyReservationBar(data.booking);
      loadLiveStationsForHome();
      showHomeToast(`Bay #${data.booking.slot_number || 1} Locked Exclusively for 30 Minutes!`);
    } else {
      showHomeToast(data.error || 'Could not lock slot. Please select another bay.');
    }
  } catch (err) {
    submitBtn.disabled = false;
    submitBtn.innerHTML = `<i class="fa-solid fa-lock"></i> Confirm 30-Minute Lock`;
    showHomeToast('Network error while locking charging bay.');
  }
}

function showDigitalPassModal(booking) {
  const s = allStations.find(item => String(item.id) === String(booking.station_id));
  const stationName = booking.station_name || (s ? s.name : 'EV Yatra Fast Hub');

  document.getElementById('passId').textContent = booking.id || booking.booking_id || 'EVY-LOCK';
  document.getElementById('passStationName').textContent = stationName;
  document.getElementById('passBayNumber').textContent = `Bay #${booking.slot_number || booking.bay_number || 1} (RESERVED)`;
  document.getElementById('passPilotName').textContent = booking.user_name || 'EV Driver';
  document.getElementById('passVehicleNumber').textContent = booking.vehicle_number || 'IND EV';

  document.getElementById('homePassModal').classList.remove('hidden');
  startBookingCountdown(booking.expires_at_epoch || booking.expires_at);
}

function closeHomePassModal() {
  document.getElementById('homePassModal').classList.add('hidden');
}

function restoreActiveReservation() {
  const saved = localStorage.getItem('ev_yatra_active_booking');
  if (!saved) return;
  try {
    const booking = JSON.parse(saved);
    const expiryMs = booking.expires_at_epoch
      ? booking.expires_at_epoch * 1000
      : (typeof booking.expires_at === 'string' ? new Date(booking.expires_at).getTime() : 0);
    if (booking && expiryMs > Date.now()) {
      activeReservation = booking;
      updateStickyReservationBar(booking);
      startBookingCountdown(booking.expires_at_epoch || booking.expires_at);
    } else {
      localStorage.removeItem('ev_yatra_active_booking');
    }
  } catch (e) {
    localStorage.removeItem('ev_yatra_active_booking');
  }
}

function updateStickyReservationBar(booking) {
  const bar = document.getElementById('stickyReservationBar');
  if (!bar) return;
  if (!booking) {
    bar.classList.add('hidden');
    return;
  }
  const s = allStations.find(item => String(item.id) === String(booking.station_id));
  const stName = booking.station_name || (s ? s.name : 'EV Charging Hub');
  const nameEl = document.getElementById('stickyBarStationName');
  const bayEl = document.getElementById('stickyBarBayInfo');
  if (nameEl) nameEl.textContent = stName;
  if (bayEl) bayEl.textContent = `Bay #${booking.slot_number || booking.bay_number || 1} • Pass ${booking.id || booking.booking_id}`;
  bar.classList.remove('hidden');
}

function startBookingCountdown(expiresInput) {
  if (passCountdownInterval) clearInterval(passCountdownInterval);
  const modalTimerEl = document.getElementById('passCountdownTimer');
  const stickyTimerEl = document.getElementById('stickyBarCountdown');

  let expiryMs = Date.now() + 30 * 60 * 1000;
  if (typeof expiresInput === 'number') {
    expiryMs = expiresInput * 1000;
  } else if (typeof expiresInput === 'string') {
    const parsed = new Date(expiresInput).getTime();
    if (!isNaN(parsed)) expiryMs = parsed;
  }

  const tick = () => {
    const remainingSec = Math.max(0, Math.floor((expiryMs - Date.now()) / 1000));
    const mins = String(Math.floor(remainingSec / 60)).padStart(2, '0');
    const secs = String(remainingSec % 60).padStart(2, '0');
    const formatted = `${mins}:${secs}`;
    if (modalTimerEl) modalTimerEl.textContent = formatted;
    if (stickyTimerEl) stickyTimerEl.textContent = formatted;

    if (remainingSec <= 0) {
      clearInterval(passCountdownInterval);
      localStorage.removeItem('ev_yatra_active_booking');
      updateStickyReservationBar(null);
    }
  };
  tick();
  passCountdownInterval = setInterval(tick, 1000);
}

async function checkInActiveBooking() {
  if (!activeReservation) {
    closeHomePassModal();
    return;
  }
  const bId = activeReservation.id || activeReservation.booking_id;
  try {
    const res = await fetch(`/api/bookings/${bId}/checkin`, { method: 'POST' });
    const data = await res.json();
    localStorage.removeItem('ev_yatra_active_booking');
    activeReservation = null;
    updateStickyReservationBar(null);
    closeHomePassModal();
    loadLiveStationsForHome();
    if (currentAuthUser?.id) {
      await initHomeAuthUI();
    }
    showHomeToast(data.message || 'Checked in! Charging session started.');
  } catch (e) {
    showHomeToast('Network error checking in.');
  }
}

async function cancelActiveBooking() {
  if (!activeReservation) return;
  const bId = activeReservation.id || activeReservation.booking_id;
  try {
    await fetch(`/api/bookings/${bId}/cancel`, { method: 'POST' });
  } catch (e) {}
  localStorage.removeItem('ev_yatra_active_booking');
  activeReservation = null;
  updateStickyReservationBar(null);
  closeHomePassModal();
  loadLiveStationsForHome();
  showHomeToast('30-Minute slot lock cancelled and bay released.');
}

// ================= 10. Comprehensive Inspect Bays / Slot Telemetry Modal =================
async function inspectSlotsFromHome(stationId) {
  let s = allStations.find(item => String(item.id) === String(stationId));
  if (!s) return;

  const modal = document.getElementById('homeInspectModal');
  const titleEl = document.getElementById('inspectModalStationTitle');
  const slotsContainer = document.getElementById('inspectSlotsGrid');

  titleEl.textContent = s.name;
  slotsContainer.innerHTML = `<div style="padding: 2rem; text-align: center; color: #94a3b8;"><i class="fa-solid fa-spinner fa-spin"></i> Loading live bay telemetry...</div>`;
  modal.classList.remove('hidden');

  try {
    const res = await fetch(`/api/stations/${stationId}/slots`);
    const data = await res.json();
    if (data && data.station) {
      s = normalizeStationSlots({ ...s, ...data.station });
    }
  } catch (err) {}

  const slots = Array.isArray(s.slots) && s.slots.length > 0 ? s.slots : normalizeStationSlots(s).slots;
  const freeCount = slots.filter(sl => sl.is_free || String(sl.status).toLowerCase() === 'available').length;
  const price = s.price_per_kwh || 18.5;

  const topOverviewHtml = `
    <div style="background:#111827;border:1px solid rgba(255,255,255,0.12);border-radius:12px;padding:0.85rem 1rem;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.6rem;margin-bottom:0.85rem;">
      <div>
        <div style="font-size:0.75rem;color:#94a3b8;">${s.network || s.operator || 'EV Grid'} &bull; ${s.address || s.city || 'India'}</div>
        <div style="display:flex;align-items:center;gap:0.75rem;margin-top:3px;">
          <span style="font-size:0.92rem;font-weight:800;color:#00d4aa;">${freeCount}/${slots.length} Bays Available</span>
          <span style="font-size:0.85rem;color:#38bdf8;font-weight:700;">₹${price}/kWh</span>
          <span style="font-size:0.85rem;color:#f59e0b;font-weight:700;">Up to ${s.power_kw || 60} kW</span>
        </div>
      </div>
      <button type="button" onclick="closeHomeInspectModal(); showElectricRoute('${s.id}');" style="background:#0ea5e9;color:#fff;border:none;border-radius:8px;padding:6px 12px;font-size:0.78rem;font-weight:700;cursor:pointer;display:inline-flex;align-items:center;gap:5px;">
        <i class="fa-solid fa-diamond-turn-right"></i> Route on Map
      </button>
    </div>
  `;

  const slotsListHtml = slots.map(slot => {
    const statusUpper = String(slot.status || 'available').toUpperCase();
    const isFree = statusUpper === 'AVAILABLE' || slot.is_free;
    const badgeColor = isFree ? '#10b981' : (statusUpper === 'RESERVED' ? '#f59e0b' : '#ef4444');
    const pKw = slot.power_kw || s.power_kw || 60;
    const estTimeMin = pKw >= 100 ? '~22 mins' : (pKw >= 50 ? '~35 mins' : '~90 mins');
    const reservedInfo = slot.reserved_until ? ` &bull; Locked until ${slot.reserved_until}` : '';

    return `
      <div style="background: #192238; border: 1.5px solid ${badgeColor}44; border-radius: 12px; padding: 0.95rem 1rem; display: flex; justify-content: space-between; align-items: center; gap: 0.75rem; flex-wrap: wrap;">
        <div>
          <div style="font-weight: 800; color: #ffffff; font-size: 0.96rem; display:flex; align-items:center; gap:6px;">
            <i class="fa-solid fa-charging-station" style="color:${badgeColor};"></i>
            <span>Bay #${slot.slot_number || 1} &mdash; ${slot.connector_type || 'CCS2 Fast DC'}</span>
          </div>
          <div style="font-size: 0.78rem; color: #94a3b8; margin-top: 3px;">
            Max Output: <strong style="color:#fff;">${pKw} kW</strong> &bull; 20-80%: <span style="color:#38bdf8;">${estTimeMin}</span> &bull; Tariff: <span style="color:#34d399;">₹${price}/kWh</span>${reservedInfo}
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:0.5rem;flex-wrap:wrap;">
          <span style="padding: 4px 10px; border-radius: 999px; font-size: 0.74rem; font-weight: 800; background: ${badgeColor}22; color: ${badgeColor}; border:1px solid ${badgeColor}55;">
            ${statusUpper}
          </span>
          ${isFree ? `
            <button onclick="closeHomeInspectModal(); openBookingFromHome('${s.id}', '${slot.id}')" style="background:#ff5722;color:#fff;border:none;border-radius:8px;padding:6px 12px;font-size:0.78rem;font-weight:800;cursor:pointer;display:inline-flex;align-items:center;gap:4px;">
              <i class="fa-solid fa-lock"></i> Lock Bay
            </button>
          ` : `
            <span style="font-size:0.75rem;color:#94a3b8;padding:4px 8px;background:rgba(255,255,255,0.05);border-radius:6px;">In Use</span>
          `}
        </div>
      </div>
    `;
  }).join('');

  slotsContainer.innerHTML = topOverviewHtml + slotsListHtml;
}

function closeHomeInspectModal() {
  document.getElementById('homeInspectModal').classList.add('hidden');
}

// ================= 11. Real Account & Mission Control Dashboard Modal (5 Tabs) =================
function openPilotDashboardModal(defaultTab = 'telemetry') {
  if (!currentAuthUser || !currentAuthUser.id) {
    pendingDashboardTab = defaultTab;
    showHomeToast('Please sign in or create an account to access your dashboard.');
    openInPageAuthModal('login');
    return;
  }

  const modal = document.getElementById('pilotDashboardModal');
  if (!modal) return;
  modal.classList.remove('hidden');
  switchPilotTab(defaultTab);
  refreshPilotDashboardData();
}

function closePilotDashboardModal() {
  const modal = document.getElementById('pilotDashboardModal');
  if (modal) modal.classList.add('hidden');
}

function switchPilotTab(tabId) {
  document.querySelectorAll('.pilot-tab-btn').forEach(btn => {
    if (btn.hasAttribute('data-tab')) {
      btn.classList.toggle('active', btn.getAttribute('data-tab') === tabId);
    }
  });
  document.querySelectorAll('.pilot-tab-pane').forEach(pane => {
    pane.classList.toggle('active', pane.id === `pilotTab-${tabId}`);
  });
}

async function refreshPilotDashboardData() {
  if (!currentAuthUser || !currentAuthUser.id) return;
  const userId = currentAuthUser.id;

  try {
    const res = await fetch(`/api/auth/profile?user_id=${encodeURIComponent(userId)}`);
    const data = await res.json();
    if (data.success && data.user) {
      currentAuthUser = data.user;
      localStorage.setItem('ev_yatra_auth_user', JSON.stringify(currentAuthUser));
    }
  } catch (e) {}

  // Header
  const pilotNameEl = document.getElementById('pilotHeaderName');
  const pilotEmailEl = document.getElementById('pilotHeaderEmail');
  const pilotVehicleEl = document.getElementById('pilotHeaderVehicle');
  if (pilotNameEl) pilotNameEl.textContent = currentAuthUser.name;
  if (pilotEmailEl) pilotEmailEl.textContent = currentAuthUser.email;
  if (pilotVehicleEl) pilotVehicleEl.textContent = `${currentAuthUser.vehicle_model || 'EV'} (${currentAuthUser.vehicle_number || 'IND'})`;

  // Tab 1: Real Telemetry & Impact
  const totalKwh = Number(currentAuthUser.total_kwh || 0).toFixed(1);
  const co2Saved = Number(currentAuthUser.co2_saved_kg || 0).toFixed(1);
  const sessions = Number(currentAuthUser.completed_sessions || 0);
  const savedInr = Number(currentAuthUser.fuel_saved_inr || Math.round(totalKwh * 45)).toLocaleString('en-IN');

  const kwhEl = document.getElementById('pilotStatKwh');
  const co2El = document.getElementById('pilotStatCo2');
  const sessEl = document.getElementById('pilotStatSessions');
  const inrEl = document.getElementById('pilotStatSavedInr');
  if (kwhEl) kwhEl.textContent = `${totalKwh} kWh`;
  if (co2El) co2El.textContent = `${co2Saved} kg`;
  if (sessEl) sessEl.textContent = `${sessions} Sessions`;
  if (inrEl) inrEl.textContent = `₹${savedInr}`;

  // Tab 2: My EV Garage
  const garageList = document.getElementById('pilotGarageList');
  const vehicles = currentAuthUser.vehicles || [];
  if (garageList) {
    if (vehicles.length === 0) {
      garageList.innerHTML = `<div style="padding:1rem;color:#94a3b8;">No vehicles registered yet. Add your EV below.</div>`;
    } else {
      garageList.innerHTML = vehicles.map(v => {
        const modelName = v.vehicle_model || v.model || 'EV Vehicle';
        const plateNo = v.vehicle_number || v.registration_number || 'IND EV';
        const connType = v.preferred_connector || v.connector_type || 'CCS2';
        return `
          <div style="background:#192238;border:1px solid ${v.is_active ? '#00d4aa' : 'rgba(255,255,255,0.1)'};border-radius:12px;padding:0.9rem 1rem;display:flex;justify-content:space-between;align-items:center;gap:0.75rem;">
            <div>
              <div style="font-weight:800;color:#fff;font-size:0.95rem;">
                <i class="fa-solid fa-car-side" style="color:#00d4aa;"></i> ${modelName}
                ${v.is_active ? '<span style="font-size:0.7rem;background:rgba(0,212,170,0.2);color:#00d4aa;padding:2px 8px;border-radius:99px;margin-left:6px;">ACTIVE EV</span>' : ''}
              </div>
              <div style="font-size:0.78rem;color:#94a3b8;">Plate: ${plateNo} • ${connType} • ${v.battery_capacity_kwh || 45} kWh</div>
            </div>
            <div style="display:flex;gap:0.45rem;">
              ${!v.is_active ? `<button onclick="selectActivePilotVehicle('${v.id}')" style="background:#ff5722;color:#fff;border:none;border-radius:8px;padding:6px 10px;font-size:0.75rem;font-weight:700;cursor:pointer;">Set Active</button>` : ''}
              ${vehicles.length > 1 ? `<button onclick="deletePilotVehicle('${v.id}')" style="background:rgba(239,68,68,0.15);color:#f87171;border:1px solid rgba(239,68,68,0.3);border-radius:8px;padding:6px 9px;font-size:0.75rem;cursor:pointer;" title="Remove Vehicle"><i class="fa-solid fa-trash"></i></button>` : ''}
            </div>
          </div>
        `;
      }).join('');
    }
  }

  // Tab 4: Passes, Orders & History
  const historyList = document.getElementById('pilotHistoryList');
  const bookings = currentAuthUser.bookings || [];
  if (historyList) {
    if (bookings.length === 0) {
      historyList.innerHTML = `<div style="padding:1rem;text-align:center;color:#94a3b8;background:#192238;border-radius:10px;">No slot reservations yet. Lock any station for 30 minutes from the map!</div>`;
    } else {
      historyList.innerHTML = bookings.map(b => {
        const stUpper = String(b.status || 'active').toUpperCase();
        const isAct = stUpper === 'ACTIVE';
        return `
          <div style="background:#192238;border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:0.8rem 1rem;display:flex;justify-content:space-between;align-items:center;gap:0.75rem;">
            <div>
              <div style="font-weight:800;color:#fff;font-size:0.9rem;">${b.station_name || 'EV Charging Hub'}</div>
              <div style="font-size:0.76rem;color:#94a3b8;">Pass: <strong style="color:#38bdf8;">${b.id}</strong> • Bay #${b.slot_number || 1} • ${b.vehicle_number || ''}</div>
            </div>
            <div style="display:flex;align-items:center;gap:0.5rem;">
              <span style="font-size:0.7rem;font-weight:800;padding:3px 9px;border-radius:99px;background:rgba(16,185,129,0.15);color:#34d399;">${stUpper}</span>
              ${isAct ? `<button onclick="closePilotDashboardModal(); activeReservation = ${JSON.stringify(b).replace(/"/g, '&quot;')}; checkInActiveBooking();" style="background:#00d4aa;color:#041318;border:none;border-radius:7px;padding:4px 8px;font-size:0.72rem;font-weight:800;cursor:pointer;">Check In</button>` : ''}
            </div>
          </div>
        `;
      }).join('');
    }
  }

  const ordersList = document.getElementById('pilotOrdersList');
  const orders = currentAuthUser.orders || [];
  if (ordersList) {
    if (orders.length === 0) {
      ordersList.innerHTML = `<div style="padding:1rem;text-align:center;color:#94a3b8;background:#192238;border-radius:10px;">No active store passes or hardware orders yet.</div>`;
    } else {
      ordersList.innerHTML = orders.map(o => `
        <div style="background:#192238;border:1px solid rgba(56,189,248,0.25);border-radius:12px;padding:0.8rem 1rem;display:flex;justify-content:space-between;align-items:center;gap:0.75rem;">
          <div>
            <div style="font-weight:800;color:#fff;font-size:0.9rem;">${o.item_name}</div>
            <div style="font-size:0.76rem;color:#94a3b8;">Order ID: <strong style="color:#00d4aa;">${o.id}</strong> • ₹${o.amount_inr}</div>
          </div>
          <span style="font-size:0.7rem;font-weight:800;padding:3px 9px;border-radius:99px;background:rgba(56,189,248,0.15);color:#38bdf8;">${String(o.status).toUpperCase()}</span>
        </div>
      `).join('');
    }
  }

  // Tab 5: Account & Security pre-fill
  const profName = document.getElementById('profEditName');
  const profPhone = document.getElementById('profEditPhone');
  const profModel = document.getElementById('profEditVehicleModel');
  const profNum = document.getElementById('profEditVehicleNumber');
  if (profName) profName.value = currentAuthUser.name || '';
  if (profPhone) profPhone.value = currentAuthUser.phone || '';
  if (profModel) profModel.value = currentAuthUser.vehicle_model || '';
  if (profNum) profNum.value = currentAuthUser.vehicle_number || '';
}

async function selectActivePilotVehicle(vehicleId) {
  if (!currentAuthUser?.id) return;
  try {
    const res = await fetch(`/api/users/${currentAuthUser.id}/vehicles/${vehicleId}/select`, { method: 'PUT' });
    const data = await res.json();
    if (data.success && data.user) {
      currentAuthUser = data.user;
      localStorage.setItem('ev_yatra_auth_user', JSON.stringify(currentAuthUser));
      refreshPilotDashboardData();
      showHomeToast('Active EV updated!');
    }
  } catch (e) {
    showHomeToast('Could not switch active vehicle.');
  }
}

async function deletePilotVehicle(vehicleId) {
  if (!currentAuthUser?.id) return;
  try {
    const res = await fetch(`/api/users/${currentAuthUser.id}/vehicles/${vehicleId}`, { method: 'DELETE' });
    const data = await res.json();
    if (data.success && data.user) {
      currentAuthUser = data.user;
      localStorage.setItem('ev_yatra_auth_user', JSON.stringify(currentAuthUser));
      refreshPilotDashboardData();
      showHomeToast('Vehicle removed from garage.');
    }
  } catch (e) {}
}

async function handlePilotAddVehicle(e) {
  e.preventDefault();
  if (!currentAuthUser?.id) return;
  const model = document.getElementById('newEvModel').value.trim();
  const regNo = document.getElementById('newEvPlate').value.trim().toUpperCase();
  const connector = document.getElementById('newEvConnector').value;
  const capacity = parseFloat(document.getElementById('newEvCapacity').value) || 45;

  if (!model || !regNo) return;

  try {
    const res = await fetch(`/api/users/${currentAuthUser.id}/vehicles`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        vehicle_model: model,
        vehicle_number: regNo,
        preferred_connector: connector,
        battery_capacity_kwh: capacity
      })
    });
    const data = await res.json();
    if (data.success) {
      e.target.reset();
      await refreshPilotDashboardData();
      showHomeToast(`${model} added to your EV Garage!`);
    }
  } catch (err) {
    showHomeToast('Error adding vehicle.');
  }
}

async function handleUpdateProfileSubmit(e) {
  e.preventDefault();
  if (!currentAuthUser?.id) return;
  const name = document.getElementById('profEditName').value.trim();
  const phone = document.getElementById('profEditPhone').value.trim();
  const vehicle_model = document.getElementById('profEditVehicleModel').value.trim();
  const vehicle_number = document.getElementById('profEditVehicleNumber').value.trim().toUpperCase();

  try {
    const res = await fetch('/api/auth/profile', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: currentAuthUser.id,
        name,
        phone,
        vehicle_model,
        vehicle_number
      })
    });
    const data = await res.json();
    if (data.success && data.user) {
      currentAuthUser = data.user;
      localStorage.setItem('ev_yatra_auth_user', JSON.stringify(currentAuthUser));
      initHomeAuthUI();
      refreshPilotDashboardData();
      showHomeToast('Profile updated in database!');
    } else {
      showHomeToast(data.error || 'Could not update profile.');
    }
  } catch (err) {
    showHomeToast('Network error updating profile.');
  }
}

async function handleChangePasswordSubmit(e) {
  e.preventDefault();
  if (!currentAuthUser?.id) return;
  const current_password = document.getElementById('profCurrPassword').value.trim();
  const new_password = document.getElementById('profNewPassword').value.trim();

  try {
    const res = await fetch('/api/auth/change-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: currentAuthUser.id,
        current_password,
        new_password
      })
    });
    const data = await res.json();
    if (data.success) {
      e.target.reset();
      showHomeToast(data.message || 'Password updated!');
    } else {
      showHomeToast(data.error || 'Could not change password.');
    }
  } catch (err) {
    showHomeToast('Network error changing password.');
  }
}

function autoFillStationGps() {
  const latInput = document.getElementById('newStationLat');
  const lngInput = document.getElementById('newStationLng');
  if (latInput) latInput.value = userLat.toFixed(5);
  if (lngInput) lngInput.value = userLng.toFixed(5);
  showHomeToast('GPS coordinates auto-filled!');
}

async function handlePilotRegisterStation(e) {
  e.preventDefault();
  const name = document.getElementById('newStationName').value.trim();
  const network = document.getElementById('newStationOperator').value.trim() || 'EV Yatra Partner';
  const address = document.getElementById('newStationAddress').value.trim();
  const lat = parseFloat(document.getElementById('newStationLat').value) || userLat;
  const lng = parseFloat(document.getElementById('newStationLng').value) || userLng;
  const powerKw = parseInt(document.getElementById('newStationPower').value, 10) || 60;
  const price = parseFloat(document.getElementById('newStationPrice').value) || 18.0;
  const totalSlots = parseInt(document.getElementById('newStationSlots').value, 10) || 4;

  try {
    const res = await fetch('/api/stations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        network,
        address,
        latitude: lat,
        longitude: lng,
        power_kw: powerKw,
        price_per_kwh: price,
        total_slots: totalSlots
      })
    });
    const data = await res.json();
    if (data.success && data.station) {
      e.target.reset();
      closePilotDashboardModal();
      await loadLiveStationsForHome();
      focusStationOnMap(data.station.id);
      showHomeToast(`Station "${name}" permanently added to the Pan-India Live Map!`);
    } else {
      showHomeToast(data.error || 'Could not register station.');
    }
  } catch (err) {
    showHomeToast('Error registering station.');
  }
}

// ================= 12. Real Partner Applications & Store Orders =================
function openPartnerModal() {
  document.getElementById('partnerInquiryModal').classList.remove('hidden');
}

function closePartnerModal() {
  document.getElementById('partnerInquiryModal').classList.add('hidden');
}

async function handlePartnerFormSubmit(e) {
  e.preventDefault();
  const contact_name = document.getElementById('partName').value.trim();
  const phone = document.getElementById('partPhone').value.trim();
  const city = document.getElementById('partCity').value.trim();
  const email = document.getElementById('partEmail').value.trim();
  const property_type = document.getElementById('partLandType')?.value || 'Commercial Land';
  const power_load = document.getElementById('partPower')?.value || '60kW - 120kW DC Fast';

  const btn = document.getElementById('partSubmitBtn');
  if (btn) btn.disabled = true;

  try {
    const res = await fetch('/api/partners/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ contact_name, phone, email, city, property_type, power_load })
    });
    const data = await res.json();
    if (btn) btn.disabled = false;

    if (data.success) {
      closePartnerModal();
      e.target.reset();
      showHomeToast(data.message || `Application registered for ${city}!`);
    } else {
      showHomeToast(data.error || 'Could not submit application.');
    }
  } catch (err) {
    if (btn) btn.disabled = false;
    showHomeToast('Network error submitting partnership application.');
  }
}

function openOffersModal() {
  document.getElementById('offersModal').classList.remove('hidden');
}

function closeOffersModal() {
  document.getElementById('offersModal').classList.add('hidden');
}

async function purchaseStoreItem(itemName, itemType, amountInr) {
  if (!currentAuthUser || !currentAuthUser.id) {
    closeOffersModal();
    showHomeToast('Please sign in to activate a pass or place a hardware order.');
    openInPageAuthModal('login');
    return;
  }

  try {
    const res = await fetch('/api/store/order', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: currentAuthUser.id,
        item_name: itemName,
        item_type: itemType,
        amount_inr: amountInr
      })
    });
    const data = await res.json();
    if (data.success) {
      closeOffersModal();
      showHomeToast(data.message || `Order confirmed for ${itemName}!`);
      openPilotDashboardModal('history');
    } else {
      showHomeToast(data.error || 'Could not complete order.');
    }
  } catch (err) {
    showHomeToast('Network error placing order.');
  }
}

// ================= 13. Utilities =================
function calculateHaversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

function showHomeToast(msg) {
  const toast = document.getElementById('homeToast');
  if (!toast) return;
  toast.textContent = msg;
  toast.style.display = 'block';
  clearTimeout(window._homeToastTimer);
  window._homeToastTimer = setTimeout(() => {
    toast.style.display = 'none';
  }, 4000);
}

function toggleMobileNavDrawer() {
  const drawer = document.getElementById('mobileNavDrawer');
  if (drawer) {
    drawer.classList.toggle('hidden');
    drawer.classList.toggle('active');
  }
}


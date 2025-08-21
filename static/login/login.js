// Variables globales
let isPasswordVisible = false;

// Utilitaire: récupération du CSRF token
function getCsrfToken() {
	const fromWindow = typeof window !== 'undefined' ? window.CSRF_TOKEN : null;
	if (fromWindow) return fromWindow;
	const cookieMatch = document.cookie.match(/csrftoken=([^;]+)/);
	return cookieMatch ? cookieMatch[1] : '';
}

// Fonction pour basculer la visibilité du mot de passe
function togglePassword() {
	const passwordInput = document.getElementById('password');
	const toggleIcon = document.querySelector('.password-toggle');
	if (passwordInput.type === 'password') {
		passwordInput.type = 'text';
		toggleIcon.textContent = '🙈';
	} else {
		passwordInput.type = 'password';
		toggleIcon.textContent = '👁️';
	}
}

// Gestion du formulaire de connexion (appel API Django)
document.addEventListener('DOMContentLoaded', function() {
	const form = document.getElementById('loginForm');
	const loginBtn = document.getElementById('loginBtn');
	if (!form) return;

	form.addEventListener('submit', async function(e) {
		e.preventDefault();
		const username = document.getElementById('username').value.trim();
		const password = document.getElementById('password').value.trim();
		if (!username || !password) {
			showNotification('Veuillez remplir tous les champs', 'error');
			return;
		}
		setLoadingState(loginBtn, true);
		try {
			const response = await fetch('/gestion-caisses/api/login/', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'X-CSRFToken': getCsrfToken(),
				},
				credentials: 'same-origin',
				body: JSON.stringify({ username, password })
			});
			const data = await response.json();
			if (response.ok && data.success) {
				showNotification('Connexion réussie !', 'success');
				setTimeout(() => {
					// Rediriger selon le rôle de l'utilisateur
                    if (data.user && data.user.role === 'Administrateur') {
                        window.location.href = '/adminsecurelogin/';
					} else {
						window.location.href = '/gestion-caisses/dashboard/';
					}
				}, 700);
			} else {
				handleAuthError(loginBtn, data.message || 'Identifiants incorrects');
			}
		} catch (err) {
			console.error(err);
			handleAuthError(loginBtn, 'Erreur de connexion au serveur');
		} finally {
			setTimeout(() => setLoadingState(loginBtn, false), 400);
		}
	});
});

// États de chargement
function setLoadingState(button, isLoading) {
	if (!button) return;
	if (isLoading) {
		button.classList.add('loading');
		button.textContent = '';
	} else {
		button.classList.remove('loading');
		button.textContent = 'Se connecter';
	}
}

// Gestion des erreurs
function handleAuthError(loginBtn, message) {
	setLoadingState(loginBtn, false);
	showNotification(message, 'error');
	const container = document.querySelector('.login-container');
	if (container) {
		container.style.animation = 'shake 0.5s ease-in-out';
		setTimeout(() => { container.style.animation = ''; }, 500);
	}
	const userInput = document.getElementById('username');
	if (userInput) userInput.focus();
}

// Notifications UI
function showNotification(message, type = 'info') {
	const existingNotifications = document.querySelectorAll('.notification');
	existingNotifications.forEach(n => n.remove());
	const notification = document.createElement('div');
	notification.className = `notification ${type}`;
	notification.textContent = message;
	const styles = {
		info: 'background: linear-gradient(135deg, #4299e1, #3182ce);',
		success: 'background: linear-gradient(135deg, #48bb78, #38a169);',
		error: 'background: linear-gradient(135deg, #f56565, #e53e3e);',
		warning: 'background: linear-gradient(135deg, #ed8936, #dd6b20);'
	};
	notification.style.cssText = `position: fixed; top: 20px; right: 20px; padding: 16px 24px; border-radius: 12px; color: white; font-weight: 500; z-index: 1000; transform: translateX(100%); transition: transform 0.3s ease; box-shadow: 0 10px 25px rgba(0,0,0,0.1); ${styles[type]}`;
	document.body.appendChild(notification);
	setTimeout(() => { notification.style.transform = 'translateX(0)'; }, 50);
	setTimeout(() => {
		notification.style.transform = 'translateX(100%)';
		setTimeout(() => notification.remove(), 300);
	}, 3000);
	notification.addEventListener('click', () => {
		notification.style.transform = 'translateX(100%)';
		setTimeout(() => notification.remove(), 300);
	});
}

// Styles dynamiques pour validation
const validationStyles = `
	.field-valid { border-color: #48bb78 !important; background: #f0fff4 !important; }
	.field-invalid { border-color: #f56565 !important; background: #fff5f5 !important; }
`;
const styleSheet = document.createElement('style');
styleSheet.textContent = validationStyles;
document.head.appendChild(styleSheet);



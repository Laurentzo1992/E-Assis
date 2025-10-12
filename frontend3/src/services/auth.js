/**
 * @file auth.js
 * @description Service de gestion de l'authentification et des tokens.
 * Gère le stockage, la récupération, le rafraîchissement des tokens JWT,
 * et la déconnexion de l'utilisateur.
 */

// --- Instance de navigation pour les redirections ---
let navigateInstance;

/**
 * Définit l'instance de navigation de React Router pour permettre les redirections
 * depuis l'extérieur des composants React.
 * @param {Function} navigateFunc - La fonction `navigate` obtenue via le hook `useNavigate`.
 */
export const setNavigateInstance = (navigateFunc) => {
  navigateInstance = navigateFunc;
};

// --- Fonctions de gestion des tokens ---

/**
 * Récupère les tokens depuis le localStorage ou sessionStorage.
 * @returns {{accessToken: string|null, refreshToken: string|null}}
 */
const getTokens = () => {
  const accessToken =
    localStorage.getItem("accessToken") ||
    sessionStorage.getItem("accessToken");
  const refreshToken =
    localStorage.getItem("refreshToken") ||
    sessionStorage.getItem("refreshToken");
  return { accessToken, refreshToken };
};

/**
 * Stocke les tokens dans le localStorage
 * ou dans le sessionStorage.
 * @param {string} access - Le token d'accès.
 * @param {string} refresh - Le token de rafraîchissement.
 * @param {boolean} rememberMe - Indique si les tokens doivent être persistants.
 */
export const storeTokens = (access, refresh, rememberMe) => {
  const storage = rememberMe ? localStorage : sessionStorage;
  storage.setItem("accessToken", access);
  storage.setItem("refreshToken", refresh);
};

/**
 * Déconnecte l'utilisateur en supprimant tous les tokens et en redirigeant
 * vers la page de connexion.
 */
export const logout = () => {
  localStorage.removeItem("accessToken");
  localStorage.removeItem("refreshToken");
  sessionStorage.removeItem("accessToken");
  sessionStorage.removeItem("refreshToken");

  console.log("User logged out, redirecting to login.");

  if (navigateInstance) {
    navigateInstance("/Connexion");
  } else {
    // Fallback si navigateInstance n'est pas encore défini
    window.location.href = "/Connexion";
  }
};

/**
 * Tente de rafraîchir le token d'accès en utilisant le refresh token.
 * C'est une fonction interne utilisée par le service `api.js`.
 * @returns {Promise<boolean>} Vrai si le rafraîchissement a réussi, faux sinon.
 */
export const refreshAccessToken = async () => {
  const { refreshToken } = getTokens();

  if (!refreshToken) {
    console.warn("No refresh token available for refresh attempt.");
    return false;
  }

  try {
    const response = await fetch(
      "http://127.0.0.1:8000/api/auth/token/refresh/",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: refreshToken }),
      }
    );

    if (response.ok) {
      const data = await response.json();
      // Le 'rememberMe' est déterminé par la présence du refreshToken dans le localStorage
      const rememberMe = !!localStorage.getItem("refreshToken");
      storeTokens(data.access, data.refresh || refreshToken, rememberMe);
      console.log("Access token refreshed successfully.");
      return true;
    } else {
      // Si le refresh token est lui-même invalide (ex: 401 Unauthorized), on doit déconnecter.
      console.error("Refresh token is invalid or expired. Logging out.");
      logout();
      return false;
    }
  } catch (error) {
    console.error("A network error occurred during token refresh:", error);
    // On ne déconnecte pas forcément sur une erreur réseau, l'utilisateur pourra réessayer.
    return false;
  }
};

/**
 * Renvoie le token d'accès actuel. Utilisé par `api.js`.
 * @returns {string|null} Le token d'accès.
 */
export const getAccessToken = () => {
  return getTokens().accessToken;
};

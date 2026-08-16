// src/services/auth.js

import { API_BASE_URL } from "../config";

// Obtenez une instance de navigate pour les redirections
let navigateInstance;
export const setNavigateInstance = (navigateFunc) => {
  navigateInstance = navigateFunc;
};

// Fonction pour récupérer les tokens
export const getTokens = () => {
  const accessToken =
    localStorage.getItem("accessToken") ||
    sessionStorage.getItem("accessToken");
  const refreshToken =
    localStorage.getItem("refreshToken") ||
    sessionStorage.getItem("refreshToken");
  return { accessToken, refreshToken };
};

// Fonction pour stocker les tokens (utilisée par la page de connexion)
export const storeTokens = (access, refresh, rememberMe) => {
  if (rememberMe) {
    localStorage.setItem("accessToken", access);
    localStorage.setItem("refreshToken", refresh);
  } else {
    sessionStorage.setItem("accessToken", access);
    sessionStorage.setItem("refreshToken", refresh);
  }
};

// Fonction pour supprimer les tokens (déconnexion)
export const logout = () => {
  localStorage.removeItem("accessToken");
  localStorage.removeItem("refreshToken");
  sessionStorage.removeItem("accessToken");
  sessionStorage.removeItem("refreshToken");
  if (navigateInstance) {
    navigateInstance("/"); // Redirige vers la landing page
  }
};

// Fonction pour rafraîchir le token d'accès
const refreshAccessToken = async () => {
  const { refreshToken } = getTokens();

  if (!refreshToken) {
    // Si pas de refresh token, l'utilisateur doit se reconnecter
    logout();
    throw new Error("No refresh token available. User must log in again.");
  }

  try {
    const response = await fetch(
      `${API_BASE_URL}/api/token/refresh/`, // route reelle du backend (convention Django SimpleJWT, jamais sous /api/auth/ - cf. api/routers/auth.py)
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ refresh: refreshToken }),
      }
    );

    if (response.ok) {
      const data = await response.json();
      const { access, refresh } = data; // Votre backend peut aussi renvoyer un nouveau refresh token
      storeTokens(access, refresh, !!localStorage.getItem("refreshToken")); // Préserve le choix "se souvenir de moi"
      return access; // Retourne le nouvel access token
    } else {
      // Si le refresh token est invalide ou expiré
      logout();
      throw new Error("Failed to refresh token. Redirecting to login.");
    }
  } catch (error) {
    console.error("Error refreshing token:", error);
    logout(); // En cas d'erreur réseau ou autre, déconnecter
    throw error;
  }
};

// Fonction générale pour faire des requêtes API avec authentification
export const apiRequest = async (url, options = {}) => {
  let { accessToken } = getTokens();

  // Si pas de token du tout, l'utilisateur n'est pas connecté
  if (!accessToken) {
    if (navigateInstance) {
      navigateInstance("/Connexion");
    }
    return null; // Retourne null pour indiquer que la requête n'a pas été faite
  }

  // Ajoute l'en-tête d'autorisation
  options.headers = {
    ...options.headers,
    Authorization: `Bearer ${accessToken}`,
    "Content-Type": "application/json", // Assurez-vous d'avoir toujours ce header pour les API JSON
  };

  let response = await fetch(url, options);

  // Si le token d'accès est expiré (statut 401)
  if (response.status === 401) {
    console.log("Access token expired, attempting to refresh...");
    try {
      const newAccessToken = await refreshAccessToken();
      // Retenter la requête avec le nouveau token
      options.headers["Authorization"] = `Bearer ${newAccessToken}`;
      response = await fetch(url, options);
    } catch (refreshError) {
      console.error("Refresh token failed, forcing logout:", refreshError);
      return null; // Échec du rafraîchissement, la déconnexion a déjà eu lieu
    }
  }

  return response; // Retourne la réponse (qu'elle soit bonne ou une erreur non 401)
};

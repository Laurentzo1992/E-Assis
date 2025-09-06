/**
 * @file api.js
 * @description Service centralisé pour tous les appels API.
 * Gère automatiquement l'ajout du token d'authentification et tente de le rafraîchir
 * en cas d'expiration (erreur 401).
 */

import { logout, refreshAccessToken, getAccessToken } from './auth';

const API_BASE_URL = "http://127.0.0.1:8000/api/";

/**
 * Fonction générique et unique pour effectuer toutes les requêtes API de l'application.
 * @param {string} endpoint - L'URL de l'endpoint (ex: "backend/api/alertes/").
 * @param {RequestInit} options - Options de la requête (method, headers, body, etc.).
 * @returns {Promise<Response>} La réponse de la requête fetch.
 */
export const apiRequest = async (endpoint, options = {}) => {
  const url = `${API_BASE_URL}${endpoint}`;
  const accessToken = getAccessToken();

  // Si pas de token, l'utilisateur n'est pas authentifié.
  // On ne le redirige pas ici pour permettre des appels publics si besoin.
  // Le hook `useApi` ou le composant appelant pourra gérer la redirection.
  if (!accessToken) {
    // Si l'endpoint n'est pas public, il renverra une erreur 401 que l'on peut attraper plus tard.
    console.warn(`No access token found for request to ${endpoint}.`);
  }
  
  // Configuration des en-têtes
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }

  // Première tentative de requête
  let response = await fetch(url, { ...options, headers });

  // Si la requête échoue avec une erreur 401 (Unauthorized), le token a probablement expiré.
  if (response.status === 401 && accessToken) {
    console.log("Access token expired or invalid, attempting to refresh...");
    
    const wasRefreshed = await refreshAccessToken();

    if (wasRefreshed) {
      console.log("Token refreshed. Retrying the original request...");
      // Le token a été rafraîchi, on récupère le nouveau et on réessaie la requête.
      const newAccessToken = getAccessToken();
      headers['Authorization'] = `Bearer ${newAccessToken}`;
      response = await fetch(url, { ...options, headers });
    } else {
      // Si le rafraîchissement échoue, la fonction `refreshAccessToken` a déjà géré la déconnexion.
      // On propage une erreur pour arrêter le flux de l'application.
      throw new Error("Session expired. Please log in again.");
    }
  }

  return response;
};
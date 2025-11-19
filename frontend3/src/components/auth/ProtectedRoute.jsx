import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { getAccessToken } from '../../services/auth'; // On importe la fonction qui vérifie le token

/**
 * @file ProtectedRoute.jsx
 * @description Un composant qui protège une route.
 * Si l'utilisateur est authentifié (a un token d'accès), il rend le composant enfant.
 * Sinon, il redirige l'utilisateur vers la page de connexion.
 */
const ProtectedRoute = () => {
  const isAuthenticated = !!getAccessToken(); // Renvoie true si le token existe, false sinon

  if (!isAuthenticated) {
    // Redirige vers la page de connexion si l'utilisateur n'est pas authentifié.
    // L'état `replace: true` remplace l'entrée actuelle dans l'historique de navigation,
    // ce qui empêche l'utilisateur de revenir à la page protégée avec le bouton "précédent".
    return <Navigate to="/Connexion" replace />;
  }

  // Si l'utilisateur est authentifié, affiche le contenu de la route demandée.
  // <Outlet /> est un placeholder de react-router-dom pour le composant enfant de la route.
  return <Outlet />;
};

export default ProtectedRoute;
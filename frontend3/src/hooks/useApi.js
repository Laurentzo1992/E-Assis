import { useState, useEffect, useCallback } from 'react';
import { apiRequest } from '../services/api';

/**
 * @file useApi.js
 * @description Hook React personnalisé pour gérer les appels API de manière standardisée.
 * Fournit les états de chargement, d'erreur, de données, une fonction de rafraîchissement
 * ET la fonction pour modifier l'état des données localement.
 */
const useApi = (endpoint, options = {}, dependencies = [], requireAuth = true) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Utilisation de `useCallback` pour éviter de recréer la fonction à chaque rendu
  const fetchData = useCallback(async () => {
    // Ne pas fetch si l'endpoint est null
    if (!endpoint) {
      setData(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await apiRequest(endpoint, options, requireAuth);
      if (!response.ok) {
        let errorData = await response.text();
        try { errorData = JSON.parse(errorData); } catch (jsonError) {}
        throw new Error(`Erreur HTTP: ${response.status} - ${JSON.stringify(errorData)}`);
      }
      const json = await response.json();
      setData(json.results || json);
    } catch (err) {
      console.error(`Error fetching ${endpoint}:`, err);
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [endpoint, JSON.stringify(options), requireAuth, ...dependencies]); // Inclus les dépendances

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const refetch = useCallback(() => {
    fetchData();
  }, [fetchData]);
  
  return { data, loading, error, refetch, setData };
};

export default useApi;
import { useState, useEffect, useCallback } from "react";
import { apiRequest } from "../services/api"; // Notre service API centralisé

/**
 * @file useActiveCompany.js
 * @description Hook React personnalisé pour centraliser la logique de gestion de l'entreprise active.
 * Gère le chargement initial, la sélection d'entreprise, les listes de domaines/secteurs
 * et l'état du profil.
 */

const useActiveCompany = (showCustomAlert) => {
  // --- États de l'entreprise active et de l'onboarding ---
  const [activeCompany, setActiveCompany] = useState(null); // Stocke l'objet complet de l'entreprise active
  const [loading, setLoading] = useState(true); // État de chargement général pour le hook
  const [error, setError] = useState(null); // État d'erreur général pour le hook
  const [showAddEntrepriseModal, setShowAddEntrepriseModal] = useState(false); // Pour l'onboarding initial si pas d'entreprise

  // --- NOUVEAUX ÉTATS pour la gestion de plusieurs entreprises ---
  const [userCompanies, setUserCompanies] = useState([]); // Liste de toutes les entreprises de l'utilisateur

  // --- États pour le profil de l'entreprise (dans la section Profil) ---
  const [profileData, setProfileData] = useState({
    nom: "",
    numeroIdentification: "",
    siret: "",
    adresse: "",
    email: "",
    telephone: "",
    nomRepresentant: "",
    prenomRepresentant: "",
    secteurActivite: null,
    domainesActivite: [],
  });

  // --- États pour les données des listes déroulantes/checkbox (Domaines, Secteurs) ---
  const [apiDomainesActivite, setApiDomainesActivite] = useState([]);
  const [loadingDomaines, setLoadingDomaines] = useState(true);
  const [errorDomaines, setErrorDomaines] = useState(null);

  const [apiSecteursActivite, setApiSecteursActivite] = useState([]);
  const [loadingSecteurs, setLoadingSecteurs] = useState(true);
  const [errorSecteurs, setErrorSecteurs] = useState(null);

  // --- Fonctions de récupération des données de base (Domaines, Secteurs) ---
  const fetchDomaines = useCallback(async () => {
    setLoadingDomaines(true);
    setErrorDomaines(null);
    try {
      const response = await apiRequest("entreprise/domaines/"); // Endpoint relatif
      const data = await response.json();
      setApiDomainesActivite(data.results || data);
    } catch (err) {
      console.error("Erreur lors de la récupération des domaines:", err);
      setErrorDomaines(err);
      setApiDomainesActivite([]);
    } finally {
      setLoadingDomaines(false);
    }
  }, []);

  const fetchSecteurs = useCallback(async () => {
    setLoadingSecteurs(true);
    setErrorSecteurs(null);
    try {
      const response = await apiRequest("entreprise/secteurs/"); // Endpoint relatif
      const data = await response.json();
      setApiSecteursActivite(data.results || data);
    } catch (err) {
      console.error("Erreur lors de la récupération des secteurs:", err);
      setErrorSecteurs(err);
      setApiSecteursActivite([]);
    } finally {
      setLoadingSecteurs(false);
    }
  }, []);

  // --- Fonction pour rafraîchir la liste des entreprises utilisateur ---
  const refetchUserCompanies = useCallback(async () => {
    setError(null);
    try {
      const response = await apiRequest("entreprise/entreprises/");
      const data = await response.json();
      const companies = data.results || data;
      setUserCompanies(companies);

      // Après avoir rafraîchi la liste, on met aussi à jour l'entreprise active
      try {
        const activeCompanyRes = await apiRequest(
          "entreprise/entreprises/active/"
        );
        if (activeCompanyRes.ok) {
          const activeCompanyData = await activeCompanyRes.json();
          setActiveCompany(activeCompanyData);
          // Mettre à jour profileData pour rester cohérent
          setProfileData({
            nom: activeCompanyData.nom || "",
            numeroIdentification: activeCompanyData.numero_identification || "",
            siret: activeCompanyData.siret || "",
            adresse: activeCompanyData.adresse || "",
            email: activeCompanyData.email || "",
            telephone: activeCompanyData.telephone || "",
            nomRepresentant: activeCompanyData.repnom || "",
            prenomRepresentant: activeCompanyData.repprenom || "",
            secteurActivite:
              activeCompanyData.secteurs &&
              activeCompanyData.secteurs.length > 0
                ? activeCompanyData.secteurs[0]
                : null,
            domainesActivite: activeCompanyData.domaines || [],
          });
          setShowAddEntrepriseModal(false);
        } else if (activeCompanyRes.status === 404) {
          // Pas d'entreprise active côté serveur
          setActiveCompany(null);
          if (!companies || companies.length === 0) {
            setShowAddEntrepriseModal(true);
          }
        } else {
          // autre code HTTP -> log
          try {
            const errData = await activeCompanyRes.json();
            console.warn(
              "Erreur lors de la récupération de l'entreprise active:",
              activeCompanyRes.status,
              errData
            );
          } catch (e) {
            console.warn(
              "Erreur lors de la récupération de l'entreprise active, statut:",
              activeCompanyRes.status
            );
          }
        }
      } catch (innerErr) {
        console.error(
          "Erreur lors du fetch de l'entreprise active après refetchUserCompanies:",
          innerErr
        );
      }

      return companies;
    } catch (err) {
      console.error("Erreur lors du rafraîchissement des entreprises:", err);
      setError(err);
      return null;
    }
  }, []);

  // --- Effet initial pour charger les données de base et l'entreprise active ---
  useEffect(() => {
    const initializeData = async () => {
      setLoading(true);
      setError(null);
      try {
        await Promise.all([
          fetchDomaines(),
          fetchSecteurs(),
          refetchUserCompanies(), // Charge les entreprises de l'utilisateur
        ]);

        // Après avoir chargé toutes les entreprises, on tente de récupérer l'active
        const activeCompanyRes = await apiRequest(
          "entreprise/entreprises/active/"
        );
        if (activeCompanyRes.ok) {
          const activeCompanyData = await activeCompanyRes.json();
          setActiveCompany(activeCompanyData);
          // Initialise profileData avec les données de l'entreprise active
          setProfileData({
            nom: activeCompanyData.nom || "",
            numeroIdentification: activeCompanyData.numero_identification || "",
            siret: activeCompanyData.siret || "",
            adresse: activeCompanyData.adresse || "",
            email: activeCompanyData.email || "",
            telephone: activeCompanyData.telephone || "",
            nomRepresentant: activeCompanyData.repnom || "",
            prenomRepresentant: activeCompanyData.repprenom || "",
            secteurActivite:
              activeCompanyData.secteurs &&
              activeCompanyData.secteurs.length > 0
                ? activeCompanyData.secteurs[0]
                : null,
            domainesActivite: activeCompanyData.domaines || [],
          });
          setShowAddEntrepriseModal(false);
        } else if (activeCompanyRes.status === 404) {
          setActiveCompany(null);
          // Si aucune entreprise active et aucune entreprise dans la liste, on ouvre le modal d'ajout
          if (userCompanies.length === 0) {
            // userCompanies est à jour grâce à refetchUserCompanies
            setShowAddEntrepriseModal(true);
          }
        } else {
          // Gérer d'autres erreurs spécifiques si nécessaire
          const errorData = await activeCompanyRes.json();
          throw new Error(
            `Erreur HTTP pour l'entreprise active: ${
              activeCompanyRes.status
            } - ${JSON.stringify(errorData)}`
          );
        }
      } catch (err) {
        console.error(
          "Erreur lors de l'initialisation du tableau de bord:",
          err
        );
        setError(err);
        // Si une erreur survient au chargement initial et qu'il n'y a pas d'entreprise, on propose d'en créer
        if (userCompanies.length === 0) {
          setShowAddEntrepriseModal(true);
        }
      } finally {
        setLoading(false);
      }
    };

    initializeData();
  }, [fetchDomaines, fetchSecteurs, refetchUserCompanies]);

  // Exposer les états et fonctions nécessaires
  return {
    userCompanies,
    setUserCompanies,
    activeCompany,
    setActiveCompany,
    loading,
    error,
    showAddEntrepriseModal,
    setShowAddEntrepriseModal,
    profileData,
    setProfileData,
    apiDomainesActivite,
    loadingDomaines,
    errorDomaines,
    fetchDomaines,
    apiSecteursActivite,
    loadingSecteurs,
    errorSecteurs,
    fetchSecteurs,
    refetchUserCompanies,
  };
};

export default useActiveCompany;

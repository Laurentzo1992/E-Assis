// Dashboard.jsx

import React, { useState, useEffect } from "react";
import { apiRequest, logout, setNavigateInstance } from "../services/auth";
import { useNavigate } from "react-router-dom";
import Select from "react-select";

// Style personnalisé pour React Select
const customStyles = {
  control: (base) => ({
    ...base,
    minHeight: "38px",
    border: "1px solid #dee2e6",
    "&:hover": {
      borderColor: "#86b7fe",
    },
  }),
  multiValue: (base) => ({
    ...base,
    backgroundColor: "#e9ecef",
    borderRadius: "4px",
  }),
  multiValueLabel: (base) => ({
    ...base,
    color: "#495057",
  }),
  multiValueRemove: (base) => ({
    ...base,
    color: "#495057",
    "&:hover": {
      backgroundColor: "#dc3545",
      color: "white",
    },
  }),
  menu: (base) => ({
    ...base,
    // Force le menu à s'afficher au-dessus des autres éléments
    zIndex: 9999,
  }),
};

// Styles spécifiques pour le Select dans le modal
const modalSelectStyles = {
  ...customStyles,
  menuPortal: (base) => ({
    ...base,
    zIndex: 9999,
  }),
};

const Dashboard = () => {
  // --- États généraux du tableau de bord ---
  const [activeSection, setActiveSection] = useState("accueil");
  const [sidebarOpen, setSidebarOpen] = useState(false); // État pour la barre latérale mobile
  const navigate = useNavigate(); // Hook de navigation de React Router

  // --- États de l'entreprise active et de l'onboarding ---
  const [activeCompany, setActiveCompany] = useState(null); // Stocke l'objet complet de l'entreprise active
  const [loadingActiveCompany, setLoadingActiveCompany] = useState(true);
  const [errorActiveCompany, setErrorActiveCompany] = useState(null);
  const [showAddEntrepriseModal, setShowAddEntrepriseModal] = useState(false); // Pour l'onboarding initial si pas d'entreprise

  // --- NOUVEAUX ÉTATS pour la gestion de plusieurs entreprises ---
  const [userCompanies, setUserCompanies] = useState([]); // Liste de toutes les entreprises de l'utilisateur
  const [loadingUserCompanies, setLoadingUserCompanies] = useState(true);
  const [errorUserCompanies, setErrorUserCompanies] = useState(null);

  // --- États pour le formulaire de création/modification d'entreprise ---
  const [addEntrepriseData, setAddEntrepriseData] = useState({
    nom: "",
    numeroIdentification: "",
    siret: "",
    telephone: "",
    email: "",
    nomRepresentant: "", // Mappé à repnom côté backend
    prenomRepresentant: "", // Mappé à repprenom côté backend
    domainesActivite: [], // Stockera les IDs des domaines sélectionnés
    secteurActivite: null, // Stockera l'ID du secteur sélectionné (sera envoyé comme tableau d'IDs)
    adresse: "",
  });

  // --- États pour le profil de l'entreprise (dans la section Profil) ---
  const [profileData, setProfileData] = useState({
    nom: "",
    numeroIdentification: "",
    siret: "",
    adresse: "",
    email: "",
    telephone: "",
    nomRepresentant: "", // Mappé à repnom côté backend
    prenomRepresentant: "", // Mappé à repprenom côté backend
    secteurActivite: null, // Stockera l'objet secteur ou null
    domainesActivite: [], // Stockera un tableau d'objets domaine
  });
  const [loadingProfileUpdate, setLoadingProfileUpdate] = useState(false);
  const [errorProfileUpdate, setErrorProfileUpdate] = useState(null);

  // --- États pour les données des listes déroulantes/checkbox (Domaines, Secteurs) ---
  const [apiDomainesActivite, setApiDomainesActivite] = useState([]);
  const [loadingDomaines, setLoadingDomaines] = useState(true);
  const [errorDomaines, setErrorDomaines] = useState(null);

  const [apiSecteursActivite, setApiSecteursActivite] = useState([]);
  const [loadingSecteurs, setLoadingSecteurs] = useState(true);
  const [errorSecteurs, setErrorSecteurs] = useState(null);

  // --- États pour l'ajout de nouveaux secteurs/domaines via le profil ---
  const [newSecteurNom, setNewSecteurNom] = useState("");
  const [newDomaineLibelle, setNewDomaineLibelle] = useState("");

  // --- États pour les données des sections (Accueil, Veille, Alertes) ---
  const [publications, setPublications] = useState([]);
  const [loadingPublications, setLoadingPublications] = useState(true);
  const [errorPublications, setErrorPublications] = useState(null);

  const [appelsOffresCount, setAppelsOffresCount] = useState(0);
  const [loadingAppelsOffres, setLoadingAppelsOffres] = useState(true);
  const [errorAppelsOffres, setErrorAppelsOffres] = useState(null);

  const [alertesApi, setAlertesApi] = useState([]);
  const [loadingAlertes, setLoadingAlertes] = useState(true);
  const [errorAlertes, setErrorAlertes] = useState(null);

  const [resultatsApi, setResultatsApi] = useState([]);
  const [loadingResultats, setLoadingResultats] = useState(true);
  const [errorResultats, setErrorResultats] = useState(null);

  const [lastReviewDate, setLastReviewDate] = useState("Non disponible");

  // --- États pour les filtres de la section Veille ---
  const [filters, setFilters] = useState({
    domaine: "",
    dateDebut: "",
    dateFin: "",
  });

  // --- État pour le document sélectionné dans le modal de prévisualisation ---
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [showModal, setShowModal] = useState(false);

  // --- NOUVEAUX ÉTATS pour le changement de mot de passe ---
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [loadingPasswordUpdate, setLoadingPasswordUpdate] = useState(false);
  const [errorPasswordUpdate, setErrorPasswordUpdate] = useState(null);

  // Visibilité des champs mdp (profil > changer le mot de passe)
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  // --- États pour le modal d'alerte personnalisé ---
  const [showAlertModal, setShowAlertModal] = useState(false);
  const [alertModalMessage, setAlertModalMessage] = useState("");
  const [alertModalType, setAlertModalType] = useState(""); // 'success' ou 'danger'

  // Fonction utilitaire pour afficher un modal d'alerte personnalisé
  const showCustomAlert = (message, type) => {
    setAlertModalMessage(message);
    setAlertModalType(type);
    setShowAlertModal(true);
  };

  // --- Effet pour passer l'instance de navigation au service d'authentification ---
  useEffect(() => {
    setNavigateInstance(navigate);
  }, [navigate]);

  // --- Fonctions de récupération des données de base (Domaines, Secteurs) ---
  const fetchDomaines = async () => {
    setLoadingDomaines(true);
    setErrorDomaines(null);
    try {
      const response = await apiRequest(
        "http://127.0.0.1:8000/api/entreprise/domaines/"
      );
      if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);
      const data = await response.json();
      setApiDomainesActivite(data.results || data); // Assurez-vous de gérer la pagination si 'results' est présent
    } catch (error) {
      console.error("Erreur lors de la récupération des domaines:", error);
      setErrorDomaines(error);
      setApiDomainesActivite([]);
    } finally {
      setLoadingDomaines(false);
    }
  };

  const fetchSecteurs = async () => {
    setLoadingSecteurs(true);
    setErrorSecteurs(null);
    try {
      const response = await apiRequest(
        "http://127.0.0.1:8000/api/entreprise/secteurs/"
      );
      if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);
      const data = await response.json();
      setApiSecteursActivite(data.results || data); // Assurez-vous de gérer la pagination si 'results' est présent
    } catch (error) {
      console.error("Erreur lors de la récupération des secteurs:", error);
      setErrorSecteurs(error);
      setApiSecteursActivite([]);
    } finally {
      setLoadingSecteurs(false);
    }
  };

  // --- Effet initial pour charger les domaines et secteurs au montage ---
  useEffect(() => {
    fetchDomaines();
    fetchSecteurs();
  }, []);

  // --- NOUVEL EFFET pour récupérer toutes les entreprises de l'utilisateur ---
  useEffect(() => {
    const fetchUserCompanies = async () => {
      setLoadingUserCompanies(true);
      setErrorUserCompanies(null);
      try {
        const response = await apiRequest(
          "http://127.0.0.1:8000/api/entreprise/entreprises/"
        );
        if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);
        const data = await response.json();
        setUserCompanies(data.results || data); // Assurez-vous de gérer la pagination si 'results' est présent
      } catch (error) {
        console.error(
          "Erreur lors de la récupération des entreprises de l'utilisateur:",
          error
        );
        setErrorUserCompanies(error);
        setUserCompanies([]);
      } finally {
        setLoadingUserCompanies(false);
      }
    };
    fetchUserCompanies();
  }, []); // S'exécute une seule fois au montage du composant

  // --- Effet pour gérer l'entreprise active et l'onboarding ---
  useEffect(() => {
    const fetchActiveCompany = async () => {
      // Ne pas tenter de récupérer l'entreprise active si les entreprises de l'utilisateur ne sont pas encore chargées
      if (loadingUserCompanies) return;

      setLoadingActiveCompany(true);
      setErrorActiveCompany(null);
      try {
        const response = await apiRequest(
          "http://127.0.0.1:8000/api/entreprise/entreprises/active/"
        );
        if (response.status === 404) {
          // Aucune entreprise active trouvée
          setActiveCompany(null);
          // Si l'utilisateur n'a aucune entreprise du tout, affiche le modal de création
          if (userCompanies.length === 0) {
            setShowAddEntrepriseModal(true);
          }
          // Si l'utilisateur a des entreprises mais pas d'active, le sélecteur sera visible
        } else if (!response.ok) {
          throw new Error(`Erreur HTTP: ${response.status}`);
        } else {
          const data = await response.json();
          setActiveCompany(data); // Met à jour l'entreprise active
          // Initialiser profileData avec les données de l'entreprise active
          setProfileData({
            nom: data.nom || "",
            numeroIdentification: data.numero_identification || "",
            siret: data.siret || "",
            adresse: data.adresse || "",
            email: data.email || "",
            telephone: data.telephone || "",
            nomRepresentant: data.repnom || "", // Mappé de 'repnom'
            prenomRepresentant: data.repprenom || "", // Mappé de 'repprenom'
            // Mappe 'secteurs' (tableau d'objets) à 'secteurActivite' (un seul objet ou null)
            secteurActivite:
              data.secteurs && data.secteurs.length > 0
                ? data.secteurs[0]
                : null,
            // Mappe 'domaines' (tableau d'objets) à 'domainesActivite'
            domainesActivite: data.domaines || [],
          });
          setShowAddEntrepriseModal(false); // S'assure que le modal est fermé si une entreprise active est trouvée
        }
      } catch (error) {
        console.error(
          "Erreur lors de la récupération de l'entreprise active:",
          error
        );
        setErrorActiveCompany(error);
        // Si erreur et aucune entreprise, propose de créer
        if (userCompanies.length === 0) {
          setShowAddEntrepriseModal(true);
        }
      } finally {
        setLoadingActiveCompany(false);
      }
    };
    fetchActiveCompany();
  }, [loadingUserCompanies, userCompanies]); // Dépend du chargement et de la liste des entreprises utilisateur

  // --- Fonctions de gestion des changements dans les formulaires ---
  const handleAddEntrepriseDomaine = (domaineId) => {
    const isSelected = addEntrepriseData.domainesActivite.includes(domaineId);
    const newDomaines = isSelected
      ? addEntrepriseData.domainesActivite.filter((id) => id !== domaineId)
      : [...addEntrepriseData.domainesActivite, domaineId];
    setAddEntrepriseData({
      ...addEntrepriseData,
      domainesActivite: newDomaines,
    });
  };

  const handleProfileDomaineChange = (domaineId) => {
    const isSelected = profileData.domainesActivite.some(
      (d) => d.id === domaineId
    );
    let updatedDomaines;
    if (isSelected) {
      updatedDomaines = profileData.domainesActivite.filter(
        (d) => d.id !== domaineId
      );
    } else {
      const domaineToAdd = apiDomainesActivite.find((d) => d.id === domaineId);
      updatedDomaines = [...profileData.domainesActivite, domaineToAdd];
    }
    setProfileData({ ...profileData, domainesActivite: updatedDomaines });
  };

  const handleProfileSecteurChange = (e) => {
    const selectedId = e.target.value ? parseInt(e.target.value) : null;
    const newSecteur =
      apiSecteursActivite.find((s) => s.id === selectedId) || null;
    setProfileData({ ...profileData, secteurActivite: newSecteur });
  };

  // --- Fonctions de soumission des formulaires ---
  const handleSubmitAddEntreprise = async (e) => {
    e.preventDefault();
    setLoadingActiveCompany(true);
    try {
      const createResponse = await apiRequest(
        "http://127.0.0.1:8000/api/entreprise/entreprises/",
        {
          method: "POST",
          body: JSON.stringify({
            nom: addEntrepriseData.nom,
            numero_identification: addEntrepriseData.numeroIdentification,
            siret: addEntrepriseData.siret,
            telephone: addEntrepriseData.telephone,
            email: addEntrepriseData.email,
            repnom: addEntrepriseData.nomRepresentant,
            repprenom: addEntrepriseData.prenomRepresentant,
            domaine_ids: addEntrepriseData.domainesActivite,
            secteur_ids: addEntrepriseData.secteurActivite
              ? [addEntrepriseData.secteurActivite]
              : [],
            adresse: addEntrepriseData.adresse,
          }),
        }
      );

      if (!createResponse.ok) {
        const errorData = await createResponse.json();
        throw new Error(
          `Erreur lors de la création de l'entreprise: ${JSON.stringify(
            errorData
          )}`
        );
      }
      const newCompany = await createResponse.json();

      const setActiveResponse = await apiRequest(
        "http://127.0.0.1:8000/api/entreprise/entreprises/set-active/", // Correction de l'URL ici
        {
          method: "POST",
          body: JSON.stringify({ entreprise_id: newCompany.id }),
        }
      );

      if (!setActiveResponse.ok) {
        const errorData = await setActiveResponse.json();
        throw new Error(
          `Erreur lors de la définition de l'entreprise active: ${JSON.stringify(
            errorData
          )}`
        );
      }

      // Met à jour la liste des entreprises de l'utilisateur et l'entreprise active
      setUserCompanies((prevCompanies) => [...prevCompanies, newCompany]);
      setActiveCompany(newCompany);
      setProfileData({
        nom: newCompany.nom || "",
        numeroIdentification: newCompany.numero_identification || "",
        siret: newCompany.siret || "",
        adresse: newCompany.adresse || "",
        email: newCompany.email || "",
        telephone: newCompany.telephone || "",
        nomRepresentant: newCompany.repnom || "",
        prenomRepresentant: newCompany.repprenom || "",
        secteurActivite:
          newCompany.secteurs && newCompany.secteurs.length > 0
            ? newCompany.secteurs[0]
            : null,
        domainesActivite: newCompany.domaines || [],
      });
      showCustomAlert(
        "Entreprise créée et définie comme active avec succès !",
        "success"
      );
    } catch (error) {
      console.error("Erreur lors de la création de l'entreprise:", error);
      showCustomAlert(
        `Échec de la création de l'entreprise: ${error.message}`,
        "danger"
      );
    } finally {
      setLoadingActiveCompany(false);
    }
  };

  const handleSubmitUpdateProfile = async (e) => {
    e.preventDefault();
    if (!activeCompany) {
      showCustomAlert("Aucune entreprise active à mettre à jour.", "danger");
      return;
    }
    setLoadingProfileUpdate(true);
    setErrorProfileUpdate(null);
    try {
      const response = await apiRequest(
        `http://127.0.0.1:8000/api/entreprise/entreprises/${activeCompany.id}/`,
        {
          method: "PUT",
          body: JSON.stringify({
            nom: profileData.nom,
            numero_identification: profileData.numeroIdentification,
            siret: profileData.siret,
            adresse: profileData.adresse,
            email: profileData.email,
            telephone: profileData.telephone,
            repnom: profileData.nomRepresentant,
            repprenom: profileData.prenomRepresentant,
            domaine_ids: profileData.domainesActivite.map((d) => d.id),
            secteur_ids: profileData.secteurActivite
              ? [profileData.secteurActivite.id]
              : [],
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(
          `Erreur lors de la mise à jour du profil : ${JSON.stringify(
            errorData
          )}`
        );
      }
      const updatedCompany = await response.json();
      setActiveCompany(updatedCompany); // Ceci devrait déclencher le rechargement des données dépendantes
      setProfileData({
        nom: updatedCompany.nom || "",
        numeroIdentification: updatedCompany.numero_identification || "",
        siret: updatedCompany.siret || "",
        adresse: updatedCompany.adresse || "",
        email: updatedCompany.email || "",
        telephone: updatedCompany.telephone || "",
        nomRepresentant: updatedCompany.repnom || "",
        prenomRepresentant: updatedCompany.repprenom || "",
        secteurActivite:
          updatedCompany.secteurs && updatedCompany.secteurs.length > 0
            ? updatedCompany.secteurs[0]
            : null,
        domainesActivite: updatedCompany.domaines || [],
      });
      showCustomAlert("Profil mis à jour avec succès !", "success");
    } catch (error) {
      console.error("Erreur lors de la mise à jour du profil :", error);
      setErrorProfileUpdate(error);
      showCustomAlert(`Erreur: ${error.message}`, "danger");
    } finally {
      setLoadingProfileUpdate(false);
    }
  };

  const handleSubmitChangePassword = async (e) => {
    e.preventDefault();
    setErrorPasswordUpdate(null);
    if (newPassword !== confirmNewPassword) {
      showCustomAlert(
        "Les nouveaux mots de passe ne correspondent pas.",
        "danger"
      );
      return;
    }
    if (!currentPassword || !newPassword || !confirmNewPassword) {
      showCustomAlert(
        "Veuillez remplir tous les champs du mot de passe.",
        "danger"
      );
      return;
    }

    setLoadingPasswordUpdate(true);
    try {
      const response = await apiRequest(
        "http://127.0.0.1:8000/api/auth/change-password/",
        {
          method: "POST",
          body: JSON.stringify({
            old_password: currentPassword,
            new_password: newPassword,
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(
          `Erreur lors du changement de mot de passe : ${JSON.stringify(
            errorData
          )}`
        );
      }

      showCustomAlert("Mot de passe mis à jour avec succès !", "success");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmNewPassword("");
    } catch (error) {
      console.error("Erreur lors du changement de mot de passe :", error);
      setErrorPasswordUpdate(error);
      showCustomAlert(
        `Échec du changement de mot de passe : ${error.message}`,
        "danger"
      );
    } finally {
      setLoadingPasswordUpdate(false);
    }
  };

  const handleAddSecteur = async (e) => {
    e.preventDefault();
    try {
      const response = await apiRequest(
        "http://127.0.0.1:8000/api/entreprise/secteurs/",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ nom: newSecteurNom }),
        }
      );
      if (!response.ok) throw new Error(`Erreur: ${response.status}`);
      await fetchSecteurs();
      setNewSecteurNom("");
      showCustomAlert("Secteur ajouté avec succès !", "success");
    } catch (error) {
      console.error("Erreur lors de l'ajout du secteur:", error);
      showCustomAlert(
        `Échec de l'ajout du secteur: ${error.message}`,
        "danger"
      );
    }
  };

  const handleAddDomaine = async (e) => {
    e.preventDefault();
    try {
      const response = await apiRequest(
        "http://127.0.0.1:8000/api/entreprise/domaines/",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ libelle: newDomaineLibelle }),
        }
      );
      if (!response.ok) throw new Error(`Erreur: ${response.status}`);
      await fetchDomaines();
      setNewDomaineLibelle("");
      showCustomAlert("Domaine ajouté avec succès !", "success");
    } catch (error) {
      console.error("Erreur lors de l'ajout du domaine:", error);
      showCustomAlert(
        `Échec de l'ajout du domaine: ${error.message}`,
        "danger"
      );
    }
  };

  // --- Effets pour charger les données des sections (filtrées par entreprise active) ---

  // Effet pour les publications (Veille et Accueil pour la date de dernière revue)
  useEffect(() => {
    const fetchPublications = async () => {
      if (!activeCompany) return; // Ne pas exécuter si aucune entreprise active
      setLoadingPublications(true);
      setErrorPublications(null);
      try {
        const response = await apiRequest(
          "http://127.0.0.1:8000/api/backend/api/publications/"
        );
        if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);
        const data = await response.json();

        // Filtrer les publications par les domaines de l'entreprise active
        const filteredByCompany = (data.results || data).filter(
          (
            pub // Gérer la pagination si 'results' est présent
          ) =>
            pub.domaines.some((d) =>
              activeCompany.domaines.some((ad) => ad.id === d.id)
            )
        );

        const mappedData = filteredByCompany.map((pub) => ({
          id: pub.id,
          titre: pub.titre,
          date_publication: pub.date_publication,
          source: pub.source,
          source_url: pub.source_url, // Assurez-vous que source_url est inclus ici
          type_publication: pub.type_publication,
          numero: pub.numero,
          domaine:
            pub.domaines.length > 0 ? pub.domaines[0].libelle : "Non spécifié",
          full_data: pub,
        }));
        setPublications(mappedData);

        // Mettre à jour la date de dernière revue ici
        if (mappedData.length > 0) {
          const latestDate = mappedData.reduce((maxDate, pub) => {
            const pubDate = new Date(pub.date_publication);
            return pubDate > maxDate ? pubDate : maxDate;
          }, new Date(0));
          setLastReviewDate(latestDate.toLocaleDateString("fr-FR"));
        } else {
          setLastReviewDate("Non disponible");
        }
      } catch (error) {
        console.error(
          "Erreur lors de la récupération des publications:",
          error
        );
        setErrorPublications(error);
      } finally {
        setLoadingPublications(false);
      }
    };

    // Déclenchez la récupération des publications dès que l'entreprise active est là
    if (activeCompany) {
      fetchPublications();
    }
  }, [activeCompany]); // Dépend uniquement de l'entreprise active

  // Effet pour les appels d'offres (Accueil) - Se déclenche quand l'entreprise active change
  useEffect(() => {
    const fetchAppelsOffresCount = async () => {
      if (!activeCompany) return;
      setLoadingAppelsOffres(true);
      setErrorAppelsOffres(null);
      try {
        const response = await apiRequest(
          "http://127.0.0.1:8000/api/backend/api/appels-offres/"
        );
        if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);
        const data = await response.json();

        const currentMonth = new Date().getMonth();
        const currentYear = new Date().getFullYear();

        const count = (data.results || data).filter((appel) => {
          // Gérer la pagination si 'results' est présent
          const pubDate = new Date(appel.publication.date_publication);
          const isRelevantDomain = appel.publication.domaines.some((d) =>
            activeCompany.domaines.some((ad) => ad.id === d.id)
          );
          const isCurrentMonth =
            pubDate.getMonth() === currentMonth &&
            pubDate.getFullYear() === currentYear;
          return isRelevantDomain && isCurrentMonth;
        }).length;

        setAppelsOffresCount(count);
      } catch (error) {
        console.error(
          "Erreur lors de la récupération des appels d'offres:",
          error
        );
        setErrorAppelsOffres(error);
        setAppelsOffresCount(0);
      } finally {
        setLoadingAppelsOffres(false);
      }
    };
    if (activeCompany) {
      fetchAppelsOffresCount();
    }
  }, [activeCompany]);

  // Effet pour les alertes (Alertes & Résultats) - Se déclenche quand l'entreprise active change
  useEffect(() => {
    const fetchAlertes = async () => {
      if (!activeCompany) return;
      setLoadingAlertes(true);
      setErrorAlertes(null);
      try {
        const response = await apiRequest(
          "http://127.0.0.1:8000/api/backend/api/alertes/"
        );
        if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);
        const data = await response.json();

        const filteredAlertes = (data.results || data).filter(
          (
            alerte // Gérer la pagination si 'results' est présent
          ) => alerte.entreprise && alerte.entreprise.id === activeCompany.id
        );
        setAlertesApi(filteredAlertes);
      } catch (error) {
        console.error("Erreur lors de la récupération des alertes:", error);
        setErrorAlertes(error);
      } finally {
        setLoadingAlertes(false);
      }
    };

    if (activeCompany) {
      fetchAlertes();
    }
  }, [activeCompany]);

  // Effet pour les résultats (Alertes & Résultats) - Se déclenche quand la section est "alertes" OU quand l'entreprise active change
  useEffect(() => {
    const fetchResultats = async () => {
      if (!activeCompany) return;
      setLoadingResultats(true);
      setErrorResultats(null);
      try {
        const response = await apiRequest(
          "http://127.0.0.1:8000/api/backend/api/resultats/"
        );
        if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);
        const data = await response.json();

        // Correction de la logique de filtrage pour les résultats
        const filteredResultats = (data.results || data).filter(
          (
            resultat // Gérer la pagination si 'results' est présent
          ) =>
            resultat.entreprise_attributaire &&
            resultat.entreprise_attributaire.id === activeCompany.id
        );
        setResultatsApi(filteredResultats);
      } catch (error) {
        console.error("Erreur lors de la récupération des résultats:", error);
        setErrorResultats(error);
      } finally {
        setLoadingResultats(false);
      }
    };

    // Déclenchez la récupération des résultats si la section est "alertes" ou si l'entreprise active change
    // Ceci garantit que les résultats sont mis à jour même si on ne change pas de section
    if (activeCompany && activeSection === "alertes") {
      // Maintenu pour ne pas surcharger les requêtes si non nécessaire sur d'autres sections
      fetchResultats();
    }
  }, [activeSection, activeCompany]);

  // --- Filtrage des publications pour la section Veille (côté client) ---
  const filteredPublications = publications.filter((pub) => {
    if (filters.domaine && pub.domaine !== filters.domaine) return false;
    const pubDate = new Date(pub.date_publication);
    if (filters.dateDebut) {
      const debutDate = new Date(filters.dateDebut);
      if (pubDate < debutDate) return false;
    }
    if (filters.dateFin) {
      const finDate = new Date(filters.dateFin);
      if (pubDate > finDate) return false;
    }
    return true;
  });

  // --- Rendu des composants UI ---
  const renderSidebar = () => (
    <>
      <div
        className={`sidebar-overlay ${sidebarOpen ? "show" : ""}`}
        onClick={() => setSidebarOpen(false)}
      ></div>

      <div className={`sidebar ${sidebarOpen ? "show" : ""}`}>
        <div className="sidebar-header">
          <h4>VeilleMarches Pro</h4>
          <button
            className="btn-close-sidebar d-md-none"
            onClick={() => setSidebarOpen(false)}
          >
            <svg width="24" height="24" fill="currentColor" viewBox="0 0 16 16">
              <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708z" />
            </svg>
          </button>
        </div>

        <div className="sidebar-content">
          {/* Sélecteur d'entreprise active */}
          <div className="mb-3 text-center">
            {loadingUserCompanies ? (
              <p className="text-muted mb-1">Chargement des entreprises...</p>
            ) : errorUserCompanies ? (
              <p className="text-danger mb-1">
                Erreur de chargement des entreprises:{" "}
                {errorUserCompanies.message}
              </p>
            ) : userCompanies.length > 0 ? (
              <>
                <p className="text-muted mb-1">Entreprise active :</p>
                <select
                  className="form-select mb-2"
                  value={activeCompany ? activeCompany.id : ""}
                  onChange={async (e) => {
                    const selectedId = parseInt(e.target.value);
                    if (selectedId) {
                      try {
                        const response = await apiRequest(
                          "http://127.0.0.1:8000/api/entreprise/entreprises/set-active/",
                          {
                            method: "POST",
                            body: JSON.stringify({ entreprise_id: selectedId }),
                          }
                        );
                        if (!response.ok) {
                          const errorData = await response.json();
                          throw new Error(
                            `Erreur lors de la définition de l'entreprise active: ${JSON.stringify(
                              errorData
                            )}`
                          );
                        }
                        const updatedActiveCompany = await response.json();
                        setActiveCompany(updatedActiveCompany); // Ceci devrait déclencher le rechargement des données dépendantes
                        // Met à jour profileData pour refléter les détails de la nouvelle entreprise active
                        setProfileData({
                          nom: updatedActiveCompany.nom || "",
                          numeroIdentification:
                            updatedActiveCompany.numero_identification || "",
                          siret: updatedActiveCompany.siret || "",
                          adresse: updatedActiveCompany.adresse || "",
                          email: updatedActiveCompany.email || "",
                          telephone: updatedActiveCompany.telephone || "",
                          nomRepresentant: updatedActiveCompany.repnom || "",
                          prenomRepresentant:
                            updatedActiveCompany.repprenom || "",
                          secteurActivite:
                            updatedActiveCompany.secteurs &&
                            updatedActiveCompany.secteurs.length > 0
                              ? updatedActiveCompany.secteurs[0]
                              : null,
                          domainesActivite: updatedActiveCompany.domaines || [],
                        });
                        showCustomAlert(
                          "Entreprise active changée avec succès !",
                          "success"
                        );
                      } catch (error) {
                        console.error(
                          "Erreur lors du changement d'entreprise active:",
                          error
                        );
                        showCustomAlert(
                          `Échec du changement d'entreprise active: ${error.message}`,
                          "danger"
                        );
                      }
                    }
                  }}
                >
                  <option value="">Sélectionner une entreprise</option>
                  {userCompanies.map((company) => (
                    <option key={company.id} value={company.id}>
                      {company.nom}
                    </option>
                  ))}
                </select>
              </>
            ) : (
              <p className="text-muted mb-1">Aucune entreprise trouvée.</p>
            )}
          </div>

          {/* Bouton pour ajouter une nouvelle entreprise - toujours visible si l'utilisateur est connecté */}
          <button
            className="btn btn-cta w-100 mb-4"
            onClick={() => setShowAddEntrepriseModal(true)}
          >
            <svg
              width="16"
              height="16"
              fill="currentColor"
              className="me-2"
              viewBox="0 0 16 16"
            >
              <path d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4z" />
            </svg>
            Ajouter une entreprise
          </button>

          <nav className="sidebar-nav">
            <a
              href="#"
              className={`nav-link ${
                activeSection === "accueil" ? "active" : ""
              }`}
              onClick={() => {
                setActiveSection("accueil");
                setSidebarOpen(false);
              }}
            >
              <svg
                width="16"
                height="16"
                fill="currentColor"
                className="me-2"
                viewBox="0 0 16 16"
              >
                <path d="m8 3.293 6 6V13.5a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 2 13.5V9.293l6-6zm5-.793V6l-2-2V2.5a.5.5 0 0 1 .5-.5h1a.5.5 0 0 1 .5.5z" />
                <path d="M7.293 1.5a1 1 0 0 1 1.414 0l6.647 6.646a.5.5 0 0 1-.708.708L8 2.207 1.354 8.854a.5.5 0 1 1-.708-.708L7.293 1.5z" />
              </svg>
              Accueil
            </a>
            <a
              href="#"
              className={`nav-link ${
                activeSection === "veille" ? "active" : ""
              }`}
              onClick={() => {
                setActiveSection("veille");
                setSidebarOpen(false);
              }}
            >
              <svg
                width="16"
                height="16"
                fill="currentColor"
                className="me-2"
                viewBox="0 0 16 16"
              >
                <path d="M14 4.5V14a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V2a2 2 0 0 1 2-2h5.5L14 4.5zM9.5 3A1.5 1.5 0 0 0 11 4.5h2V14a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1h5.5v2z" />
              </svg>
              Veille & Documents
            </a>
            <a
              href="#"
              className={`nav-link ${
                activeSection === "alertes" ? "active" : ""
              }`}
              onClick={() => {
                setActiveSection("alertes");
                setSidebarOpen(false);
              }}
            >
              <svg
                width="16"
                height="16"
                fill="currentColor"
                className="me-2"
                viewBox="0 0 16 16"
              >
                <path d="M8 16a2 2 0 0 0 2-2H6a2 2 0 0 0 2 2zM8 1.918l-.797.161A4.002 4.002 0 0 0 4 6c0 .628-.134 2.197-.459 3.742-.16.767-.376 1.566-.663 2.258h10.244c-.287-.692-.502-1.49-.663-2.258C12.134 8.197 12 6.628 12 6a4.002 4.002 0 0 0-3.203-3.92L8 1.917zM14.22 12c.223.447.481.801.78 1H1c.299-.199.557-.553.78-1C2.68 10.2 3 6.88 3 6c0-2.42 1.72-4.44 4.005-4.901a1 1 0 1 1 1.99 0A5.002 5.002 0 0 1 13 6c0 .88.32 4.2 1.22 6z" />
              </svg>
              Alertes & Résultats
            </a>
            <a
              href="#"
              className={`nav-link ${
                activeSection === "profil" ? "active" : ""
              }`}
              onClick={() => {
                setActiveSection("profil");
                setSidebarOpen(false);
              }}
            >
              <svg
                width="16"
                height="16"
                fill="currentColor"
                className="me-2"
                viewBox="0 0 16 16"
              >
                <path d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm2-3a2 2 0 1 1-4 0 2 2 0 0 1 4 0zm4 8c0 1-1 1-1 1H3s-1 0-1-1 1-4 6-4 6 3 6 4zm-1-.004c-.001-.246-.154-.986-.832-1.664C11.516 10.68 10.289 10 8 10c-2.29 0-3.516.68-4.168 1.332-.678.678-.83 1.418-.832 1.664h10z" />
              </svg>
              Profil
            </a>
          </nav>
        </div>

        <div className="sidebar-footer">
          <button className="btn btn-outline-light w-100" onClick={logout}>
            <svg
              width="16"
              height="16"
              fill="currentColor"
              className="me-2"
              viewBox="0 0 16 16"
            >
              <path
                fillRule="evenodd"
                d="M10 12.5a.5.5 0 0 1-.5.5h-8a.5.5 0 0 1-.5-.5v-9a.5.5 0 0 1 .5-.5h8a.5.5 0 0 1 .5.5v2a.5.5 0 0 0 1 0v-2A1.5 1.5 0 0 0 9.5 2h-8A1.5 1.5 0 0 0 0 3.5v9A1.5 1.5 0 0 0 1.5 14h8a1.5 1.5 0 0 0 1.5-1.5v-2a.5.5 0 0 0-1 0v2z"
              />
              <path
                fillRule="evenodd"
                d="M15.854 8.354a.5.5 0 0 0 0-.708l-3-3a.5.5 0 0 0-.708.708L14.293 7.5H5.5a.5.5 0 0 0 0 1h8.793l-2.147 2.146a.5.5 0 0 0 .708.708l3-3z"
              />
            </svg>
            Déconnexion
          </button>
        </div>
      </div>
    </>
  );

  const renderMobileHeader = () => (
    <div className="mobile-header d-md-none">
      <button className="btn-menu" onClick={() => setSidebarOpen(true)}>
        <svg width="24" height="24" fill="currentColor" viewBox="0 0 16 16">
          <path
            fillRule="evenodd"
            d="M2.5 12a.5.5 0 0 1 .5-.5h10a.5.5 0 0 1 0 1H3a.5.5 0 0 1-.5-.5zm0-4a.5.5 0 0 1 .5-.5h10a.5.5 0 0 1 0 1H3a.5.5 0 0 1-.5-.5zm0-4a.5.5 0 0 1 .5-.5h10a.5.5 0 0 1 0 1H3a.5.5 0 0 1-.5-.5z"
          />
        </svg>
      </button>
      <h5 className="m-0">VeilleMarches Pro</h5>
    </div>
  );

  const renderAccueil = () => (
    <div className="main-content">
      <div className="content-header">
        <h2>Tableau de bord</h2>
        <p className="text-muted">Vue d'overview de votre activité de veille</p>
      </div>

      {loadingActiveCompany ? (
        <p>Chargement des données de l'entreprise...</p>
      ) : errorActiveCompany ? (
        <div className="alert alert-danger">
          Erreur lors du chargement de l'entreprise :{" "}
          {errorActiveCompany.message}. Veuillez recharger la page.
        </div>
      ) : !activeCompany ? (
        <div className="alert alert-info">
          Veuillez créer votre entreprise pour accéder au tableau de bord.
        </div>
      ) : (
        <>
          <div className="row mb-4">
            <div className="col-lg-4 col-md-6 mb-3">
              <div className="card kpi-card">
                <div className="card-body text-center">
                  {loadingAppelsOffres ? (
                    <p>Chargement...</p>
                  ) : errorAppelsOffres ? (
                    <p className="text-danger">
                      Erreur de chargement: {errorAppelsOffres.message}
                    </p>
                  ) : (
                    <h3 className="card-title">{appelsOffresCount}</h3>
                  )}
                  <p className="card-text">
                    Appels d'offres ce mois (pour {activeCompany.nom})
                  </p>
                </div>
              </div>
            </div>
            <div className="col-lg-4 col-md-6 mb-3">
              <div className="card kpi-card">
                <div className="card-body text-center">
                  {loadingAlertes ? (
                    <p>Chargement...</p>
                  ) : errorAlertes ? (
                    <p className="text-danger">
                      Erreur de chargement: {errorAlertes.message}
                    </p>
                  ) : (
                    <h3 className="card-title">{alertesApi.length}</h3>
                  )}
                  <p className="card-text">
                    Alertes non lues (pour {activeCompany.nom})
                  </p>
                </div>
              </div>
            </div>
            <div className="col-lg-4 col-md-6 mb-3">
              <div className="card kpi-card">
                <div className="card-body text-center">
                  {/* Affichage de la date de dernière revue importée */}
                  <h3 className="card-title">{lastReviewDate}</h3>
                  <p className="card-text">
                    Date de la dernière revue importée
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h5 className="mb-0">Actions rapides</h5>
            </div>
            <div className="card-body">
              <div className="row">
                <div className="col-lg-4 col-md-6 mb-2">
                  <button
                    className="btn btn-cta w-100 "
                    onClick={() => setActiveSection("veille")}
                  >
                    Rechercher manuellement
                  </button>
                </div>
                <div className="col-lg-4 col-md-6 mb-2">
                  <button
                    className="btn btn-cta w-100"
                    onClick={() => setActiveSection("profil")}
                  >
                    Modifier les paramètres du compte
                  </button>
                </div>
                <div className="col-lg-4 col-md-6 mb-2">
                  <button
                    className="btn btn-cta w-100"
                    onClick={() => setActiveSection("alertes")}
                  >
                    Voir dernières alertes
                  </button>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );

  const renderVeille = () => (
    <div className="main-content">
      <div className="content-header">
        <h2>Veille & Documents</h2>
        <p className="text-muted">Consultation et gestion des publications</p>
      </div>

      {loadingActiveCompany ? (
        <p>Chargement des données de l'entreprise...</p>
      ) : errorActiveCompany ? (
        <div className="alert alert-danger">
          Erreur lors du chargement de l'entreprise :{" "}
          {errorActiveCompany.message}. Veuillez recharger la page.
        </div>
      ) : !activeCompany ? (
        <div className="alert alert-info">
          Veuillez créer votre entreprise pour accéder aux publications
          pertinentes.
        </div>
      ) : (
        <>
          {/* Filtres */}
          <div className="card mb-4">
            <div className="card-header">
              <h5 className="mb-0">Filtres</h5>
            </div>
            <div className="card-body">
              <div className="row">
                <div className="col-lg-4 col-md-6 mb-3">
                  <label className="form-label">Domaine</label>
                  {loadingDomaines ? (
                    <p>Chargement des domaines...</p>
                  ) : errorDomaines ? (
                    <p className="text-danger">
                      Erreur de chargement des domaines: {errorDomaines.message}
                    </p>
                  ) : (
                    <select
                      className="form-select"
                      value={filters.domaine}
                      onChange={(e) =>
                        setFilters({ ...filters, domaine: e.target.value })
                      }
                    >
                      <option value="">Tous les domaines</option>
                      {apiDomainesActivite.map((domaine) => (
                        <option key={domaine.id} value={domaine.libelle}>
                          {domaine.libelle}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
                <div className="col-lg-4 col-md-6 mb-3">
                  <label className="form-label">Date début</label>
                  <input
                    type="date"
                    className="form-control"
                    value={filters.dateDebut}
                    onChange={(e) =>
                      setFilters({ ...filters, dateDebut: e.target.value })
                    }
                  />
                </div>
                <div className="col-lg-4 col-md-6 mb-3">
                  <label className="form-label">Date fin</label>
                  <input
                    type="date"
                    className="form-control"
                    value={filters.dateFin}
                    onChange={(e) =>
                      setFilters({ ...filters, dateFin: e.target.value })
                    }
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="card mb-4">
            <div className="card-header">
              <h5 className="mb-0">
                Publications récentes (pour {activeCompany.nom})
              </h5>
            </div>
            <div className="card-body">
              {loadingPublications ? (
                <p>Chargement des publications...</p>
              ) : errorPublications ? (
                <div className="alert alert-danger">
                  Erreur lors du chargement des publications :{" "}
                  {errorPublications.message}
                  <br />
                  Veuillez vérifier votre connexion ou vous reconnecter si
                  l'erreur persiste.
                </div>
              ) : filteredPublications.length === 0 ? (
                <p>
                  Aucune publication trouvée correspondant aux domaines de votre
                  entreprise.
                </p>
              ) : (
                <div
                  className="table-responsive"
                  style={{
                    height: "400px",
                    overflowY: "auto",
                    display: "flex",
                    flexDirection: "column",
                    border: "1px solid #dee2e6",
                    borderRadius: "4px",
                  }}
                >
                  <table
                    className="table table-hover"
                    style={{ marginBottom: "0px", background: "white" }}
                  >
                    <thead>
                      <tr>
                        <th>Date de publication</th>
                        <th>Titre</th>
                        <th>Type de publication</th>
                        <th>Numéro</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredPublications.slice(0, 20).map((pub) => (
                        <tr key={pub.id} style={{ cursor: "pointer" }}>
                          <td>
                            <div className="d-none d-md-block">
                              {pub.date_publication}
                            </div>
                            <div className="d-md-none small">
                              {pub.date_publication}
                            </div>
                          </td>
                          <td>
                            <div className="fw-bold">{pub.titre}</div>
                          </td>
                          <td>{pub.type_publication}</td>
                          <td>{pub.numero}</td>
                          <td>
                            <button
                              type="button"
                              className="btn btn-sm btn-outline-primary"
                              onClick={() => {
                                setSelectedDocument(pub.full_data);
                                setShowModal(true);
                              }}
                            >
                              Voir
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );

  const renderAlertes = () => (
    <div className="main-content">
      <div className="content-header">
        <h2>Alertes & Résultats</h2>
        <p className="text-muted">
          Suivi des notifications et résultats de candidatures
        </p>
      </div>
      {loadingActiveCompany ? (
        <p>Chargement des données de l'entreprise...</p>
      ) : errorActiveCompany ? (
        <div className="alert alert-danger">
          Erreur lors du chargement de l'entreprise :{" "}
          {errorActiveCompany.message}. Veuillez recharger la page.
        </div>
      ) : !activeCompany ? (
        <div className="alert alert-info">
          Veuillez créer votre entreprise pour accéder à vos alertes et
          résultats.
        </div>
      ) : (
        <div className="row">
          <div className="col-lg-8 mb-4">
            <div className="card">
              <div className="card-header">
                <h5 className="mb-0">
                  Alertes non traitées (pour {activeCompany.nom})
                </h5>
              </div>
              <div className="card-body">
                {loadingAlertes ? (
                  <p>Chargement des alertes...</p>
                ) : errorAlertes ? (
                  <div className="alert alert-danger">
                    Erreur lors du chargement des alertes :{" "}
                    {errorAlertes.message}
                  </div>
                ) : alertesApi.length === 0 ? (
                  <p>Aucune alerte trouvée pour votre entreprise.</p>
                ) : (
                  [...alertesApi]
                    .sort(
                      (a, b) =>
                        new Date(b.date_alerte) - new Date(a.date_alerte)
                    )
                    .slice(0, 5)
                    .map((alerte) => (
                      <div
                        key={alerte.id}
                        className="d-flex flex-column flex-sm-row justify-content-between align-items-start align-items-sm-center border-bottom py-2"
                      >
                        <div className="mb-2 mb-sm-0">
                          <h6 className="mb-1">
                            {alerte.type_alerte}: {alerte.contenu_alerte}
                          </h6>
                          <small className="text-muted">
                            {new Date(alerte.date_alerte).toLocaleDateString(
                              "fr-FR"
                            )}{" "}
                            - Canal: {alerte.canal_alerte}
                          </small>
                          {alerte.publication && (
                            <small className="text-muted d-block mt-1">
                              Publication: {alerte.publication.titre}
                            </small>
                          )}
                          {alerte.entreprise && (
                            <small className="text-muted d-block">
                              Entreprise: {alerte.entreprise.nom}
                            </small>
                          )}
                        </div>
                      </div>
                    ))
                )}
              </div>
            </div>
          </div>
          <div className="col-lg-4">
            <div className="card">
              <div className="card-header">
                <h5 className="mb-0">
                  Résultats récents (pour {activeCompany.nom})
                </h5>
              </div>
              <div className="card-body">
                {loadingResultats ? (
                  <p>Chargement des résultats...</p>
                ) : errorResultats ? (
                  <div className="alert alert-danger">
                    Erreur lors du chargement des résultats :{" "}
                    {errorResultats.message}
                  </div>
                ) : resultatsApi.length === 0 ? (
                  <p>Aucun résultat trouvé pour votre entreprise.</p>
                ) : (
                  [...resultatsApi]
                    .sort(
                      (a, b) =>
                        new Date(b.date_attribution) -
                        new Date(a.date_attribution)
                    )
                    .slice(0, 5)
                    .map((resultat) => (
                      <div key={resultat.marche.id} className="mb-3">
                        <div className="d-flex justify-content-between align-items-center mb-1">
                          <span className="fw-bold">
                            {resultat.marche.publication.titre}
                          </span>
                          <span
                            className={`badge ${
                              resultat.entreprise_attributaire &&
                              resultat.entreprise_attributaire.id ===
                                activeCompany.id
                                ? "bg-success"
                                : "bg-danger"
                            }`}
                          >
                            {resultat.entreprise_attributaire &&
                            resultat.entreprise_attributaire.id ===
                              activeCompany.id
                              ? "Retenu"
                              : "Non retenu"}
                          </span>
                        </div>
                        <small className="text-muted d-block">
                          Résultat publié le{" "}
                          {new Date(
                            resultat.date_attribution
                          ).toLocaleDateString("fr-FR")}
                        </small>
                        <small className="text-muted d-block">
                          Attributaire:{" "}
                          {resultat.entreprise_attributaire
                            ? resultat.entreprise_attributaire.nom
                            : "N/A"}
                        </small>
                        <small className="text-muted d-block">
                          Montant attribué: {resultat.montant_attribue}
                        </small>
                        <a
                          href={resultat.marche.publication.source}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="small"
                        >
                          Voir l'annonce officielle
                        </a>
                      </div>
                    ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  const renderProfil = () => (
    <div className="main-content">
      <div className="content-header">
        <h2>Profil</h2>
        <p className="text-muted">Gestion des informations de l'entreprise</p>
      </div>

      {loadingActiveCompany ? (
        <p>Chargement du profil de l'entreprise...</p>
      ) : errorActiveCompany ? (
        <div className="alert alert-danger">
          Erreur lors du chargement du profil : {errorActiveCompany.message}.
          Veuillez recharger la page.
        </div>
      ) : !activeCompany ? (
        <div className="alert alert-info">
          Veuillez créer votre entreprise pour gérer votre profil.
        </div>
      ) : (
        <div className="row">
          <div className="col-lg-8 mb-4">
            <div className="card mb-4">
              <div className="card-header">
                <h5 className="mb-0">Informations de l'entreprise</h5>
              </div>
              <div className="card-body">
                <form onSubmit={handleSubmitUpdateProfile}>
                  <div className="row">
                    <div className="col-md-6 mb-3">
                      <label className="form-label">Nom de l'entreprise</label>
                      <input
                        type="text"
                        className="form-control"
                        value={profileData.nom || ""}
                        onChange={(e) =>
                          setProfileData({
                            ...profileData,
                            nom: e.target.value,
                          })
                        }
                      />
                    </div>
                    <div className="col-md-6 mb-3">
                      <label className="form-label">
                        Numéro d'identification
                      </label>
                      <input
                        type="text"
                        className="form-control"
                        value={profileData.numeroIdentification || ""}
                        onChange={(e) =>
                          setProfileData({
                            ...profileData,
                            numeroIdentification: e.target.value,
                          })
                        }
                      />
                    </div>
                  </div>
                  <div className="row">
                    <div className="col-md-6 mb-3">
                      <label className="form-label">SIRET</label>
                      <input
                        type="text"
                        className="form-control"
                        value={profileData.siret || ""}
                        onChange={(e) =>
                          setProfileData({
                            ...profileData,
                            siret: e.target.value,
                          })
                        }
                      />
                    </div>
                    <div className="col-md-6 mb-3">
                      <label className="form-label">Nom du représentant</label>
                      <input
                        type="text"
                        className="form-control"
                        value={profileData.nomRepresentant || ""}
                        onChange={(e) =>
                          setProfileData({
                            ...profileData,
                            nomRepresentant: e.target.value,
                          })
                        }
                      />
                    </div>
                  </div>
                  <div className="row">
                    <div className="col-md-6 mb-3">
                      <label className="form-label">
                        Prénom du représentant
                      </label>
                      <input
                        type="text"
                        className="form-control"
                        value={profileData.prenomRepresentant || ""}
                        onChange={(e) =>
                          setProfileData({
                            ...profileData,
                            prenomRepresentant: e.target.value,
                          })
                        }
                      />
                    </div>
                    <div className="col-md-6 mb-3">
                      <label className="form-label">Adresse</label>
                      <input
                        type="text"
                        className="form-control"
                        value={profileData.adresse || ""}
                        onChange={(e) =>
                          setProfileData({
                            ...profileData,
                            adresse: e.target.value,
                          })
                        }
                      />
                    </div>
                  </div>
                  <div className="row">
                    <div className="col-md-6 mb-3">
                      <label className="form-label">Email</label>
                      <input
                        type="email"
                        className="form-control"
                        value={profileData.email || ""}
                        onChange={(e) =>
                          setProfileData({
                            ...profileData,
                            email: e.target.value,
                          })
                        }
                      />
                    </div>
                    <div className="col-md-6 mb-3">
                      <label className="form-label">Téléphone (WhAtsApp)</label>
                      <input
                        type="tel"
                        className="form-control"
                        value={profileData.telephone || ""}
                        onChange={(e) =>
                          setProfileData({
                            ...profileData,
                            telephone: e.target.value,
                          })
                        }
                      />
                    </div>
                  </div>

                  {/* Secteur d'activité */}
                  <div className="mb-3">
                    <label className="form-label">Secteur d'activité</label>
                    {loadingSecteurs ? (
                      <p>Chargement des secteurs...</p>
                    ) : errorSecteurs ? (
                      <p className="text-danger">
                        Erreur de chargement des secteurs:{" "}
                        {errorSecteurs.message}
                      </p>
                    ) : (
                      <select
                        className="form-select"
                        value={
                          profileData.secteurActivite
                            ? profileData.secteurActivite.id
                            : ""
                        }
                        onChange={handleProfileSecteurChange}
                      >
                        <option value="">Sélectionner un secteur</option>
                        {apiSecteursActivite.map((secteur) => (
                          <option key={secteur.id} value={secteur.id}>
                            {secteur.nom}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>

                  {/* Domaines d'activité */}
                  <div className="mb-3">
                    <label className="form-label">Domaines d'activité</label>
                    {loadingDomaines ? (
                      <p>Chargement des domaines...</p>
                    ) : errorDomaines ? (
                      <p className="text-danger">
                        Erreur de chargement des domaines:{" "}
                        {errorDomaines.message}
                      </p>
                    ) : (
                      <Select
                        isMulti
                        styles={customStyles}
                        options={apiDomainesActivite.map((domaine) => ({
                          value: domaine.id,
                          label: domaine.libelle,
                        }))}
                        value={profileData.domainesActivite.map((domaine) => ({
                          value: domaine.id,
                          label: domaine.libelle,
                        }))}
                        onChange={(selectedOptions) => {
                          const selectedIds = selectedOptions
                            ? selectedOptions.map((opt) => opt.value)
                            : [];
                          setProfileData({
                            ...profileData,
                            domainesActivite: apiDomainesActivite.filter((d) =>
                              selectedIds.includes(d.id)
                            ),
                          });
                        }}
                        placeholder="Sélectionnez un ou plusieurs domaines..."
                        noOptionsMessage={() => "Aucun domaine disponible"}
                        classNamePrefix="react-select"
                      />
                    )}
                  </div>

                  <button
                    type="submit"
                    className="btn btn-cta"
                    disabled={loadingProfileUpdate}
                  >
                    {loadingProfileUpdate
                      ? "Enregistrement..."
                      : "Enregistrer les modifications"}
                  </button>
                  {errorProfileUpdate && (
                    <p className="text-danger mt-2">
                      Erreur: {errorProfileUpdate.message}
                    </p>
                  )}
                </form>
              </div>
            </div>
          </div>
          <div className="col-lg-4">
            <div className="card">
              <div className="card-header">
                <h5 className="mb-0">Changer le mot de passe</h5>
              </div>
              <div className="card-body">
                <form onSubmit={handleSubmitChangePassword}>
                  <div className="mb-3">
                    <label className="form-label">Mot de passe actuel</label>
                    <div className="input-group">
                      <input
                        type={showCurrentPassword ? "text" : "password"}
                        className="form-control"
                        value={currentPassword}
                        onChange={(e) => setCurrentPassword(e.target.value)}
                        required
                      />
                      <button
                        type="button"
                        className="btn btn-outline-secondary"
                        onClick={() => setShowCurrentPassword((v) => !v)}
                      >
                        <i
                          className={`bi ${
                            showCurrentPassword ? "bi-eye-slash" : "bi-eye"
                          }`}
                        ></i>
                      </button>
                    </div>
                  </div>
                  <div className="mb-3">
                    <label className="form-label">Nouveau mot de passe</label>
                    <div className="input-group">
                      <input
                        type={showNewPassword ? "text" : "password"}
                        className="form-control"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        required
                      />
                      <button
                        type="button"
                        className="btn btn-outline-secondary"
                        onClick={() => setShowNewPassword((v) => !v)}
                      >
                        <i
                          className={`bi ${
                            showNewPassword ? "bi-eye-slash" : "bi-eye"
                          }`}
                        ></i>
                      </button>
                    </div>
                  </div>
                  <div className="mb-3">
                    <label className="form-label">
                      Confirmer le nouveau mot de passe
                    </label>
                    <div className="input-group">
                      <input
                        type={showConfirmPassword ? "text" : "password"}
                        className="form-control"
                        value={confirmNewPassword}
                        onChange={(e) => setConfirmNewPassword(e.target.value)}
                        required
                      />
                      <button
                        type="button"
                        className="btn btn-outline-secondary"
                        onClick={() => setShowConfirmPassword((v) => !v)}
                      >
                        <i
                          className={`bi ${
                            showConfirmPassword ? "bi-eye-slash" : "bi-eye"
                          }`}
                        ></i>
                      </button>
                    </div>
                  </div>
                  <button
                    type="submit"
                    className="btn btn-cta w-100"
                    disabled={loadingPasswordUpdate}
                  >
                    {loadingPasswordUpdate
                      ? "Mise à jour..."
                      : "Mettre à jour le mot de passe"}
                  </button>
                  {errorPasswordUpdate && (
                    <p className="text-danger mt-2">
                      Erreur: {errorPasswordUpdate.message}
                    </p>
                  )}
                </form>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  const renderAddEntrepriseModal = () => (
    <div
      className={`modal fade ${showAddEntrepriseModal ? "show" : ""}`}
      style={{ display: showAddEntrepriseModal ? "block" : "none" }}
      tabIndex="-1"
      onClick={() => setShowAddEntrepriseModal(false)}
    >
      <div className="modal-dialog modal-lg">
        <div className="modal-content" onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <h5 className="modal-title">Créer votre entreprise</h5>
          </div>
          <form onSubmit={handleSubmitAddEntreprise}>
            <div className="modal-body">
              <p className="text-muted">
                Veuillez renseigner les informations de votre entreprise pour
                commencer.
              </p>
              <div className="row">
                <div className="col-md-6 mb-3">
                  <label className="form-label">Nom de l'entreprise *</label>
                  <input
                    type="text"
                    className="form-control"
                    value={addEntrepriseData.nom}
                    onChange={(e) =>
                      setAddEntrepriseData({
                        ...addEntrepriseData,
                        nom: e.target.value,
                      })
                    }
                    required
                  />
                </div>
                <div className="col-md-6 mb-3">
                  <label className="form-label">
                    Numéro d'identification *
                  </label>
                  <input
                    type="text"
                    className="form-control"
                    value={addEntrepriseData.numeroIdentification}
                    onChange={(e) =>
                      setAddEntrepriseData({
                        ...addEntrepriseData,
                        numeroIdentification: e.target.value,
                      })
                    }
                    required
                  />
                </div>
              </div>
              <div className="row">
                <div className="col-md-6 mb-3">
                  <label className="form-label">SIRET *</label>
                  <input
                    type="text"
                    className="form-control"
                    value={addEntrepriseData.siret}
                    onChange={(e) =>
                      setAddEntrepriseData({
                        ...addEntrepriseData,
                        siret: e.target.value,
                      })
                    }
                    required
                  />
                </div>
                <div className="col-md-6 mb-3">
                  <label className="form-label">Téléphone (WhAtsApp)</label>
                  <input
                    type="tel"
                    className="form-control"
                    value={addEntrepriseData.telephone}
                    onChange={(e) =>
                      setAddEntrepriseData({
                        ...addEntrepriseData,
                        telephone: e.target.value,
                      })
                    }
                  />
                </div>
              </div>
              <div className="row">
                <div className="col-md-6 mb-3">
                  <label className="form-label">Email</label>
                  <input
                    type="email"
                    className="form-control"
                    value={addEntrepriseData.email}
                    onChange={(e) =>
                      setAddEntrepriseData({
                        ...addEntrepriseData,
                        email: e.target.value,
                      })
                    }
                  />
                </div>
                <div className="col-md-6 mb-3">
                  <label className="form-label">Nom du représentant</label>
                  <input
                    type="text"
                    className="form-control"
                    value={addEntrepriseData.nomRepresentant}
                    onChange={(e) =>
                      setAddEntrepriseData({
                        ...addEntrepriseData,
                        nomRepresentant: e.target.value,
                      })
                    }
                  />
                </div>
              </div>
              <div className="row">
                <div className="col-md-6 mb-3">
                  <label className="form-label">Prénom du représentant</label>
                  <input
                    type="text"
                    className="form-control"
                    value={addEntrepriseData.prenomRepresentant}
                    onChange={(e) =>
                      setAddEntrepriseData({
                        ...addEntrepriseData,
                        prenomRepresentant: e.target.value,
                      })
                    }
                  />
                </div>
                <div className="col-md-6 mb-3">
                  <label className="form-label">Adresse</label>
                  <input
                    type="text"
                    className="form-control"
                    value={addEntrepriseData.adresse}
                    onChange={(e) =>
                      setAddEntrepriseData({
                        ...addEntrepriseData,
                        adresse: e.target.value,
                      })
                    }
                  />
                </div>
              </div>

              <div className="mb-3">
                <label className="form-label">Secteur d'activité *</label>
                {loadingSecteurs ? (
                  <p>Chargement des secteurs...</p>
                ) : errorSecteurs ? (
                  <p className="text-danger">
                    Erreur de chargement des secteurs: {errorSecteurs.message}
                  </p>
                ) : (
                  <select
                    className="form-select"
                    value={addEntrepriseData.secteurActivite || ""}
                    onChange={(e) =>
                      setAddEntrepriseData({
                        ...addEntrepriseData,
                        secteurActivite: e.target.value
                          ? parseInt(e.target.value)
                          : null,
                      })
                    }
                    required
                  >
                    <option value="">Sélectionner un secteur</option>
                    {apiSecteursActivite.map((secteur) => (
                      <option key={secteur.id} value={secteur.id}>
                        {secteur.nom}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div className="mb-3">
                <label className="form-label">Domaines d'activité *</label>
                {loadingDomaines ? (
                  <p>Chargement des domaines...</p>
                ) : errorDomaines ? (
                  <p className="text-danger">
                    Erreur de chargement des domaines: {errorDomaines.message}
                  </p>
                ) : (
                  <Select
                    isMulti
                    styles={modalSelectStyles}
                    options={apiDomainesActivite.map((domaine) => ({
                      value: domaine.id,
                      label: domaine.libelle,
                    }))}
                    value={addEntrepriseData.domainesActivite
                      .map((id) => {
                        const domaine = apiDomainesActivite.find(
                          (d) => d.id === id
                        );
                        return domaine
                          ? { value: id, label: domaine.libelle }
                          : null;
                      })
                      .filter(Boolean)}
                    onChange={(selectedOptions) => {
                      setAddEntrepriseData({
                        ...addEntrepriseData,
                        domainesActivite: selectedOptions
                          ? selectedOptions.map((opt) => opt.value)
                          : [],
                      });
                    }}
                    placeholder="Sélectionnez un ou plusieurs domaines..."
                    noOptionsMessage={() => "Aucun domaine disponible"}
                    classNamePrefix="react-select"
                    menuPortalTarget={document.body}
                    menuPosition="fixed"
                  />
                )}
              </div>
            </div>
            <div className="modal-footer">
              <button
                type="submit"
                className="btn btn-cta"
                disabled={loadingActiveCompany}
              >
                {loadingActiveCompany ? "Création..." : "Créer l'entreprise"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );

  const renderModal = () => (
    <div
      className={`modal fade ${showModal ? "show" : ""}`}
      style={{ display: showModal ? "block" : "none" }}
      tabIndex="-1"
    >
      <div className="modal-dialog modal-lg">
        <div className="modal-content">
          <div className="modal-header">
            <h5 className="modal-title">Aperçu du document</h5>
            <button
              type="button"
              className="btn-close"
              onClick={() => setShowModal(false)}
            ></button>
          </div>
          <div className="modal-body">
            {selectedDocument && (
              <div>
                <h6>{selectedDocument.titre}</h6>
                <p className="text-muted">
                  Date de publication : {selectedDocument.date_publication}
                </p>
                <p className="text-muted">
                  Source :{" "}
                  {selectedDocument.source_url || selectedDocument.source}
                </p>{" "}
                {/* Utilise source_url si disponible */}
                <p className="text-muted">
                  Type : {selectedDocument.type_publication}
                </p>
                <p className="text-muted">Numéro : {selectedDocument.numero}</p>
                <p className="text-muted">
                  Domaines :{" "}
                  {selectedDocument.domaines.map((d) => d.libelle).join(", ")}
                </p>
                <div
                  className="bg-light p-4 text-center"
                  style={{ height: "400px" }}
                >
                  <svg
                    width="64"
                    height="64"
                    fill="currentColor"
                    className="text-muted mb-3"
                    viewBox="0 0 16 16"
                  >
                    <path d="M14 4.5V14a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V2a2 2 0 0 1 2-2h5.5L14 4.5zM9.5 3A1.5 1.5 0 0 0 11 4.5h2V14a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1h5.5v2z" />
                  </svg>
                  <p>Aperçu du document PDF</p>
                </div>
              </div>
            )}
          </div>
          <div className="modal-footer">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setShowModal(false)}
            >
              Fermer
            </button>
            {selectedDocument &&
            (selectedDocument.source_url || selectedDocument.source) ? ( // Utilise source_url si disponible
              <a
                href={selectedDocument.source_url || selectedDocument.source}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-cta"
              >
                Télécharger
              </a>
            ) : (
              <button type="button" className="btn btn-secondary" disabled>
                Télécharger (lien non disponible)
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  const renderCustomAlertModal = () => (
    <div
      className={`modal fade ${showAlertModal ? "show" : ""}`}
      style={{ display: showAlertModal ? "block" : "none" }}
      tabIndex="-1"
      onClick={() => setShowAlertModal(false)} // Ferme le modal en cliquant à l'extérieur
    >
      <div className="modal-dialog modal-sm modal-dialog-centered">
        <div className="modal-content" onClick={(e) => e.stopPropagation()}>
          <div
            className={`modal-header ${
              alertModalType === "success"
                ? "bg-success text-white"
                : "bg-danger text-white"
            }`}
          >
            <h5 className="modal-title">
              {alertModalType === "success" ? "Succès" : "Erreur"}
            </h5>
            <button
              type="button"
              className="btn-close btn-close-white"
              onClick={() => setShowAlertModal(false)}
            ></button>
          </div>
          <div className="modal-body">
            <p>{alertModalMessage}</p>
          </div>
          <div className="modal-footer">
            <button
              type="button"
              className={`btn ${
                alertModalType === "success" ? "btn-success" : "btn-danger"
              }`}
              onClick={() => setShowAlertModal(false)}
            >
              Fermer
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  const renderContent = () => {
    switch (activeSection) {
      case "accueil":
        return renderAccueil();
      case "veille":
        return renderVeille();
      case "alertes":
        return renderAlertes();
      case "profil":
        return renderProfil();
      default:
        return renderAccueil();
    }
  };

  return (
    <>
      <div className="dashboard-container">
        {renderMobileHeader()}
        {renderSidebar()}
        <div className="main-wrapper">{renderContent()}</div>
        {showModal && renderModal()}
        {showAddEntrepriseModal && renderAddEntrepriseModal()}
        {showAlertModal && renderCustomAlertModal()}{" "}
        {/* Affichage du modal d'alerte personnalisé */}
      </div>
    </>
  );
};

export default Dashboard;
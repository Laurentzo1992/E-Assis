// Dashboard.jsx

import React, { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import i18n from "../i18n";
import { apiRequest, logout, setNavigateInstance } from "../services/auth";
import { useNavigate } from "react-router-dom";
import { Briefcase, Bell, CalendarClock, Home, User } from "lucide-react";
import { API_BASE_URL } from "../config";
import LanguageSwitcher, { LANGUE_SYNC_DONE_KEY } from "./LanguageSwitcher";

// Select multiple avec recherche (type Select2), en composant maison plutot qu'une dependance
// externe : react-select impliquerait une friction de peer-dependency avec React 19 (deja utilise
// ici) pour un simple filtrage textuel + selection multiple, faisable en quelques lignes en
// reutilisant les classes Bootstrap deja chargees dans public/index.html (dropdown, badge...).
// Interface volontairement generique (tableau d'IDs selectionnes) pour servir les deux formulaires
// entreprise (creation : IDs bruts : profil : objets complets) sans dupliquer le composant.
function SearchableMultiSelect({ options, selectedIds, onChange, placeholder, getId, getLabel }) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
        setQuery("");
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const filteredOptions = options.filter((opt) =>
    getLabel(opt).toLowerCase().includes(query.toLowerCase())
  );
  const selectedOptions = options.filter((opt) => selectedIds.includes(getId(opt)));

  const toggleOption = (id) => {
    onChange(
      selectedIds.includes(id)
        ? selectedIds.filter((i) => i !== id)
        : [...selectedIds, id]
    );
  };

  return (
    <div className="position-relative" ref={containerRef}>
      <div
        className="form-control d-flex flex-wrap align-items-center gap-1"
        style={{ cursor: "text", minHeight: "42px" }}
        onClick={() => setOpen(true)}
      >
        {selectedOptions.map((opt) => (
          <span
            key={getId(opt)}
            className="badge bg-primary d-flex align-items-center gap-1"
          >
            {getLabel(opt)}
            <button
              type="button"
              className="btn-close btn-close-white"
              style={{ fontSize: "0.55rem" }}
              aria-label={t("dashboard.common.retirerLabel", { label: getLabel(opt) })}
              onClick={(e) => {
                e.stopPropagation();
                toggleOption(getId(opt));
              }}
            />
          </span>
        ))}
        <input
          type="text"
          className="border-0 flex-grow-1 p-0"
          style={{ outline: "none", minWidth: "100px" }}
          placeholder={selectedOptions.length === 0 ? placeholder : ""}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setOpen(true)}
        />
      </div>
      {open && (
        <div
          className="dropdown-menu show w-100 p-0"
          style={{ maxHeight: "220px", overflowY: "auto" }}
        >
          {filteredOptions.length === 0 ? (
            <span className="dropdown-item-text text-muted">{t("dashboard.common.aucunResultat")}</span>
          ) : (
            filteredOptions.map((opt) => (
              <button
                key={getId(opt)}
                type="button"
                className="dropdown-item d-flex align-items-center gap-2"
                onClick={() => toggleOption(getId(opt))}
              >
                <input
                  type="checkbox"
                  readOnly
                  checked={selectedIds.includes(getId(opt))}
                  className="form-check-input m-0"
                />
                {getLabel(opt)}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

const Dashboard = () => {
  const { t } = useTranslation();
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
    rccm: "",
    telephone: "",
    email: "",
    nomRepresentant: "", // Mappé à repnom côté backend
    prenomRepresentant: "", // Mappé à repprenom côté backend
    domainesActivite: [], // Stockera les IDs des domaines sélectionnés
    secteursActivite: [], // Stockera les IDs des secteurs sélectionnés (multiple)
    adresse: "",
  });

  // --- États pour le profil de l'entreprise (dans la section Profil) ---
  const [profileData, setProfileData] = useState({
    nom: "",
    numeroIdentification: "",
    rccm: "",
    adresse: "",
    email: "",
    telephone: "",
    nomRepresentant: "", // Mappé à repnom côté backend
    prenomRepresentant: "", // Mappé à repprenom côté backend
    secteursActivite: [], // Stockera un tableau d'objets secteur (multiple)
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

  // --- États pour l'ajout d'un domaine par saisie libre, directement dans les formulaires
  // entreprise (en plus des cases a cocher) - distincts de newDomaineLibelle ci-dessus qui
  // alimente la carte de gestion globale des domaines, plus bas dans la page Profil.
  const [newDomaineInputAdd, setNewDomaineInputAdd] = useState("");
  const [newDomaineInputProfile, setNewDomaineInputProfile] = useState("");

  // --- États pour les données des sections (Accueil, Alertes) ---
  const [alertesApi, setAlertesApi] = useState([]);
  const [loadingAlertes, setLoadingAlertes] = useState(true);
  const [errorAlertes, setErrorAlertes] = useState(null);

  const [resultatsApi, setResultatsApi] = useState([]);
  const [loadingResultats, setLoadingResultats] = useState(true);
  const [errorResultats, setErrorResultats] = useState(null);

  const [lastReviewDate, setLastReviewDate] = useState(t("dashboard.accueil.dateNonDisponible"));

  // --- États pour l'abonnement (essai gratuit / actif / expiré) de l'entreprise active ---
  const [subscription, setSubscription] = useState(null);
  const [loadingSubscription, setLoadingSubscription] = useState(true);
  const [errorSubscription, setErrorSubscription] = useState(null);
  const [initiatingPayment, setInitiatingPayment] = useState(false);

  // --- État pour le document sélectionné dans le modal de prévisualisation ---
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [showModal, setShowModal] = useState(false);

  // --- États pour l'aperçu du PDF dans le modal (lecture a l'ecran, pas de telechargement) ---
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState(null);
  const [pdfPreviewLoading, setPdfPreviewLoading] = useState(false);
  const [pdfPreviewError, setPdfPreviewError] = useState(null);
  const [pdfPreviewPage, setPdfPreviewPage] = useState(null);

  // --- NOUVEAUX ÉTATS pour le changement de mot de passe ---
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [loadingPasswordUpdate, setLoadingPasswordUpdate] = useState(false);
  const [errorPasswordUpdate, setErrorPasswordUpdate] = useState(null);

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

  // --- Synchronisation de la langue du compte -> appareil (au chargement du Dashboard) ---
  // Objectif : un compte qui se connecte sur un nouvel appareil retrouve sa langue preferee.
  // On n'ecrase jamais un choix de langue explicite deja fait sur CET appareil : la cle
  // LANGUE_SYNC_DONE_KEY n'est posee QUE par LanguageSwitcher (changement manuel), jamais ici -
  // tant qu'aucun choix manuel n'a ete fait sur cet appareil, chaque chargement du Dashboard
  // retente la synchronisation (sans effet si la langue du compte est deja active).
  useEffect(() => {
    const syncLangueDuCompte = async () => {
      try {
        if (localStorage.getItem(LANGUE_SYNC_DONE_KEY)) return;
        const response = await apiRequest(`${API_BASE_URL}/api/auth/profile/`);
        if (!response || !response.ok) return;
        const data = await response.json();
        if (data.langue && data.langue !== i18n.language) {
          i18n.changeLanguage(data.langue);
        }
      } catch (error) {
        // Best-effort : si le backend ne renvoie pas encore ce champ ou est injoignable, on
        // garde simplement la langue actuellement active (localStorage/navigateur).
        console.error("Erreur lors de la synchronisation de la langue du compte:", error);
      }
    };
    syncLangueDuCompte();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- Fonctions de récupération des données de base (Domaines, Secteurs) ---
  const fetchDomaines = async () => {
    setLoadingDomaines(true);
    setErrorDomaines(null);
    try {
      const response = await apiRequest(
        `${API_BASE_URL}/api/entreprise/domaines/`
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
        `${API_BASE_URL}/api/entreprise/secteurs/`
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
          `${API_BASE_URL}/api/entreprise/entreprises/`
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
          `${API_BASE_URL}/api/entreprise/entreprises/active/`
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
            rccm: data.rccm || "",
            adresse: data.adresse || "",
            email: data.email || "",
            telephone: data.telephone || "",
            nomRepresentant: data.repnom || "", // Mappé de 'repnom'
            prenomRepresentant: data.repprenom || "", // Mappé de 'repprenom'
            // Mappe 'secteurs' (tableau d'objets) à 'secteursActivite' (plusieurs possibles)
            secteursActivite: data.secteurs || [],
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

  // Ajoute un domaine par saisie libre (en plus des cases a cocher) directement dans le
  // formulaire de creation d'entreprise, et le selectionne immediatement.
  const handleAddEntrepriseNewDomaine = async (e) => {
    e.preventDefault();
    const libelle = newDomaineInputAdd.trim();
    if (!libelle) return;
    try {
      const response = await apiRequest(
        `${API_BASE_URL}/api/entreprise/domaines/`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ libelle }),
        }
      );
      if (!response.ok) throw new Error(`Erreur: ${response.status}`);
      const domaine = await response.json();
      setApiDomainesActivite((prev) =>
        prev.some((d) => d.id === domaine.id) ? prev : [...prev, domaine]
      );
      setAddEntrepriseData((prev) =>
        prev.domainesActivite.includes(domaine.id)
          ? prev
          : { ...prev, domainesActivite: [...prev.domainesActivite, domaine.id] }
      );
      setNewDomaineInputAdd("");
    } catch (error) {
      showCustomAlert(t("dashboard.common.echecAjoutDomaineInline", { message: error.message }), "danger");
    }
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

  // Ajoute un domaine par saisie libre (en plus des cases a cocher) directement dans le
  // formulaire de profil, et le selectionne immediatement.
  const handleProfileNewDomaine = async (e) => {
    e.preventDefault();
    const libelle = newDomaineInputProfile.trim();
    if (!libelle) return;
    try {
      const response = await apiRequest(
        `${API_BASE_URL}/api/entreprise/domaines/`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ libelle }),
        }
      );
      if (!response.ok) throw new Error(`Erreur: ${response.status}`);
      const domaine = await response.json();
      setApiDomainesActivite((prev) =>
        prev.some((d) => d.id === domaine.id) ? prev : [...prev, domaine]
      );
      setProfileData((prev) =>
        prev.domainesActivite.some((d) => d.id === domaine.id)
          ? prev
          : { ...prev, domainesActivite: [...prev.domainesActivite, domaine] }
      );
      setNewDomaineInputProfile("");
    } catch (error) {
      showCustomAlert(t("dashboard.common.echecAjoutDomaineInline", { message: error.message }), "danger");
    }
  };

  // --- Fonctions de soumission des formulaires ---
  const handleSubmitAddEntreprise = async (e) => {
    e.preventDefault();
    // Le select "Secteurs d'activité *" n'est plus un <select> natif (SearchableMultiSelect est
    // un <div>), donc l'attribut HTML `required` ne peut plus etre valide par le navigateur -
    // controle manuel a la place.
    if (addEntrepriseData.secteursActivite.length === 0) {
      showCustomAlert(t("dashboard.modales.ajoutEntreprise.erreurSecteurRequis"), "danger");
      return;
    }
    setLoadingActiveCompany(true);
    try {
      const createResponse = await apiRequest(
        `${API_BASE_URL}/api/entreprise/entreprises/`,
        {
          method: "POST",
          body: JSON.stringify({
            nom: addEntrepriseData.nom,
            numero_identification: addEntrepriseData.numeroIdentification,
            rccm: addEntrepriseData.rccm,
            telephone: addEntrepriseData.telephone,
            email: addEntrepriseData.email,
            repnom: addEntrepriseData.nomRepresentant,
            repprenom: addEntrepriseData.prenomRepresentant,
            domaine_ids: addEntrepriseData.domainesActivite,
            secteur_ids: addEntrepriseData.secteursActivite,
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
        `${API_BASE_URL}/api/entreprise/entreprises/set-active/`, // Correction de l'URL ici
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
        rccm: newCompany.rccm || "",
        adresse: newCompany.adresse || "",
        email: newCompany.email || "",
        telephone: newCompany.telephone || "",
        nomRepresentant: newCompany.repnom || "",
        prenomRepresentant: newCompany.repprenom || "",
        secteursActivite: newCompany.secteurs || [],
        domainesActivite: newCompany.domaines || [],
      });
      showCustomAlert(
        t("dashboard.modales.ajoutEntreprise.succes"),
        "success"
      );
    } catch (error) {
      console.error("Erreur lors de la création de l'entreprise:", error);
      showCustomAlert(
        t("dashboard.modales.ajoutEntreprise.echec", { message: error.message }),
        "danger"
      );
    } finally {
      setLoadingActiveCompany(false);
    }
  };

  const handleSubmitUpdateProfile = async (e) => {
    e.preventDefault();
    if (!activeCompany) {
      showCustomAlert(t("dashboard.profil.entreprise.erreurAucuneActive"), "danger");
      return;
    }
    setLoadingProfileUpdate(true);
    setErrorProfileUpdate(null);
    try {
      const response = await apiRequest(
        `${API_BASE_URL}/api/entreprise/entreprises/${activeCompany.id}/`,
        {
          method: "PUT",
          body: JSON.stringify({
            nom: profileData.nom,
            numero_identification: profileData.numeroIdentification,
            rccm: profileData.rccm,
            adresse: profileData.adresse,
            email: profileData.email,
            telephone: profileData.telephone,
            repnom: profileData.nomRepresentant,
            repprenom: profileData.prenomRepresentant,
            domaine_ids: profileData.domainesActivite.map((d) => d.id),
            secteur_ids: profileData.secteursActivite.map((s) => s.id),
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
        rccm: updatedCompany.rccm || "",
        adresse: updatedCompany.adresse || "",
        email: updatedCompany.email || "",
        telephone: updatedCompany.telephone || "",
        nomRepresentant: updatedCompany.repnom || "",
        prenomRepresentant: updatedCompany.repprenom || "",
        secteursActivite: updatedCompany.secteurs || [],
        domainesActivite: updatedCompany.domaines || [],
      });
      showCustomAlert(t("dashboard.profil.entreprise.succesMiseAJour"), "success");
    } catch (error) {
      console.error("Erreur lors de la mise à jour du profil :", error);
      setErrorProfileUpdate(error);
      showCustomAlert(t("dashboard.common.erreurAvecMessage", { message: error.message }), "danger");
    } finally {
      setLoadingProfileUpdate(false);
    }
  };

  const handleSubmitChangePassword = async (e) => {
    e.preventDefault();
    setErrorPasswordUpdate(null);
    if (newPassword !== confirmNewPassword) {
      showCustomAlert(
        t("dashboard.profil.motDePasse.erreurMismatch"),
        "danger"
      );
      return;
    }
    if (!currentPassword || !newPassword || !confirmNewPassword) {
      showCustomAlert(
        t("dashboard.profil.motDePasse.erreurChampsRequis"),
        "danger"
      );
      return;
    }

    setLoadingPasswordUpdate(true);
    try {
      const response = await apiRequest(
        `${API_BASE_URL}/api/auth/change-password/`,
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

      showCustomAlert(t("dashboard.profil.motDePasse.succes"), "success");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmNewPassword("");
    } catch (error) {
      console.error("Erreur lors du changement de mot de passe :", error);
      setErrorPasswordUpdate(error);
      showCustomAlert(
        t("dashboard.profil.motDePasse.echec", { message: error.message }),
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
        `${API_BASE_URL}/api/entreprise/secteurs/`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ nom: newSecteurNom }),
        }
      );
      if (!response.ok) throw new Error(`Erreur: ${response.status}`);
      await fetchSecteurs();
      setNewSecteurNom("");
      showCustomAlert(t("dashboard.profil.secteurs.succesAjout"), "success");
    } catch (error) {
      console.error("Erreur lors de l'ajout du secteur:", error);
      showCustomAlert(
        t("dashboard.profil.secteurs.echecAjout", { message: error.message }),
        "danger"
      );
    }
  };

  const handleAddDomaine = async (e) => {
    e.preventDefault();
    try {
      const response = await apiRequest(
        `${API_BASE_URL}/api/entreprise/domaines/`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ libelle: newDomaineLibelle }),
        }
      );
      if (!response.ok) throw new Error(`Erreur: ${response.status}`);
      await fetchDomaines();
      setNewDomaineLibelle("");
      showCustomAlert(t("dashboard.profil.domaines.succesAjout"), "success");
    } catch (error) {
      console.error("Erreur lors de l'ajout du domaine:", error);
      showCustomAlert(
        t("dashboard.profil.domaines.echecAjout", { message: error.message }),
        "danger"
      );
    }
  };

  // --- Effets pour charger les données des sections (filtrées par entreprise active) ---

  // Effet pour la date de derniere revue (Accueil) - seule information encore tiree de
  // /publications/ depuis la suppression de l'ecran "Veille & Documents".
  useEffect(() => {
    const fetchDerniereRevue = async () => {
      if (!activeCompany) return;
      try {
        const response = await apiRequest(
          `${API_BASE_URL}/api/backend/api/publications/`
        );
        if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);
        const data = await response.json();
        const publications = data.results || data;

        if (publications.length > 0) {
          const latestDate = publications.reduce((maxDate, pub) => {
            const pubDate = new Date(pub.date_publication);
            return pubDate > maxDate ? pubDate : maxDate;
          }, new Date(0));
          setLastReviewDate(latestDate.toLocaleDateString("fr-FR"));
        } else {
          setLastReviewDate(t("dashboard.accueil.dateNonDisponible"));
        }
      } catch (error) {
        console.error(
          "Erreur lors de la récupération de la date de dernière revue:",
          error
        );
      }
    };

    if (activeCompany) {
      fetchDerniereRevue();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeCompany]);

  // Effet pour l'abonnement (essai/actif/expiré) - Se déclenche quand l'entreprise active change,
  // puis se rafraîchit toutes les 5 minutes : jours_restants est recalculé côté serveur à chaque
  // appel (jamais mis en cache), mais sans ce polling un onglet resté ouvert plusieurs heures
  // afficherait un compte à rebours figé sur sa valeur du chargement initial.
  useEffect(() => {
    let annule = false;

    const fetchSubscription = async () => {
      if (!activeCompany) {
        setSubscription(null);
        setLoadingSubscription(false);
        return;
      }
      setLoadingSubscription(true);
      setErrorSubscription(null);
      try {
        const response = await apiRequest(
          `${API_BASE_URL}/api/paiement/abonnement/${activeCompany.id}/`
        );
        if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);
        const data = await response.json();
        if (!annule) setSubscription(data);
      } catch (error) {
        console.error("Erreur lors de la récupération de l'abonnement:", error);
        if (!annule) {
          setErrorSubscription(error);
          setSubscription(null);
        }
      } finally {
        if (!annule) setLoadingSubscription(false);
      }
    };

    fetchSubscription();
    const intervalId = setInterval(fetchSubscription, 5 * 60 * 1000);
    return () => {
      annule = true;
      clearInterval(intervalId);
    };
  }, [activeCompany]);

  // Lance le paiement CinetPay pour l'entreprise active et redirige vers la page de paiement
  // hebergee renvoyee par le backend (aucune donnee bancaire ne transite par ce frontend).
  const handleSouscrire = async () => {
    if (!activeCompany) return;
    setInitiatingPayment(true);
    try {
      const response = await apiRequest(`${API_BASE_URL}/api/paiement/initier/`, {
        method: "POST",
        body: JSON.stringify({ entreprise_id: activeCompany.id }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Erreur HTTP: ${response.status}`);
      }
      const { url } = await response.json();
      window.location.href = url;
    } catch (error) {
      console.error("Erreur lors de l'initiation du paiement:", error);
      showCustomAlert(t("dashboard.profil.abonnement.echecPaiement", { message: error.message }), "danger");
      setInitiatingPayment(false);
    }
  };

  // Effet pour les alertes (Alertes & Résultats) - Se déclenche quand l'entreprise active change
  useEffect(() => {
    const fetchAlertes = async () => {
      if (!activeCompany) return;
      setLoadingAlertes(true);
      setErrorAlertes(null);
      try {
        const response = await apiRequest(
          `${API_BASE_URL}/api/backend/api/alertes/`
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

  // Marquage a l'ouverture : des que l'ecran "Alertes & Resultats" est consulte, toutes les
  // alertes affichees passent lu=true (l'ecran les montre toutes en meme temps, pas de marquage
  // alerte par alerte). Se re-declenche sans effet si tout est deja marque (le .some() coupe court).
  useEffect(() => {
    if (activeSection !== "alertes") return;
    if (!alertesApi.some((a) => !a.lu)) return;
    (async () => {
      try {
        const response = await apiRequest(
          `${API_BASE_URL}/api/backend/api/alertes/marquer-lues/`,
          { method: "POST" }
        );
        if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);
        setAlertesApi((prev) => prev.map((a) => ({ ...a, lu: true })));
      } catch (error) {
        console.error("Erreur lors du marquage des alertes comme lues:", error);
      }
    })();
  }, [activeSection, alertesApi]);

  // Effet pour les résultats (Alertes & Résultats) - Se déclenche quand la section est "alertes" OU quand l'entreprise active change
  useEffect(() => {
    const fetchResultats = async () => {
      if (!activeCompany) return;
      setLoadingResultats(true);
      setErrorResultats(null);
      try {
        const response = await apiRequest(
          `${API_BASE_URL}/api/backend/api/resultats/`
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

  const handleOuvrirApercu = (publication, pageNumber = null) => {
    setSelectedDocument(publication);
    setPdfPreviewPage(pageNumber);
    setShowModal(true);
  };

  // Charge l'URL presignee du PDF des l'ouverture du modal, pour un aperçu directement a l'ecran
  // (iframe) plutot qu'un telechargement. pdfPreviewPage (fixe par handleOuvrirApercu, independant
  // de cet appel) permet de sauter directement a la page du bulletin ou se trouve le marche de
  // l'alerte, via le fragment #page=N supporte nativement par les visionneuses PDF des navigateurs.
  useEffect(() => {
    if (!showModal || !selectedDocument) {
      setPdfPreviewUrl(null);
      setPdfPreviewError(null);
      return;
    }
    let annule = false;
    setPdfPreviewLoading(true);
    setPdfPreviewError(null);
    setPdfPreviewUrl(null);
    (async () => {
      try {
        const response = await apiRequest(
          `${API_BASE_URL}/api/backend/api/publications/${selectedDocument.id}/pdf-url/`
        );
        if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);
        const { url } = await response.json();
        if (!annule) setPdfPreviewUrl(url);
      } catch (error) {
        if (!annule) setPdfPreviewError(error.message);
      } finally {
        if (!annule) setPdfPreviewLoading(false);
      }
    })();
    return () => {
      annule = true;
    };
  }, [showModal, selectedDocument]);

  // --- Rendu des composants UI ---
  const renderSidebar = () => (
    <>
      <div
        className={`sidebar-overlay ${sidebarOpen ? "show" : ""}`}
        onClick={() => setSidebarOpen(false)}
      ></div>

      <div className={`sidebar ${sidebarOpen ? "show" : ""}`}>
        <div className="sidebar-header">
          <h4>{t("dashboard.sidebar.brand")}</h4>
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
              <p className="text-muted mb-1">{t("dashboard.sidebar.chargementEntreprises")}</p>
            ) : errorUserCompanies ? (
              <p className="text-danger mb-1">
                {t("dashboard.sidebar.erreurChargementEntreprises", { message: errorUserCompanies.message })}
              </p>
            ) : userCompanies.length > 0 ? (
              <>
                <p className="text-muted mb-1">{t("dashboard.sidebar.entrepriseActiveLabel")}</p>
                <select
                  className="form-select mb-2"
                  value={activeCompany ? activeCompany.id : ""}
                  onChange={async (e) => {
                    const selectedId = parseInt(e.target.value);
                    if (selectedId) {
                      try {
                        const response = await apiRequest(
                          `${API_BASE_URL}/api/entreprise/entreprises/set-active/`,
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
                          rccm: updatedActiveCompany.rccm || "",
                          adresse: updatedActiveCompany.adresse || "",
                          email: updatedActiveCompany.email || "",
                          telephone: updatedActiveCompany.telephone || "",
                          nomRepresentant: updatedActiveCompany.repnom || "",
                          prenomRepresentant:
                            updatedActiveCompany.repprenom || "",
                          secteursActivite: updatedActiveCompany.secteurs || [],
                          domainesActivite: updatedActiveCompany.domaines || [],
                        });
                        showCustomAlert(
                          t("dashboard.sidebar.succesChangementEntreprise"),
                          "success"
                        );
                      } catch (error) {
                        console.error(
                          "Erreur lors du changement d'entreprise active:",
                          error
                        );
                        showCustomAlert(
                          t("dashboard.sidebar.echecChangementEntreprise", { message: error.message }),
                          "danger"
                        );
                      }
                    }
                  }}
                >
                  <option value="">{t("dashboard.sidebar.selectionnerEntreprise")}</option>
                  {userCompanies.map((company) => (
                    <option key={company.id} value={company.id}>
                      {company.nom}
                    </option>
                  ))}
                </select>
              </>
            ) : (
              <p className="text-muted mb-1">{t("dashboard.sidebar.aucuneEntreprise")}</p>
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
            {t("dashboard.sidebar.ajouterEntreprise")}
          </button>

          <nav className="sidebar-nav">
            <button
              type="button"
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
              {t("dashboard.sidebar.navAccueil")}
            </button>
            <button
              type="button"
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
              {t("dashboard.sidebar.navAlertes")}
            </button>
            <button
              type="button"
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
              {t("dashboard.sidebar.navProfil")}
            </button>
          </nav>
        </div>

        <div className="sidebar-footer">
          <div className="mb-2 text-center">
            <LanguageSwitcher />
          </div>
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
            {t("dashboard.sidebar.deconnexion")}
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
      <h5 className="m-0">{t("dashboard.sidebar.brand")}</h5>
    </div>
  );

  // Barre d'onglets fixee en bas de l'ecran, visible uniquement sur mobile (d-md-none) : pattern
  // de navigation natif (pouce, acces direct) plutot que le menu hamburger seul, qui reste
  // disponible pour le changement d'entreprise et la deconnexion (actions secondaires).
  const renderMobileBottomNav = () => (
    <nav className="bottom-nav d-md-none">
      <button
        type="button"
        className={`bottom-nav-item ${activeSection === "accueil" ? "active" : ""}`}
        onClick={() => setActiveSection("accueil")}
      >
        <Home size={20} />
        <span>{t("dashboard.sidebar.navAccueil")}</span>
      </button>
      <button
        type="button"
        className={`bottom-nav-item ${activeSection === "alertes" ? "active" : ""}`}
        onClick={() => setActiveSection("alertes")}
      >
        <Bell size={20} />
        <span>{t("dashboard.sidebar.navAlertesCourt")}</span>
      </button>
      <button
        type="button"
        className={`bottom-nav-item ${activeSection === "profil" ? "active" : ""}`}
        onClick={() => setActiveSection("profil")}
      >
        <User size={20} />
        <span>{t("dashboard.sidebar.navProfil")}</span>
      </button>
    </nav>
  );

  // Banniere de statut d'abonnement, affichee au-dessus de toutes les sections (pas seulement
  // Profil) puisqu'un essai/abonnement expire doit rester visible quel que soit l'ecran consulte.
  const renderSubscriptionBanner = () => {
    if (!activeCompany || loadingSubscription || errorSubscription || !subscription) return null;

    if (subscription.statut === "actif") return null; // rien a signaler tant que l'abonnement est en cours

    const variante = subscription.statut === "essai" ? "alert-warning" : "alert-danger";
    const message =
      subscription.statut === "essai"
        ? t("dashboard.common.bannerEssai", { jours: subscription.jours_restants, nom: activeCompany.nom })
        : t("dashboard.common.bannerExpire", { nom: activeCompany.nom });

    return (
      <div className={`alert ${variante} d-flex flex-column flex-sm-row justify-content-between align-items-sm-center gap-2 mb-3`}>
        <span>{message}</span>
        <button
          type="button"
          className="btn btn-cta flex-shrink-0"
          onClick={handleSouscrire}
          disabled={initiatingPayment}
        >
          {initiatingPayment ? t("dashboard.common.redirection") : t("dashboard.common.sabonner")}
        </button>
      </div>
    );
  };

  const renderAccueil = () => (
    <div className="main-content">
      <div className="content-header">
        <h2>{t("dashboard.accueil.titre")}</h2>
        <p className="text-muted">{t("dashboard.accueil.sousTitre")}</p>
      </div>

      {loadingActiveCompany ? (
        <p>{t("dashboard.common.chargementDonneesEntreprise")}</p>
      ) : errorActiveCompany ? (
        <div className="alert alert-danger">
          {t("dashboard.common.erreurChargementEntreprise", { message: errorActiveCompany.message })}
        </div>
      ) : !activeCompany ? (
        <div className="alert alert-info">
          {t("dashboard.accueil.pasEntreprise")}
        </div>
      ) : (
        <>
          <div className="row mb-4">
            <div className="col-lg-4 col-md-6 mb-3">
              <div className="card kpi-card">
                <div className="card-body text-center">
                  <div className="kpi-icon kpi-icon-blue">
                    <Briefcase size={22} />
                  </div>
                  {loadingAlertes ? (
                    <p>{t("dashboard.common.chargementCourt")}</p>
                  ) : errorAlertes ? (
                    <p className="text-danger">
                      {t("dashboard.common.erreurChargementCourt", { message: errorAlertes.message })}
                    </p>
                  ) : (
                    <h3 className="card-title">
                      {
                        alertesApi.filter((a) => {
                          if (a.type_alerte !== "marche") return false;
                          const dateAlerte = new Date(a.date_alerte);
                          const maintenant = new Date();
                          return (
                            dateAlerte.getMonth() === maintenant.getMonth() &&
                            dateAlerte.getFullYear() === maintenant.getFullYear()
                          );
                        }).length
                      }
                    </h3>
                  )}
                  <p className="card-text">
                    {t("dashboard.accueil.kpiAppelsOffres", { nom: activeCompany.nom })}
                  </p>
                </div>
              </div>
            </div>
            <div className="col-lg-4 col-md-6 mb-3">
              <div className="card kpi-card">
                <div className="card-body text-center">
                  <div className="kpi-icon kpi-icon-orange">
                    <Bell size={22} />
                  </div>
                  {loadingAlertes ? (
                    <p>{t("dashboard.common.chargementCourt")}</p>
                  ) : errorAlertes ? (
                    <p className="text-danger">
                      {t("dashboard.common.erreurChargementCourt", { message: errorAlertes.message })}
                    </p>
                  ) : (
                    <h3 className="card-title">
                      {alertesApi.filter((a) => !a.lu).length}
                    </h3>
                  )}
                  <p className="card-text">
                    {t("dashboard.accueil.kpiAlertesNonLues", { nom: activeCompany.nom })}
                  </p>
                </div>
              </div>
            </div>
            <div className="col-lg-4 col-md-6 mb-3">
              <div className="card kpi-card">
                <div className="card-body text-center">
                  <div className="kpi-icon kpi-icon-blue">
                    <CalendarClock size={22} />
                  </div>
                  {/* Affichage de la date de dernière revue importée */}
                  <h3 className="card-title">{lastReviewDate}</h3>
                  <p className="card-text">
                    {t("dashboard.accueil.kpiDerniereRevue")}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h5 className="mb-0">{t("dashboard.accueil.actionsRapides")}</h5>
            </div>
            <div className="card-body">
              <div className="row">
                <div className="col-lg-6 col-md-6 mb-2">
                  <button
                    className="btn btn-cta w-100"
                    onClick={() => setActiveSection("profil")}
                  >
                    {t("dashboard.accueil.btnModifierParametres")}
                  </button>
                </div>
                <div className="col-lg-6 col-md-6 mb-2">
                  <button
                    className="btn btn-cta w-100"
                    onClick={() => setActiveSection("alertes")}
                  >
                    {t("dashboard.accueil.btnVoirAlertes")}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );

  const renderAlertes = () => (
    <div className="main-content">
      <div className="content-header">
        <h2>{t("dashboard.alertes.titre")}</h2>
        <p className="text-muted">
          {t("dashboard.alertes.sousTitre")}
        </p>
      </div>
      {loadingActiveCompany ? (
        <p>{t("dashboard.common.chargementDonneesEntreprise")}</p>
      ) : errorActiveCompany ? (
        <div className="alert alert-danger">
          {t("dashboard.common.erreurChargementEntreprise", { message: errorActiveCompany.message })}
        </div>
      ) : !activeCompany ? (
        <div className="alert alert-info">
          {t("dashboard.alertes.pasEntreprise")}
        </div>
      ) : (
        <div className="row">
          <div className="col-lg-8 mb-4">
            <div className="card">
              <div className="card-header">
                <h5 className="mb-0">
                  {t("dashboard.alertes.titreCarteAlertes", { nom: activeCompany.nom })}
                </h5>
              </div>
              <div className="card-body">
                {loadingAlertes ? (
                  <p>{t("dashboard.alertes.chargementAlertes")}</p>
                ) : errorAlertes ? (
                  <div className="alert alert-danger">
                    {t("dashboard.alertes.erreurChargementAlertes", { message: errorAlertes.message })}
                  </div>
                ) : alertesApi.length === 0 ? (
                  <p>{t("dashboard.alertes.aucuneAlerte")}</p>
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
                            {!alerte.lu && (
                              <span className="badge bg-danger me-2">{t("dashboard.alertes.badgeNouveau")}</span>
                            )}
                            {alerte.type_alerte === "marche" ? t("dashboard.alertes.typeOffre") : alerte.type_alerte}: {alerte.contenu_alerte}
                          </h6>
                          <small className="text-muted">
                            {new Date(alerte.date_alerte).toLocaleDateString(
                              "fr-FR"
                            )}{" "}
                            - {t("dashboard.alertes.canal")}: {alerte.canal_alerte}
                          </small>
                          {alerte.publication && (
                            <small className="text-muted d-block mt-1">
                              {t("dashboard.alertes.publicationLabel")}: {alerte.publication.titre}
                            </small>
                          )}
                          {alerte.entreprise && (
                            <small className="text-muted d-block">
                              {t("dashboard.alertes.entrepriseLabel")}: {alerte.entreprise.nom}
                            </small>
                          )}
                        </div>
                        {alerte.publication && (
                          <button
                            type="button"
                            className="btn btn-sm btn-outline-primary flex-shrink-0"
                            onClick={() =>
                              handleOuvrirApercu(
                                alerte.publication,
                                alerte.marche ? alerte.marche.page_number : null
                              )
                            }
                          >
                            {t("dashboard.alertes.voirBulletin")}
                          </button>
                        )}
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
                  {t("dashboard.alertes.titreCarteResultats", { nom: activeCompany.nom })}
                </h5>
              </div>
              <div className="card-body">
                {loadingResultats ? (
                  <p>{t("dashboard.alertes.chargementResultats")}</p>
                ) : errorResultats ? (
                  <div className="alert alert-danger">
                    {t("dashboard.alertes.erreurChargementResultats", { message: errorResultats.message })}
                  </div>
                ) : resultatsApi.length === 0 ? (
                  <p>{t("dashboard.alertes.aucunResultat")}</p>
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
                              ? t("dashboard.alertes.retenu")
                              : t("dashboard.alertes.nonRetenu")}
                          </span>
                        </div>
                        <small className="text-muted d-block">
                          {t("dashboard.alertes.resultatPublieLe")}{" "}
                          {new Date(
                            resultat.date_attribution
                          ).toLocaleDateString("fr-FR")}
                        </small>
                        <small className="text-muted d-block">
                          {t("dashboard.alertes.attributaireLabel")}:{" "}
                          {resultat.entreprise_attributaire
                            ? resultat.entreprise_attributaire.nom
                            : resultat.entreprise_attributaire_nom || t("dashboard.common.nonApplicable")}
                        </small>
                        <small className="text-muted d-block">
                          {t("dashboard.alertes.montantAttribueLabel")}: {resultat.montant_attribue}
                        </small>
                        <a
                          href={resultat.marche.publication.source}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="small"
                        >
                          {t("dashboard.alertes.voirAnnonce")}
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
        <h2>{t("dashboard.profil.titre")}</h2>
        <p className="text-muted">{t("dashboard.profil.sousTitre")}</p>
      </div>

      {loadingActiveCompany ? (
        <p>{t("dashboard.profil.chargementProfil")}</p>
      ) : errorActiveCompany ? (
        <div className="alert alert-danger">
          {t("dashboard.profil.erreurChargementProfil", { message: errorActiveCompany.message })}
        </div>
      ) : !activeCompany ? (
        <div className="alert alert-info">
          {t("dashboard.profil.pasEntreprise")}
        </div>
      ) : (
        <div className="row">
          <div className="col-lg-8 mb-4">
            <div className="card mb-4">
              <div className="card-header">
                <h5 className="mb-0">{t("dashboard.profil.abonnement.titre")}</h5>
              </div>
              <div className="card-body">
                {loadingSubscription ? (
                  <p className="mb-0">{t("dashboard.profil.abonnement.chargement")}</p>
                ) : errorSubscription ? (
                  <p className="text-danger mb-0">
                    {t("dashboard.profil.abonnement.erreur", { message: errorSubscription.message })}
                  </p>
                ) : !subscription ? (
                  <p className="text-muted mb-0">{t("dashboard.profil.abonnement.aucuneInfo")}</p>
                ) : (
                  <div className="d-flex flex-column flex-sm-row justify-content-between align-items-sm-center gap-3">
                    <div>
                      {subscription.statut === "essai" && (
                        <p className="mb-0">
                          <span className="badge bg-warning text-dark me-2">{t("dashboard.profil.abonnement.badgeEssai")}</span>
                          {t("dashboard.profil.abonnement.essaiTexte", {
                            jours: subscription.jours_restants,
                            date: new Date(subscription.date_fin_essai).toLocaleDateString("fr-FR"),
                          })}
                        </p>
                      )}
                      {subscription.statut === "actif" && (
                        <p className="mb-0">
                          <span className="badge bg-success me-2">{t("dashboard.profil.abonnement.badgeActif")}</span>
                          {t("dashboard.profil.abonnement.actifTexte", {
                            date: new Date(subscription.date_fin_abonnement).toLocaleDateString("fr-FR"),
                          })}
                        </p>
                      )}
                      {subscription.statut === "expire" && (
                        <p className="mb-0">
                          <span className="badge bg-danger me-2">{t("dashboard.profil.abonnement.badgeExpire")}</span>
                          {t("dashboard.profil.abonnement.expireTexte")}
                        </p>
                      )}
                    </div>
                    {subscription.statut !== "actif" && (
                      <button
                        type="button"
                        className="btn btn-cta flex-shrink-0"
                        onClick={handleSouscrire}
                        disabled={initiatingPayment}
                      >
                        {initiatingPayment ? t("dashboard.common.redirection") : t("dashboard.profil.abonnement.sabonnerAnnuel")}
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>

            <div className="card mb-4">
              <div className="card-header">
                <h5 className="mb-0">{t("dashboard.profil.entreprise.titre")}</h5>
              </div>
              <div className="card-body">
                <form onSubmit={handleSubmitUpdateProfile}>
                  <div className="row">
                    <div className="col-md-6 mb-3">
                      <label className="form-label">{t("dashboard.profil.entreprise.labelNom")}</label>
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
                        {t("dashboard.profil.entreprise.labelNumeroId")}
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
                      <label className="form-label">{t("dashboard.profil.entreprise.labelRccm")}</label>
                      <input
                        type="text"
                        className="form-control"
                        value={profileData.rccm || ""}
                        onChange={(e) =>
                          setProfileData({
                            ...profileData,
                            rccm: e.target.value,
                          })
                        }
                      />
                    </div>
                    <div className="col-md-6 mb-3">
                      <label className="form-label">{t("dashboard.profil.entreprise.labelNomRepresentant")}</label>
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
                        {t("dashboard.profil.entreprise.labelPrenomRepresentant")}
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
                      <label className="form-label">{t("dashboard.profil.entreprise.labelAdresse")}</label>
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
                      <label className="form-label">{t("dashboard.profil.entreprise.labelEmail")}</label>
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
                      <label className="form-label">{t("dashboard.profil.entreprise.labelTelephone")}</label>
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

                  {/* Secteurs d'activité (select multiple avec recherche) */}
                  <div className="mb-3">
                    <label className="form-label">{t("dashboard.profil.entreprise.labelSecteurs")}</label>
                    {loadingSecteurs ? (
                      <p>{t("dashboard.common.chargementSecteurs")}</p>
                    ) : errorSecteurs ? (
                      <p className="text-danger">
                        {t("dashboard.common.erreurChargementSecteurs", { message: errorSecteurs.message })}
                      </p>
                    ) : (
                      <SearchableMultiSelect
                        options={apiSecteursActivite}
                        selectedIds={profileData.secteursActivite.map(
                          (s) => s.id
                        )}
                        onChange={(ids) => {
                          const updated = apiSecteursActivite.filter((s) =>
                            ids.includes(s.id)
                          );
                          setProfileData({
                            ...profileData,
                            secteursActivite: updated,
                          });
                        }}
                        placeholder={t("dashboard.common.rechercherSecteur")}
                        getId={(s) => s.id}
                        getLabel={(s) => s.nom}
                      />
                    )}
                  </div>

                  {/* Domaines d'activité */}
                  <div className="mb-3">
                    <label className="form-label">{t("dashboard.profil.entreprise.labelDomaines")}</label>
                    {loadingDomaines ? (
                      <p>{t("dashboard.common.chargementDomaines")}</p>
                    ) : errorDomaines ? (
                      <p className="text-danger">
                        {t("dashboard.common.erreurChargementDomaines", { message: errorDomaines.message })}
                      </p>
                    ) : (
                      <div className="row">
                        {apiDomainesActivite.map((domaine) => (
                          <div key={domaine.id} className="col-md-6 mb-2">
                            <div className="form-check">
                              <input
                                className="form-check-input"
                                type="checkbox"
                                id={`domaine-${domaine.id}`}
                                checked={profileData.domainesActivite.some(
                                  (d) => d.id === domaine.id
                                )}
                                onChange={() =>
                                  handleProfileDomaineChange(domaine.id)
                                }
                              />
                              <label
                                className="form-check-label"
                                htmlFor={`domaine-${domaine.id}`}
                              >
                                {domaine.libelle}
                              </label>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="input-group mt-2">
                      <input
                        type="text"
                        className="form-control"
                        placeholder={t("dashboard.common.placeholderAjouterDomaine")}
                        value={newDomaineInputProfile}
                        onChange={(e) =>
                          setNewDomaineInputProfile(e.target.value)
                        }
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleProfileNewDomaine(e);
                        }}
                      />
                      <button
                        type="button"
                        className="btn btn-outline-secondary"
                        onClick={handleProfileNewDomaine}
                      >
                        {t("dashboard.common.ajouter")}
                      </button>
                    </div>
                  </div>

                  <button
                    type="submit"
                    className="btn btn-cta"
                    disabled={loadingProfileUpdate}
                  >
                    {loadingProfileUpdate
                      ? t("dashboard.profil.entreprise.btnEnregistrement")
                      : t("dashboard.profil.entreprise.btnEnregistrer")}
                  </button>
                  {errorProfileUpdate && (
                    <p className="text-danger mt-2">
                      {t("dashboard.common.erreurAvecMessage", { message: errorProfileUpdate.message })}
                    </p>
                  )}
                </form>
              </div>
            </div>

            {/* Section Ajout de Secteur */}
            <div className="card mb-4">
              <div className="card-header">
                <h5 className="mb-0">{t("dashboard.profil.secteurs.titre")}</h5>
              </div>
              <div className="card-body">
                <form onSubmit={handleAddSecteur}>
                  <div className="mb-3">
                    <label className="form-label">{t("dashboard.profil.secteurs.labelNom")}</label>
                    <input
                      type="text"
                      className="form-control"
                      value={newSecteurNom}
                      onChange={(e) => setNewSecteurNom(e.target.value)}
                      required
                    />
                  </div>
                  <button type="submit" className="btn btn-cta">
                    {t("dashboard.profil.secteurs.btnAjouter")}
                  </button>
                </form>
              </div>
            </div>

            {/* Section Ajout de Domaine */}
            <div className="card mb-4">
              <div className="card-header">
                <h5 className="mb-0">{t("dashboard.profil.domaines.titre")}</h5>
              </div>
              <div className="card-body">
                <form onSubmit={handleAddDomaine}>
                  <div className="mb-3">
                    <label className="form-label">{t("dashboard.profil.domaines.labelLibelle")}</label>
                    <input
                      type="text"
                      className="form-control"
                      value={newDomaineLibelle}
                      onChange={(e) => setNewDomaineLibelle(e.target.value)}
                      required
                    />
                  </div>
                  <button type="submit" className="btn btn-cta">
                    {t("dashboard.profil.domaines.btnAjouter")}
                  </button>
                </form>
              </div>
            </div>
          </div>

          <div className="col-lg-4">
            <div className="card">
              <div className="card-header">
                <h5 className="mb-0">{t("dashboard.profil.motDePasse.titre")}</h5>
              </div>
              <div className="card-body">
                <form onSubmit={handleSubmitChangePassword}>
                  <div className="mb-3">
                    <label className="form-label">{t("dashboard.profil.motDePasse.labelActuel")}</label>
                    <input
                      type="password"
                      className="form-control"
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                      required
                    />
                  </div>
                  <div className="mb-3">
                    <label className="form-label">{t("dashboard.profil.motDePasse.labelNouveau")}</label>
                    <input
                      type="password"
                      className="form-control"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      required
                    />
                  </div>
                  <div className="mb-3">
                    <label className="form-label">
                      {t("dashboard.profil.motDePasse.labelConfirmer")}
                    </label>
                    <input
                      type="password"
                      className="form-control"
                      value={confirmNewPassword}
                      onChange={(e) => setConfirmNewPassword(e.target.value)}
                      required
                    />
                  </div>
                  <button
                    type="submit"
                    className="btn btn-cta w-100"
                    disabled={loadingPasswordUpdate}
                  >
                    {loadingPasswordUpdate
                      ? t("dashboard.profil.motDePasse.btnMiseAJour")
                      : t("dashboard.profil.motDePasse.btnMettreAJour")}
                  </button>
                  {errorPasswordUpdate && (
                    <p className="text-danger mt-2">
                      {t("dashboard.common.erreurAvecMessage", { message: errorPasswordUpdate.message })}
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
            <h5 className="modal-title">{t("dashboard.modales.ajoutEntreprise.titre")}</h5>
          </div>
          <form onSubmit={handleSubmitAddEntreprise}>
            <div className="modal-body">
              <p className="text-muted">
                {t("dashboard.modales.ajoutEntreprise.intro")}
              </p>
              <div className="row">
                <div className="col-md-6 mb-3">
                  <label className="form-label">{t("dashboard.modales.ajoutEntreprise.labelNom")}</label>
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
                    {t("dashboard.modales.ajoutEntreprise.labelNumeroId")}
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
                  <label className="form-label">{t("dashboard.modales.ajoutEntreprise.labelRccm")}</label>
                  <input
                    type="text"
                    className="form-control"
                    value={addEntrepriseData.rccm}
                    onChange={(e) =>
                      setAddEntrepriseData({
                        ...addEntrepriseData,
                        rccm: e.target.value,
                      })
                    }
                    required
                  />
                </div>
                <div className="col-md-6 mb-3">
                  <label className="form-label">{t("dashboard.profil.entreprise.labelTelephone")}</label>
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
                  <label className="form-label">{t("dashboard.profil.entreprise.labelEmail")}</label>
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
                  <label className="form-label">{t("dashboard.profil.entreprise.labelNomRepresentant")}</label>
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
                  <label className="form-label">{t("dashboard.profil.entreprise.labelPrenomRepresentant")}</label>
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
                  <label className="form-label">{t("dashboard.profil.entreprise.labelAdresse")}</label>
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
                <label className="form-label">{t("dashboard.modales.ajoutEntreprise.labelSecteurs")}</label>
                {loadingSecteurs ? (
                  <p>{t("dashboard.common.chargementSecteurs")}</p>
                ) : errorSecteurs ? (
                  <p className="text-danger">
                    {t("dashboard.common.erreurChargementSecteurs", { message: errorSecteurs.message })}
                  </p>
                ) : (
                  <SearchableMultiSelect
                    options={apiSecteursActivite}
                    selectedIds={addEntrepriseData.secteursActivite}
                    onChange={(ids) =>
                      setAddEntrepriseData({
                        ...addEntrepriseData,
                        secteursActivite: ids,
                      })
                    }
                    placeholder={t("dashboard.common.rechercherSecteur")}
                    getId={(s) => s.id}
                    getLabel={(s) => s.nom}
                  />
                )}
              </div>

              <div className="mb-3">
                <label className="form-label">{t("dashboard.modales.ajoutEntreprise.labelDomaines")}</label>
                {loadingDomaines ? (
                  <p>{t("dashboard.common.chargementDomaines")}</p>
                ) : errorDomaines ? (
                  <p className="text-danger">
                    {t("dashboard.common.erreurChargementDomaines", { message: errorDomaines.message })}
                  </p>
                ) : (
                  <div className="row">
                    {apiDomainesActivite.map((domaine) => (
                      <div key={domaine.id} className="col-md-6 mb-2">
                        <div className="form-check">
                          <input
                            className="form-check-input"
                            type="checkbox"
                            id={`add-domaine-${domaine.id}`}
                            checked={addEntrepriseData.domainesActivite.includes(
                              domaine.id
                            )}
                            onChange={() =>
                              handleAddEntrepriseDomaine(domaine.id)
                            }
                          />
                          <label
                            className="form-check-label"
                            htmlFor={`add-domaine-${domaine.id}`}
                          >
                            {domaine.libelle}
                          </label>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                <div className="input-group mt-2">
                  <input
                    type="text"
                    className="form-control"
                    placeholder={t("dashboard.common.placeholderAjouterDomaine")}
                    value={newDomaineInputAdd}
                    onChange={(e) => setNewDomaineInputAdd(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleAddEntrepriseNewDomaine(e);
                    }}
                  />
                  <button
                    type="button"
                    className="btn btn-outline-secondary"
                    onClick={handleAddEntrepriseNewDomaine}
                  >
                    {t("dashboard.common.ajouter")}
                  </button>
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button
                type="submit"
                className="btn btn-cta"
                disabled={loadingActiveCompany}
              >
                {loadingActiveCompany ? t("dashboard.modales.ajoutEntreprise.btnCreation") : t("dashboard.modales.ajoutEntreprise.btnCreer")}
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
      <div className="modal-dialog modal-xl">
        <div className="modal-content">
          <div className="modal-header">
            <h5 className="modal-title">{t("dashboard.modales.apercu.titre")}</h5>
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
                <p className="text-muted mb-2">
                  {t("dashboard.modales.apercu.numeroPublieLe", {
                    numero: selectedDocument.numero,
                    date: selectedDocument.date_publication,
                  })}
                  {pdfPreviewPage ? t("dashboard.modales.apercu.pageSuffix", { page: pdfPreviewPage }) : ""}
                </p>
                {pdfPreviewLoading ? (
                  <div className="bg-light p-4 text-center" style={{ height: "70vh" }}>
                    <p className="mb-0 pt-5">{t("dashboard.modales.apercu.chargement")}</p>
                  </div>
                ) : pdfPreviewError ? (
                  <div className="alert alert-danger">
                    {t("dashboard.modales.apercu.erreur", { error: pdfPreviewError })}
                  </div>
                ) : (
                  <iframe
                    src={
                      pdfPreviewPage
                        ? `${pdfPreviewUrl}#page=${pdfPreviewPage}`
                        : pdfPreviewUrl
                    }
                    title={selectedDocument.titre}
                    style={{ width: "100%", height: "70vh", border: "none" }}
                  />
                )}
              </div>
            )}
          </div>
          <div className="modal-footer">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setShowModal(false)}
            >
              {t("dashboard.common.fermer")}
            </button>
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
              {alertModalType === "success" ? t("dashboard.modales.alerte.succes") : t("dashboard.modales.alerte.erreur")}
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
              {t("dashboard.common.fermer")}
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
        <div className="main-wrapper">
          {renderSubscriptionBanner()}
          {renderContent()}
        </div>
        {renderMobileBottomNav()}
        {showModal && renderModal()}
        {showAddEntrepriseModal && renderAddEntrepriseModal()}
        {showAlertModal && renderCustomAlertModal()}{" "}
        {/* Affichage du modal d'alerte personnalisé */}
      </div>
    </>
  );
};

export default Dashboard;

import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

// Hooks et services
import { setNavigateInstance, logout } from "../services/auth";
import useActiveCompany from "../hooks/useActiveCompany";

// Composants de layout et d'interface
import Header from '../components/layout/Header';
import Sidebar from '../components/layout/Sidebar';
import AddEntrepriseModal from '../components/entreprise/AddEntrepriseModal';
import CustomAlert from '../components/ui/CustomAlert';
import Spinner from '../components/ui/Spinner';

// Composants de section (le contenu principal)
import NotificationsSection from '../components/sections/NotificationsSection';
import VeilleSection from '../components/sections/VeilleSection';
import ProfileSection from '../components/sections/ProfileSection';

/**
 * @file DashboardPage.jsx
 * @description Page principale du tableau de bord.
 * Ce composant agit comme un chef d'orchestre. Il utilise le hook `useActiveCompany`
 * pour obtenir toutes les données relatives à l'utilisateur et à ses entreprises,
 * puis il passe ces données aux composants enfants appropriés (Sidebar, Sections, Modals).
 * Son rôle principal est l'assemblage et la gestion de l'état global de l'interface.
 */
const DashboardPage = () => {
  // --- États spécifiques au layout ---
  const [activeSection, setActiveSection] = useState("alertes"); // Gère la section affichée
  const [sidebarOpen, setSidebarOpen] = useState(false); // Gère l'ouverture/fermeture de la sidebar sur mobile
  const navigate = useNavigate();

  // --- États pour le système de notification global (modales d'alerte) ---
  const [showAlertModal, setShowAlertModal] = useState(false);
  const [alertModalMessage, setAlertModalMessage] = useState("");
  const [alertModalType, setAlertModalType] = useState("success");

  /**
   * Fonction utilitaire pour déclencher l'affichage d'une alerte.
   * Elle sera passée en prop aux composants enfants qui ont besoin d'afficher des notifications.
   * @param {string} message - Le message à afficher.
   * @param {'success'|'danger'} type - Le type d'alerte.
   */
  const showCustomAlert = (message, type) => {
    setAlertModalMessage(message);
    setAlertModalType(type);
    setShowAlertModal(true);
  };

  // Initialise l'instance de navigation pour que les services (comme auth.js) puissent l'utiliser.
  useEffect(() => {
    setNavigateInstance(navigate);
  }, [navigate]);

  // --- Le cœur de la gestion de données ---
  // Le hook personnalisé `useActiveCompany` centralise toute la logique de récupération
  // et de gestion des données liées à l'utilisateur et à ses entreprises.
  const companyData = useActiveCompany(showCustomAlert);
  
  // Destructuration pour un accès plus facile aux données du hook
  const {
    userCompanies,
    activeCompany,
    setActiveCompany,
    loading: loadingActiveCompanyData,
    error: errorActiveCompanyData,
    refetchUserCompanies,
    showAddEntrepriseModal,
    setShowAddEntrepriseModal
  } = companyData;


  const handleSuccess = (newCompany) => {
  setActiveCompany(newCompany); // définit l'entreprise active
  showCustomAlert("Entreprise créée avec succès !", "success");
  setShowAddEntrepriseModal(false); // ferme le modal
};


  /**
   * Gère le rendu conditionnel du contenu principal.
   * Affiche un spinner, une erreur, un message de bienvenue, ou la section active.
   */
  const renderContent = () => {
    if (loadingActiveCompanyData) {
      return <Spinner message="Chargement des informations de l'entreprise..." />;
    }

    if (errorActiveCompanyData) {
      return (
        <div className="alert alert-danger m-4">
          <h4>Erreur de chargement</h4>
          <p>{errorActiveCompanyData.message}</p>
          <p>Veuillez recharger la page. Si le problème persiste, contactez le support.</p>
        </div>
      );
    }
    
    // Si l'utilisateur n'a pas encore d'entreprise, on l'incite à en créer une.
    if (!activeCompany && !showAddEntrepriseModal) {
      return (
        <div className="text-center p-5 bg-light rounded m-4">
            <h4>Bienvenue sur VeilleMarches Pro</h4>
            <p className="text-muted">Pour commencer, veuillez créer votre première entreprise.</p>
            <button 
              className="btn btn-primary mt-3" 
              onClick={() => setShowAddEntrepriseModal(true)}
            >
              Créer mon entreprise
            </button>
        </div>
      );
    }

    // Aiguillage vers le composant de section approprié.
    // On passe l'ensemble des données de `companyData` via le "spread" operator `...companyData`
    // pour que chaque section ait accès à tout ce dont elle pourrait avoir besoin.
    switch (activeSection) {
      case "veille":
        return <VeilleSection {...companyData} />;
      case "profil":
        return <ProfileSection {...companyData} showCustomAlert={showCustomAlert} />;
      case "alertes":
      default:
        return <NotificationsSection activeCompany={activeCompany} showCustomAlert={showCustomAlert} />;
    }
  };

  return (
    <>
      <div className="dashboard-container">
        <Header onMenuClick={() => setSidebarOpen(true)} />

        <Sidebar 
            userCompanies={userCompanies}
            activeCompany={activeCompany}
            setActiveCompany={setActiveCompany}
            onAddCompanyClick={() => setShowAddEntrepriseModal(true)}
            activeSection={activeSection}
            setActiveSection={setActiveSection}
            sidebarOpen={sidebarOpen}
            setSidebarOpen={setSidebarOpen}
            onLogout={logout}
            showCustomAlert={showCustomAlert}
            refetchUserCompanies={refetchUserCompanies}
        />

        <main className="main-wrapper">
            {renderContent()}
        </main>
        
        {/* Les modales sont gérées ici, au niveau le plus haut, pour s'afficher
            correctement au-dessus de n'importe quelle section. */}
        {showAddEntrepriseModal && (
          <AddEntrepriseModal
            onClose={() => setShowAddEntrepriseModal(false)}
            onSuccess={handleSuccess}
            apiDomainesActivite={companyData.apiDomainesActivite}
            loadingDomaines={companyData.loadingDomaines}
            apiSecteursActivite={companyData.apiSecteursActivite}
            loadingSecteurs={companyData.loadingSecteurs}
            showCustomAlert={showCustomAlert}
          />
        )}
        <CustomAlert
            show={showAlertModal}
            message={alertModalMessage}
            type={alertModalType}
            onClose={() => setShowAlertModal(false)}
        />
      </div>
    </>
  );
};

export default DashboardPage;
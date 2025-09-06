import React, { useState } from 'react';
import { apiRequest } from '../../services/api';

/**
 * @file Sidebar.jsx
 * @description Composant final pour la barre latérale.
 * Gère la navigation entre les sections et le changement d'entreprise active.
 */
const Sidebar = ({
  userCompanies,
  activeCompany,
  setActiveCompany,
  onAddCompanyClick,
  activeSection,
  setActiveSection,
  sidebarOpen,
  setSidebarOpen,
  onLogout,
  showCustomAlert,
}) => {
  // Ajout d'un état de chargement local pour le sélecteur
  const [isChangingCompany, setIsChangingCompany] = useState(false);

  /**
   * Gère le changement d'entreprise active via le sélecteur.
   * Cette fonction est maintenant entièrement contenue dans la Sidebar.
   * @param {React.ChangeEvent<HTMLSelectElement>} e - L'événement de changement du sélecteur.
   */
  const handleCompanyChange = async (e) => {
    const selectedId = parseInt(e.target.value);
    if (!selectedId || selectedId === activeCompany?.id) {
      return; // Ne rien faire si la même entreprise est re-sélectionnée
    }

    setIsChangingCompany(true); // Début du chargement
    try {
      const response = await apiRequest("entreprise/entreprises/set-active/", {
        method: "POST",
        body: JSON.stringify({ entreprise_id: selectedId }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(JSON.stringify(errorData));
      }

      const updatedActiveCompany = await response.json();
      
      // --- POINT CLÉ ---
      // On appelle la fonction `setActiveCompany` passée en prop par DashboardPage.
      // C'est ce qui met à jour l'état au niveau supérieur et déclenche le re-rendu global.
      setActiveCompany(updatedActiveCompany);
      
      showCustomAlert("Entreprise active changée avec succès !", "success");
      setSidebarOpen(false); // Ferme la sidebar sur mobile après le changement

    } catch (error) {
      console.error("Erreur lors du changement d'entreprise active:", error);
      showCustomAlert(`Échec du changement d'entreprise : ${error.message}`, "danger");
    } finally {
      setIsChangingCompany(false); // Fin du chargement
    }
  };

  return (
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
          </button>
        </div>

        <div className="sidebar-content">
          <div className="mb-3 text-center">
            {userCompanies.length > 0 ? (
              <>
                <p className="text-muted mb-1">Entreprise active :</p>
                <select
                  className="form-select mb-2"
                  value={activeCompany ? activeCompany.id : ""}
                  onChange={handleCompanyChange}
                  disabled={isChangingCompany} // Désactive le sélecteur pendant le chargement
                >
                  <option value="">Sélectionner une entreprise</option>
                  {userCompanies.map((company) => (
                    <option key={company.id} value={company.id}>
                      {company.nom}
                    </option>
                  ))}
                </select>
                {isChangingCompany && <div className="spinner-border spinner-border-sm" role="status"><span className="visually-hidden">Loading...</span></div>}
              </>
            ) : (
              <p className="text-muted mb-1">Aucune entreprise trouvée.</p>
            )}
          </div>
          
          <button className="btn btn-cta w-100 mb-4" onClick={onAddCompanyClick}>
            {/* ... SVG icône plus ... */} Ajouter une entreprise
          </button>

          <nav className="sidebar-nav">
             <a href="#" className={`nav-link ${activeSection === "alertes" ? "active" : ""}`} onClick={() => { setActiveSection("alertes"); setSidebarOpen(false); }}>
              {/* ... SVG icône cloche ... */} Alertes & Résultats
            </a>
            <a href="#" className={`nav-link ${activeSection === "veille" ? "active" : ""}`} onClick={() => { setActiveSection("veille"); setSidebarOpen(false); }}>
              {/* ... SVG icône document ... */} Publications officielles
            </a>
            <a href="#" className={`nav-link ${activeSection === "profil" ? "active" : ""}`} onClick={() => { setActiveSection("profil"); setSidebarOpen(false); }}>
              {/* ... SVG icône profil ... */} Profil
            </a>
          </nav>
        </div>

        <div className="sidebar-footer">
          <button className="btn btn-outline-light w-100" onClick={onLogout}>
            {/* ... SVG icône déconnexion ... */} Déconnexion
          </button>
        </div>
      </div>
    </>
  );
};

export default Sidebar;
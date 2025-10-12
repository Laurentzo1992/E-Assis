import React, { useState, useEffect } from 'react';
import useApi from '../../hooks/useApi';
import Spinner from '../ui/Spinner';
import VeilleFilters from '../veille/VeilleFilters'; // Composant pour les filtres
import PublicationList from '../veille/PublicationList'; // Composant pour la liste des publications
import PublicationDetailModal from '../veille/PublicationDetailModal'; // Composant pour le modal de détail

/**
 * @file VeilleSection.jsx
 * @description Composant principal pour la section "Veille & Documents".
 * Gère l'état des filtres, effectue les appels API pour récupérer les publications filtrées,
 * et orchestre l'affichage des filtres, de la liste et du modal de détail.
 */

/**
 * Composant VeilleSection.
 * @param {Object} props - Les props du composant.
 * @param {Object|null} props.activeCompany - L'entreprise active.
 * @param {Array<Object>} props.apiDomainesActivite - La liste des domaines d'activité disponibles.
 * @param {boolean} props.loadingDomaines - État de chargement des domaines.
 * @param {Error|null} props.errorDomaines - Erreur lors du chargement des domaines.
 */
const VeilleSection = ({ activeCompany, apiDomainesActivite, loadingDomaines, errorDomaines }) => {
  // --- État pour les filtres ---
  const [filters, setFilters] = useState({
    domaineId: '', // On utilisera l'ID pour plus de précision
    dateDebut: '',
    dateFin: '',
    search: '', // Ajout d'un champ de recherche textuelle
  });

  // --- État pour le modal de détail ---
  const [selectedPublication, setSelectedPublication] = useState(null);
  const [showDetailModal, setShowDetailModal] = useState(false);

  // --- Construction dynamique de l'endpoint API basé sur les filtres ---
  // On utilise URLSearchParams pour construire proprement la query string.
  const queryParams = new URLSearchParams();
  if (filters.domaineId) queryParams.append('domaine_id', filters.domaineId);
  if (filters.dateDebut) queryParams.append('date_publication__gte', filters.dateDebut); // gte = greater than or equal
  if (filters.dateFin) queryParams.append('date_publication__lte', filters.dateFin); // lte = less than or equal
  if (filters.search) queryParams.append('search', filters.search); // Utilise le 'search_fields' du backend
  
  const endpoint = `backend/publications/?${queryParams.toString()}`;

  // --- Appel API avec le hook useApi ---
  // Le hook se redéclenchera automatiquement à chaque fois que `endpoint` change,
  // c'est-à-dire à chaque modification des filtres.
  const { data: publications, loading, error } = useApi(endpoint, {}, [endpoint]);

  // Ouvre le modal avec les détails de la publication sélectionnée
  const handleViewPublication = (publication) => {
    setSelectedPublication(publication);
    setShowDetailModal(true);
  };

  return (
    <div className="main-content">
      <div className="content-header">
        <h2>Veille & Documents</h2>
        <p className="text-muted">Consultez et filtrez les publications officielles</p>
      </div>

      {/* --- Composant des filtres --- */}
      <VeilleFilters
        filters={filters}
        setFilters={setFilters}
        domaines={apiDomainesActivite}
        loadingDomaines={loadingDomaines}
        errorDomaines={errorDomaines}
      />

      {/* --- Contenu principal : liste des publications --- */}
      <div className="card">
        <div className="card-header">
          <h5 className="mb-0">Publications récentes</h5>
        </div>
        <div className="card-body">
          {loading && <Spinner message="Recherche des publications..." />}
          {error && (
            <div className="alert alert-danger">
              Erreur lors du chargement des publications : {error.message}
            </div>
          )}
          {!loading && !error && (
            <PublicationList
              publications={publications || []}
              onViewClick={handleViewPublication}
            />
          )}
        </div>
      </div>
      
      {/* --- Modal de détail de la publication --- */}
      <PublicationDetailModal
        show={showDetailModal}
        publication={selectedPublication}
        onClose={() => setShowDetailModal(false)}
      />
    </div>
  );
};

export default VeilleSection;
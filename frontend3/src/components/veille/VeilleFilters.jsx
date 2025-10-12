import React from 'react';

/**
 * @file VeilleFilters.jsx
 * @description Composant de formulaire contenant les filtres pour la section de veille.
 * Il est contrôlé par son parent (`VeilleSection`) via les props.
 */
const VeilleFilters = ({ filters, setFilters, domaines, loadingDomaines, errorDomaines }) => {
  
  /**
   * Gère les changements sur n'importe quel champ de filtre.
   * @param {React.ChangeEvent<HTMLInputElement|HTMLSelectElement>} e - L'événement de changement.
   */
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFilters(prevFilters => ({
      ...prevFilters,
      [name]: value,
    }));
  };

  return (
    <div className="card mb-4">
      <div className="card-header">
        <h5 className="mb-0">Filtres</h5>
      </div>
      <div className="card-body">
        <div className="row g-3 align-items-end">
          
          {/* Filtre par Date de début */}
          <div className="col-lg-3 col-md-6">
            <label htmlFor="dateDebut" className="form-label">Date de début</label>
            <input
              type="date"
              id="dateDebut"
              name="dateDebut"
              className="form-control"
              value={filters.dateDebut}
              onChange={handleChange}
            />
          </div>
          {/* Filtre par Date de fin */}
          <div className="col-lg-3 col-md-6">
            <label htmlFor="dateFin" className="form-label">Date de fin</label>
            <input
              type="date"
              id="dateFin"
              name="dateFin"
              className="form-control"
              value={filters.dateFin}
              onChange={handleChange}
            />
          </div>
          {/* Filtre par Recherche textuelle */}
          <div className="col-lg-3 col-md-6">
            <label htmlFor="search" className="form-label">Recherche</label>
             <input
              type="search"
              id="search"
              name="search"
              className="form-control"
              placeholder="Titre, N° revue..."
              value={filters.search}
              onChange={handleChange}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default VeilleFilters;
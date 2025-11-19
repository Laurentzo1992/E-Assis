import React, { useState } from 'react';
import Button from '../ui/Button';

const NotificationFilters = ({ filters, setFilters, loading }) => {
  const [showFilters, setShowFilters] = useState(true);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFilters(prev => ({ ...prev, [name]: value }));
  };

  const handleReset = () => {
    setFilters({ type: '', status: '', search: '' });
  };

  return (
    <div className="card mb-4 shadow-sm" style={{ borderRadius: '12px' }}>
      {/* Header cliquable */}
      <div
        className="card-header d-flex justify-content-between align-items-center"
        onClick={() => setShowFilters(!showFilters)}
        style={{ cursor: 'pointer', userSelect: 'none', backgroundColor: '#f8f9fa', borderRadius: '12px 12px 0 0' }}
      >
        <h5 className="mb-0 fw-bold">Filtres</h5>
        <span className="fs-5">{showFilters ? '▲' : '▼'}</span>
      </div>

      {/* Corps des filtres */}
      {showFilters && (
        <div className="card-body">
          <fieldset disabled={loading}>
            <div className="row g-3">
              {/* Type */}
              <div className="col-md-4">
                <label htmlFor="type" className="form-label fw-semibold">Type de notification</label>
                <select
                  id="type"
                  name="type"
                  className="form-select"
                  value={filters.type}
                  onChange={handleChange}
                  style={{ borderRadius: '8px' }}
                >
                  <option value="">Tous les types</option>
                  <option value="DOMAINE">Nouvelles Opportunités</option>
                  <option value="ENTREPRISE_SPECIFIQUE">Résultats de Marchés</option>
                </select>
              </div>

              {/* Statut */}
              <div className="col-md-4">
                <label htmlFor="status" className="form-label fw-semibold">Statut</label>
                <select
                  id="status"
                  name="status"
                  className="form-select"
                  value={filters.status}
                  onChange={handleChange}
                  style={{ borderRadius: '8px' }}
                >
                  <option value="">Tous</option>
                  <option value="false">Non lues</option>
                  <option value="true">Lues</option>
                </select>
              </div>

              {/* Recherche */}
              <div className="col-md-4">
                <label htmlFor="search" className="form-label fw-semibold">Recherche par mot-clé</label>
                <input
                  type="search"
                  id="search"
                  name="search"
                  className="form-control"
                  placeholder="Objet du marché..."
                  value={filters.search}
                  onChange={handleChange}
                  style={{ borderRadius: '8px' }}
                />
              </div>
            </div>

            <hr className="my-3"/>

            {/* Bouton Réinitialiser */}
            <div className="text-end">
              <Button variant="outline-secondary" onClick={handleReset}>
                Réinitialiser
              </Button>
            </div>
          </fieldset>
        </div>
      )}
    </div>
  );
};

export default NotificationFilters;

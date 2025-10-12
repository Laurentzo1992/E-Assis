import React, { useState, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import useApi from '../../hooks/useApi';
import { apiRequest } from '../../services/api';
import Spinner from '../ui/Spinner';
import NotificationItem from '../notifications/NotificationItem';
import NotificationFilters from '../notifications/NotificationFilters';


const groupNotificationsByDate = (notifications) => {
  const groups = { "Aujourd'hui": [], "Hier": [], "Cette semaine": [], "Plus ancien": [] };
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  const oneWeekAgo = new Date();
  oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);

  notifications.forEach(notif => {
    const notifDate = new Date(notif.created_at);
    if (notifDate.toDateString() === today.toDateString()) groups["Aujourd'hui"].push(notif);
    else if (notifDate.toDateString() === yesterday.toDateString()) groups["Hier"].push(notif);
    else if (notifDate > oneWeekAgo) groups["Cette semaine"].push(notif);
    else groups["Plus ancien"].push(notif);
  });
  return groups;
};


const NotificationsSection = ({ activeCompany, showCustomAlert }) => {
  const [filters, setFilters] = useState({ type: '', status: '', search: '' });
  const navigate = useNavigate(); // Hook pour gérer la navigation

  const queryParams = useMemo(() => {
    const params = new URLSearchParams();
    if (activeCompany) params.append('entreprise', activeCompany.id);
    if (filters.type) params.append('type_notification', filters.type);
    if (filters.status) params.append('lu', filters.status);
    if (filters.search) params.append('search', filters.search);
    return params.toString();
  }, [filters, activeCompany]);

  const endpoint = activeCompany ? `backend/notifications/?${queryParams}` : null;
  
  const { data: notifications, loading, error, setData: setNotifications } = useApi(endpoint, {}, [endpoint]);

  const groupedNotifications = useMemo(() => {
    return notifications ? groupNotificationsByDate(notifications) : {};
  }, [notifications]);

  const handleNotificationClick = useCallback(async (notification) => {
    if (!notification.lu) {
      setNotifications(currentNotifs => 
        currentNotifs.map(n => n.id === notification.id ? { ...n, lu: true } : n)
      );
      try {
        await apiRequest(`backend/notifications/${notification.id}/`, {
          method: 'PATCH',
          body: JSON.stringify({ lu: true }),
        });
      } catch (err) {
        showCustomAlert("Erreur lors du marquage de la notification.", "danger");
        // Rollback en cas d'erreur
        setNotifications(currentNotifs => 
          currentNotifs.map(n => n.id === notification.id ? { ...n, lu: false } : n)
        );
      }
    }
    
    // 2. Naviguer vers la page de détail
    navigate(`/marche/${notification.marche}`);

  }, [setNotifications, showCustomAlert, navigate]);

  return (
    <div className="main-content">
      <div className="mb-5 p-4 rounded shadow-sm d-flex flex-column flex-md-row align-items-md-center justify-content-between" style={{ backgroundColor: '#f8f9fa' }}>
  <div className="d-flex align-items-center mb-3 mb-md-0 gap-3">
    {/* Icône */}
    <span style={{ fontSize: '2rem' }}>🔔</span>
    <div>
      <h2 className="fw-bold mb-1" style={{ fontSize: '1.75rem', lineHeight: '1.2' }}>Centre de Notifications</h2>
      <p className="text-muted mb-0" style={{ fontSize: '0.95rem' }}>
        Gérez vos alertes et résultats pour <strong>{activeCompany?.nom}</strong>
      </p>
    </div>
  </div>
</div>


      <NotificationFilters filters={filters} setFilters={setFilters} loading={loading} />

      {loading && <Spinner message="Mise à jour des notifications..." />}
      {error && <div className="alert alert-danger">Erreur: {error.message}</div>}
      
      {!loading && !error && notifications && (
        notifications.length === 0 ? (
          <div className="text-center p-5 bg-light rounded">
             <h4 className="h2">📥</h4>
             <h4>Boîte de réception vide</h4>
             <p className="text-muted">Aucune notification ne correspond à vos filtres. Essayez de les ajuster ou de les réinitialiser.</p>
          </div>
        ) : (
          Object.entries(groupedNotifications).map(([group, notifs]) => 
            notifs.length > 0 && (
              <div key={group} className="mb-4">
                <h4 className="mb-3 border-bottom pb-2">{group}</h4>
                <div className="row g-4">
                  {notifs.map((notification) => (
                    <div key={notification.id} className="col-12 col-lg-6">
                      {/* On passe la nouvelle fonction en prop */}
                      <NotificationItem notification={notification} onNotificationClick={handleNotificationClick} />
                    </div>
                  ))}
                </div>
              </div>
            )
          )
        )
      )}
    </div>
  );
};

export default NotificationsSection;
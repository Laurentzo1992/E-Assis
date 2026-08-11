"""Site d'administration (sqladmin, monte sous /admin) - reserve aux comptes is_staff/is_superuser.

Choisi plutot qu'un ecran /admin custom cote React : sqladmin genere directement les vues
liste/detail/creation/edition a partir des modeles SQLAlchemy deja definis dans api/models/, ce qui
couvre l'essentiel des besoins identifies (gerer les utilisateurs/entreprises, corriger les
publications/marches/resultats a la main, ajuster un abonnement) sans dupliquer cette logique dans
le frontend. Authentification distincte du JWT du reste de l'API : sqladmin utilise sa propre
session signee par cookie (Starlette SessionMiddleware), verifiee ici contre les memes comptes
Utilisateur/mot de passe que le reste du systeme.
"""

from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import select
from starlette.requests import Request

from api.config import settings
from api.database import SessionLocal, engine
from api.models.abonnement import Abonnement, Paiement
from api.models.backend import Alerte, AppelOffre, Lot, Marche, Publication, Resultat, TypeProcedure
from api.models.entreprise import Domaine, Entreprise, SecteurActivite
from api.models.tarif import TarifAbonnement
from api.models.utilisateur import Utilisateur
from api.security import verify_password


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        email = form.get("username", "")
        password = form.get("password", "")

        db = SessionLocal()
        try:
            user = db.scalar(select(Utilisateur).where(Utilisateur.email == email))
        finally:
            db.close()

        if user is None or not verify_password(password, user.password_hash):
            return False
        if not (user.is_staff or user.is_superuser):
            return False

        request.session.update({"user_id": user.id})
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        user_id = request.session.get("user_id")
        if user_id is None:
            return False

        # Revalide a chaque requete (pas seulement au login) : un compte desactive ou retire du
        # staff apres coup ne doit pas garder l'acces via une session deja ouverte.
        db = SessionLocal()
        try:
            user = db.get(Utilisateur, user_id)
        finally:
            db.close()

        return user is not None and user.is_active and (user.is_staff or user.is_superuser)


class UtilisateurAdmin(ModelView, model=Utilisateur):
    category = "Comptes"
    column_list = [
        Utilisateur.id, Utilisateur.email, Utilisateur.is_active, Utilisateur.is_staff,
        Utilisateur.is_superuser, Utilisateur.notifications_actives, Utilisateur.date_joined,
        Utilisateur.last_login,
    ]
    column_searchable_list = [Utilisateur.email]
    form_excluded_columns = [
        Utilisateur.password_hash, Utilisateur.activation_token, Utilisateur.activation_token_created_at,
        Utilisateur.owned_entreprises, Utilisateur.active_entreprise,
    ]
    # La creation d'un utilisateur exige un hachage de mot de passe (cf. api/security.py) que le
    # formulaire generique ne sait pas produire - passe par /api/auth/register/ a la place.
    can_create = False
    # Suppression bloquee : casserait les entreprises/abonnements lies (owner_id) sans le
    # confirmer explicitement ailleurs - desactiver via is_active est le chemin sur.
    can_delete = False


class EntrepriseAdmin(ModelView, model=Entreprise):
    category = "Comptes"
    column_list = [
        Entreprise.id, Entreprise.nom, Entreprise.numero_identification, Entreprise.owner,
        Entreprise.telephone, Entreprise.email,
    ]
    column_searchable_list = [Entreprise.nom, Entreprise.numero_identification, Entreprise.rccm]


class AbonnementAdmin(ModelView, model=Abonnement):
    category = "Abonnements"
    column_list = [
        Abonnement.id, Abonnement.entreprise, Abonnement.statut, Abonnement.date_fin_essai,
        Abonnement.date_fin_abonnement,
    ]
    # Un essai est cree automatiquement a la creation de l'entreprise (cf. api/routers/entreprise.py) -
    # en creer un second via l'admin romprait la contrainte d'unicite sur entreprise_id.
    can_create = False
    # Le seul champ qu'un admin doit modifier a la main est le statut/la date de fin (ex. acces
    # accorde manuellement en attendant CinetPay) - laisser can_delete=False pour ne jamais priver
    # une entreprise de tout abonnement (le join dans match_and_alert.py suppose sa presence).
    can_delete = False


class PaiementAdmin(ModelView, model=Paiement):
    category = "Abonnements"
    column_list = [
        Paiement.id, Paiement.abonnement, Paiement.reference, Paiement.fournisseur, Paiement.montant,
        Paiement.devise, Paiement.statut, Paiement.date_creation, Paiement.date_confirmation,
    ]
    column_searchable_list = [Paiement.reference]
    # Historique financier : jamais cree ni supprime depuis l'admin (uniquement par
    # api/routers/paiement.py) - modifiable seulement pour corriger un statut en cas de support.
    can_create = False
    can_delete = False


class TarifAdmin(ModelView, model=TarifAbonnement):
    category = "Abonnements"
    name = "Tarif"
    name_plural = "Tarif"
    column_list = [TarifAbonnement.prix_annuel, TarifAbonnement.devise, TarifAbonnement.essai_gratuit_jours]
    # Ligne unique (cf. api/models/tarif.py, get_tarif) - ni creation (ambiguite sur laquelle fait
    # foi) ni suppression (le paiement en cours et la landing page en dependent).
    can_create = False
    can_delete = False


class PublicationAdmin(ModelView, model=Publication):
    category = "Marchés publics"
    column_list = [Publication.id, Publication.titre, Publication.numero, Publication.date_publication, Publication.source]
    column_searchable_list = [Publication.titre, Publication.numero]


class MarcheAdmin(ModelView, model=Marche):
    category = "Marchés publics"
    column_list = [Marche.id, Marche.publication, Marche.objet, Marche.ministere, Marche.region, Marche.budget_min, Marche.budget_max]
    column_searchable_list = [Marche.objet]


class AppelOffreAdmin(ModelView, model=AppelOffre):
    category = "Marchés publics"
    name_plural = "Appels d'offres"
    column_list = [AppelOffre.marche, AppelOffre.dateDepot, AppelOffre.referenceDossier]
    column_searchable_list = [AppelOffre.referenceDossier]


class ResultatAdmin(ModelView, model=Resultat):
    category = "Marchés publics"
    # Le principal cas d'usage attendu ici : corriger un marche mal classe (cf. session d'audit qui
    # a necessite des correctifs SQL manuels) en liant directement le bon entreprise_attributaire.
    # entreprise_attributaire_nom (texte brut extrait par le LLM) reste affiche meme quand aucune
    # Entreprise inscrite ne correspond - c'est le cas de la grande majorite des resultats reels.
    column_list = [
        Resultat.marche, Resultat.date_attribution, Resultat.entreprise_attributaire_nom,
        Resultat.entreprise_attributaire, Resultat.montant_attribue, Resultat.reference_decision,
    ]
    column_searchable_list = [Resultat.entreprise_attributaire_nom]


class LotAdmin(ModelView, model=Lot):
    category = "Marchés publics"
    column_list = [Lot.id, Lot.marche, Lot.numero_lot, Lot.description, Lot.montant]


class TypeProcedureAdmin(ModelView, model=TypeProcedure):
    category = "Marchés publics"
    name_plural = "Types de procédure"
    column_list = [TypeProcedure.id, TypeProcedure.libelle, TypeProcedure.description]


class DomaineAdmin(ModelView, model=Domaine):
    category = "Marchés publics"
    column_list = [Domaine.id, Domaine.libelle, Domaine.description]


class SecteurActiviteAdmin(ModelView, model=SecteurActivite):
    category = "Marchés publics"
    name_plural = "Secteurs d'activité"
    column_list = [SecteurActivite.id, SecteurActivite.nom, SecteurActivite.description]


class AlerteAdmin(ModelView, model=Alerte):
    category = "Alertes"
    column_list = [
        Alerte.id, Alerte.entreprise, Alerte.publication, Alerte.type_alerte, Alerte.canal_alerte,
        Alerte.lu, Alerte.date_alerte,
    ]
    # Generees uniquement par api/scripts/match_and_alert.py - l'admin ne fait que consulter (support/
    # debug) et supprimer une alerte erronee (cf. les 2 fausses alertes nettoyees manuellement cette
    # session), jamais en creer ou en modifier le contenu a la main.
    can_create = False
    can_edit = False


def init_admin(app) -> Admin:
    secret_key = settings.admin_session_secret_key or settings.jwt_secret_key
    admin = Admin(app, engine, authentication_backend=AdminAuth(secret_key=secret_key))

    for view in [
        UtilisateurAdmin, EntrepriseAdmin, AbonnementAdmin, PaiementAdmin, TarifAdmin, PublicationAdmin,
        MarcheAdmin, AppelOffreAdmin, ResultatAdmin, LotAdmin, TypeProcedureAdmin, DomaineAdmin,
        SecteurActiviteAdmin, AlerteAdmin,
    ]:
        admin.add_view(view)

    return admin

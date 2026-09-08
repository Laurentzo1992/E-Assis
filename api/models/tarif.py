"""Tarification de l'abonnement annuel, geree en base plutot qu'en variables d'environnement -
modifiable a chaud depuis le site d'administration (api/admin.py) sans redeploiement.

Table a une seule ligne (comme un singleton de configuration) : `get_tarif` recupere toujours la
plus recente, `api/admin.py` interdit d'en creer une seconde (can_create=False) pour eviter toute
ambiguite sur laquelle fait foi.
"""

from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from api.database import Base


class TarifAbonnement(Base):
    __tablename__ = "tarifs_abonnement"

    id: Mapped[int] = mapped_column(primary_key=True)
    prix_annuel: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    devise: Mapped[str] = mapped_column(String(3), default="XOF")
    essai_gratuit_jours: Mapped[int]

    def __str__(self) -> str:
        return f"{self.prix_annuel} {self.devise} / an - essai {self.essai_gratuit_jours}j"


def get_tarif(db: Session) -> TarifAbonnement:
    """La ligne unique de tarification. La migration f... (voir alembic/versions) en seme toujours
    une a l'application - si elle manquait malgre tout (base restauree partiellement, etc.), une
    erreur claire vaut mieux qu'un prix ou un essai silencieusement a 0."""
    tarif = db.query(TarifAbonnement).order_by(TarifAbonnement.id.desc()).first()
    if tarif is None:
        raise RuntimeError(
            "Aucun tarif configure en base (table tarifs_abonnement vide) - "
            "verifier que la migration l'ayant creee a bien ete appliquee."
        )
    return tarif

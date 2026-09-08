"""Tache DAG independante (cf. dags/dag_kbbot_quotidien.py) : reanalyse les entreprises dont le
profil (domaines/secteurs) a change depuis le dernier passage, contre les marches encore ouverts
et recents (tous bulletins confondus). Ne depend d'aucun nouveau bulletin - tourne tous les jours,
meme un jour sans publication DGCMEF. Logique complete dans
api/scripts/match_and_alert.py:rattraper_profils_modifies.
"""

import argparse

from api.scripts.match_and_alert import RATTRAPAGE_FENETRE_JOURS, rattraper_profils_modifies


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rattrape les entreprises dont le profil (domaines/secteurs) a change"
    )
    parser.add_argument(
        "--jours",
        type=int,
        default=RATTRAPAGE_FENETRE_JOURS,
        help=f"Fenetre de recherche des marches encore ouverts (defaut : {RATTRAPAGE_FENETRE_JOURS} jours)",
    )
    args = parser.parse_args()
    n = rattraper_profils_modifies(jours=args.jours)
    print(f"{n} alertes de rattrapage envoyees")


if __name__ == "__main__":
    main()

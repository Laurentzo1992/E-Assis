# entreprise/management/commands/generate_entreprises.py

import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from entreprise.models import Entreprise, Domaine, SecteurActivite

class Command(BaseCommand):
    help = "Génère 20 entreprises aléatoires d'origine Burkina Faso avec domaines et secteurs"

    def handle(self, *args, **kwargs):
        # Liste des domaines par défaut
        domaines_default = [
            {"libelle": "Informatique", "description": "Domaine IT"},
            {"libelle": "Agriculture", "description": "Domaine agricole"},
            {"libelle": "Commerce", "description": "Domaine commercial"},
            {"libelle": "Finance", "description": "Domaine financier"},
            {"libelle": "Santé", "description": "Domaine médical"},
        ]

        # Liste des secteurs par défaut
        secteurs_default = [
            {"nom": "SaaS", "description": "Logiciel en cloud"},
            {"nom": "E-commerce", "description": "Vente en ligne"},
            {"nom": "Transport", "description": "Transport et logistique"},
            {"nom": "BTP", "description": "Bâtiment et travaux publics"},
            {"nom": "Éducation", "description": "Secteur éducatif"},
        ]

        # Création ou récupération des domaines
        for d in domaines_default:
            Domaine.objects.get_or_create(libelle=d['libelle'], defaults={"description": d['description']})

        # Création ou récupération des secteurs
        for s in secteurs_default:
            SecteurActivite.objects.get_or_create(nom=s['nom'], defaults={"description": s['description']})

        domaines = list(Domaine.objects.all())
        secteurs = list(SecteurActivite.objects.all())

        noms_entreprises = [
            "Société FasoTech", "Burkina Agro", "Ouaga Services", "Bobo Industries",
            "Société Sahel", "FasoCom", "Ouaga Transport", "Bobo Solutions",
            "Burkina Energie", "Faso Agroalimentaire", "Ouaga Informatique",
            "Bobo Construction", "Faso Textile", "Ouaga Médical", "Bobo Électronique",
            "Burkina Finance", "Faso BTP", "Ouaga Énergie", "Bobo Agro", "Faso Logistique"
        ]

        noms_rep = ["Kaboré", "Ouédraogo", "Zongo", "Sawadogo", "Traoré", "Compaoré"]
        prenoms_rep = ["Abdoulaye", "Fatoumata", "Issa", "Aminata", "Moussa", "Salimata"]

        for i in range(20):
            nom = noms_entreprises[i % len(noms_entreprises)]
            numero_identification = f"IDBURK{i+1000:04d}"
            siret = f"{random.randint(10000000000000, 99999999999999)}"
            adresse = f"{random.randint(1, 100)} Rue de Ouaga"
            telephone = f"+226 {random.randint(60000000, 79999999)}"
            email = f"contact{i}@{nom.lower().replace(' ', '')}.bf"
            date_creation = datetime.now() - timedelta(days=random.randint(365, 3650))
            description = f"Entreprise spécialisée dans {random.choice(domaines).libelle.lower()}."
            repnom = random.choice(noms_rep)
            repprenom = random.choice(prenoms_rep)
            rccm = f"RC{random.randint(100000, 999999)}"

            entreprise = Entreprise.objects.create(
                nom=nom,
                numero_identification=numero_identification,
                siret=siret,
                adresse=adresse,
                telephone=telephone,
                email=email,
                date_creation=date_creation.date(),
                description=description,
                repnom=repnom,
                repprenom=repprenom,
                rccm=rccm
            )

            # Associer 1 à 3 domaines aléatoires
            domaines_choisis = random.sample(domaines, k=random.randint(1, min(3, len(domaines))))
            for domaine in domaines_choisis:
                entreprise.domaines.add(domaine)

            # Associer 1 à 2 secteurs aléatoires
            secteurs_choisis = random.sample(secteurs, k=random.randint(1, min(2, len(secteurs))))
            for secteur in secteurs_choisis:
                entreprise.secteurs.add(secteur)

            self.stdout.write(self.style.SUCCESS(f"Entreprise créée : {entreprise.nom}"))

        self.stdout.write(self.style.SUCCESS("Génération terminée."))

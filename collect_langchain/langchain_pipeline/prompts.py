SOMMAIRE_PROMPT = """
Voici le sommaire extrait d’un document PDF de marchés publics. Analyse-le et retourne une structure JSON listant chaque section principale, ses sous-sections, et les pages associées.

Sommaire :
{text}
"""

ENTITES_PROMPT = """
Voici un extrait d’un document de marchés publics. Analyse ce texte et retourne un JSON structuré des entités suivantes : Publication, Marche, Lot, Résultat, Entreprise, etc.

Texte :
{text}
"""

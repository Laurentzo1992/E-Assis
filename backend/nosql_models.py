# backend/nosql_models.py

from mongoengine import Document, fields

class DocumentBrut(Document):
    publication_id = fields.IntField(required=True)
    nom_fichier = fields.StringField(required=True)
    fichier_pdf = fields.FileField(required=True)
    date_telechargement = fields.DateTimeField()
    source = fields.StringField()
    meta = {'collection': 'documentsBruts'}

class DonneesExtraites(Document):
    publication_id = fields.IntField(required=True)
    texte_extrait = fields.StringField()
    date_extraction = fields.DateTimeField()
    meta = {'collection': 'donneesExtraites'}

class LotNoSQL(Document):
    marche_id = fields.IntField(required=True)
    numero_lot = fields.StringField()
    intitule = fields.StringField()
    montant = fields.DecimalField(precision=2)
    description = fields.StringField()
    meta = {'collection': 'lots'}

class JournalExtraction(Document):
    publication_id = fields.IntField()
    date_traitement = fields.DateTimeField()
    statut = fields.StringField()
    message = fields.StringField()
    meta = {'collection': 'journauxExtraction'}

class FichierAlerte(Document):
    entreprise_id = fields.IntField()
    marche_id = fields.IntField()
    message = fields.StringField()
    date_detection = fields.DateTimeField()
    valide = fields.BooleanField(default=False)
    meta = {'collection': 'fichierAlerte'}

class IndexRecherche(Document):
    publication_id = fields.IntField()
    texte_indexe = fields.StringField()
    meta = {'collection': 'indexRecherche'}

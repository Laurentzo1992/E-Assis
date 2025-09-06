from django.contrib import admin
from backend.models import ( TypeProcedure, Marche, AppelOffre, Resultat, Lot, Notification, Publication, Lot )

# Configuration pour le modèle Publication
@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    """
    Configuration de l'interface d'administration pour les Publications.
    Permet de suivre l'état du traitement de chaque revue PDF.
    """
    list_display = ('__str__', 'status', 'date_publication', 'marches_count')
    list_filter = ('status', 'date_publication')
    search_fields = ('title', 'numero_revue')
    date_hierarchy = 'date_publication'
    readonly_fields = ('created_at', 'updated_at')

    def marches_count(self, obj):
        """Affiche le nombre de marchés extraits de cette publication."""
        return obj.marches.count()
    marches_count.short_description = 'Marchés extraits'

# Configuration pour le modèle TypeProcedure
@admin.register(TypeProcedure)
class TypeProcedureAdmin(admin.ModelAdmin):
    """
    Configuration de l'interface d'administration pour les Types de Procédures.
    """
    list_display = ('libelle',)
    search_fields = ('libelle',)


class AppelOffreInline(admin.StackedInline):
    """
    Permet d'éditer les détails d'un Appel d'Offre directement
    depuis la page d'un Marché.
    """
    model = AppelOffre
    can_delete = False
    verbose_name_plural = 'Détails de l\'Appel d\'Offre'
    ordering_field = None

class ResultatInline(admin.StackedInline):
    """
    Permet d'éditer les détails d'un Résultat directement
    depuis la page d'un Marché.
    """
    model = Resultat
    can_delete = False
    verbose_name_plural = 'Détails du Résultat'
    ordering_field = None

class LotInline(admin.TabularInline):
    """
    Permet de voir et d'éditer les Lots liés à un Marché sous forme de tableau.
    C'est plus compact et lisible pour des listes.
    """
    model = Lot
    extra = 0  # N'affiche pas de formulaire de lot vide par défaut
    raw_id_fields = ('entreprise_concernee',) # Améliore la sélection d'entreprise si la liste est longue
    readonly_fields = ('statut', 'rang', 'motif')
    list_display = ('numero_lot', 'entreprise_concernee', 'statut', 'montant_propose')
    ordering_field = None

# Configuration pour le modèle Marche
@admin.register(Marche)
class MarcheAdmin(admin.ModelAdmin):
    """
    Configuration de l'interface d'administration pour les Marchés.
    C'est le point central pour visualiser les données extraites.
    """
    list_display = ('objet_court', 'ministere', 'type_procedure', 'publication', 'created_at')
    list_filter = ('type_procedure', 'ministere', 'region', 'publication__date_publication')
    search_fields = ('objet', 'ministere')
    date_hierarchy = 'created_at'
 
    inlines = [AppelOffreInline, ResultatInline, LotInline]

    def objet_court(self, obj):
        """Fonction pour afficher une version tronquée de l'objet dans la liste."""
        return (obj.objet[:75] + '...') if len(obj.objet) > 75 else obj.objet
    objet_court.short_description = 'Objet du Marché'



@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id", "type_notification", "entreprise", "marche",
        "domaine", "lot", "lu", "created_at"
    )
    list_filter = ("type_notification", "lu", "domaine", "marche")
    search_fields = ("message", "entreprise__nom", "marche__objet", "domaine__libelle", "lot__id")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (None, {
            "fields": (
                "type_notification", "entreprise", "marche",
                "domaine", "lot", "message", "lu"
            )
        }),
        ("Dates", {"fields": ("created_at", "updated_at")}),
    )



admin.site.register(Lot)
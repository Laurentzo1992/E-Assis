from django.contrib import admin
from .models import Entreprise, Domaine, SecteurActivite, EntrepriseDomaine, EntrepriseSecteur

class EntrepriseDomaineInline(admin.TabularInline):
    model = EntrepriseDomaine
    extra = 1

class EntrepriseSecteurInline(admin.TabularInline):
    model = EntrepriseSecteur
    extra = 1

@admin.register(Entreprise)
class EntrepriseAdmin(admin.ModelAdmin):
    list_display = ('nom', 'numero_identification', 'siret', 'email', 'telephone', 'date_creation')
    search_fields = ('nom', 'numero_identification', 'siret', 'email', 'repnom', 'repprenom')
    list_filter = ('date_creation',)
    ordering = ('nom',)

    fieldsets = (
        (None, {
            'fields': ('nom', 'numero_identification', 'siret', 'rccm')
        }),
        ('Contact', {
            'fields': ('email', 'telephone', 'adresse')
        }),
        ('Représentant', {
            'fields': ('repnom', 'repprenom')
        }),
        ('Informations supplémentaires', {
            'fields': ('date_creation', 'description')
        }),
    )

    inlines = [EntrepriseDomaineInline, EntrepriseSecteurInline]

@admin.register(Domaine)
class DomaineAdmin(admin.ModelAdmin):
    list_display = ('libelle', 'description')
    search_fields = ('libelle',)

@admin.register(SecteurActivite)
class SecteurActiviteAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description')
    search_fields = ('nom',)

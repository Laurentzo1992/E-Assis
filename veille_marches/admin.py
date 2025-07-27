from django.contrib import admin
from .models import Publication

@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'title', 'status', 'fichier_pdf')
    list_filter = ('status', 'date_publication')
    search_fields = ('title', 'numero_revue')
    actions = ['lancer_le_scraping_action']
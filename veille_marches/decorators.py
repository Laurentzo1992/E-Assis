from django.http import HttpResponseForbidden
from functools import wraps

def superuser_required(view_func):
    """
    Décorateur qui vérifie que l'utilisateur est bien un superuser.
    Si ce n'est pas le cas, il renvoie une réponse 403 Forbidden.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_superuser:
            return HttpResponseForbidden("<h1>Accès Interdit</h1><p>Vous n'avez pas les permissions nécessaires pour accéder à cette page.</p>")
        return view_func(request, *args, **kwargs)
    return _wrapped_view
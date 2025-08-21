from .utils import get_parametres_application


def app_params(request):
	"""Expose les paramètres d'application (nom, logo, etc.) aux templates."""
	params = get_parametres_application()
	return {
		'app_params': params,
	}



"""

esimCloud URL Configuration

"""

from django.contrib import admin
from django.urls import path
from simulationAPI import urls as simulationURLs
from authAPI.views import UserActivationView, GoogleOAuth2
from libAPI import urls as libURLs
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.conf.urls import url, include
schema_view = get_schema_view(
    openapi.Info(
        title="eSim Cloud API",
        default_version='v1',
        description="Public API Endpoints for eSim Cloud",
        license=openapi.License(name="GPLv3 License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)


urlpatterns = [
    path('api/admin/', admin.site.urls),

    # Simulation API Routes
    path('api/simulation/', include(simulationURLs)),
    path('api/', include(libURLs)),

    # Auth API Routes
    url(r'^api/auth/', include('djoser.urls')),
    url(r'^api/auth/', include('djoser.urls.authtoken')),
    url(r'^api/auth/', include("djoser.social.urls")),
    url(r'^api/auth/google-callback', GoogleOAuth2.as_view()),
    url(r'^api/auth/users/activate/(?P<uid>[\w-]+)/(?P<token>[\w-]+)/$',
        UserActivationView.as_view()),

    # For API Documentation
    url(r'^api/docs(?P<format>\.json|\.yaml)$',
        schema_view.without_ui(
            cache_timeout=0),
        name='schema-json'),

    path('api/docs', schema_view.with_ui(
        'swagger',
        cache_timeout=0),
        name='schema-swagger-ui'),

]

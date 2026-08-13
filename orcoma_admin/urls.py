"""
URL configuration for orcoma_admin project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as static_serve
from core.admin import admin_site
from core.views import frontend_index

urlpatterns = [
    path('admin/', admin_site.urls),
    path('', include('core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    # Serve the built Vite frontend (dist/) during development
    frontend_dist = settings.FRONTEND_DIST_DIR
    urlpatterns += [
        path('', frontend_index, name='frontend_index'),
        re_path(
            r'^(?P<path>assets/.*)$',
            static_serve,
            kwargs={'document_root': frontend_dist},
        ),
        re_path(
            r'^(?P<path>.*\.(?:png|jpe?g|gif|svg|webp|ico|txt|xml|json|webmanifest|woff2?|ttf|otf|eot))$',
            static_serve,
            kwargs={'document_root': frontend_dist},
        ),
    ]

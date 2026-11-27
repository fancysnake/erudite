from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from erudite.gates.web.django.book import book
from erudite.gates.web.django.home import home
from erudite.gates.web.django.open_library import open_library, open_library_queue

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("books/<int:book_id>/", book, name="book"),
    path("books/open-library/", open_library_queue, name="open_library_queue"),
    path("books/<int:book_id>/open-library/", open_library, name="open_library"),
    # The dev server is the only server: it also gives out the cover images.
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
]

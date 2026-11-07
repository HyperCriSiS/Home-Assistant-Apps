"""Offline browser fixture renders the unmodified pinned CWA templates with sample books."""

from pathlib import Path
from types import SimpleNamespace as NS
from datetime import datetime
import re, sys, os
from urllib.parse import urlencode
from flask import Flask, g, render_template

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rootfs/opt/ha-cwa"))
from modern_theme import install_modern_theme

source = Path(os.environ["CWA_SOURCE"]).resolve()
app = Flask(__name__, template_folder=str((source / "cps/templates").resolve()))


class User:
    locale = "de"
    is_authenticated = True
    is_anonymous = False
    name = "Leser"
    theme = 1
    email = ""
    kindle_mail = ""
    id = 1

    def role_upload(self):
        return True

    def __getattr__(self, key):
        return lambda *a, **k: False

    def check_visibility(self, *a):
        return True


user = User()
for p in (source / "cps/templates").glob("*.html"):
    for f in re.findall(r"\|\s*(\w+)", p.read_text(encoding="utf-8")):
        if f not in app.jinja_env.filters:
            app.jinja_env.filters[f] = lambda v, *a, **k: v
app.jinja_env.globals.update(
    _=lambda x, *a, **k: x,
    csrf_token=lambda: "fixture",
    url_for=lambda endpoint, **kw: (
        "/upload" if endpoint == "edit-book.upload" else
        "/library/aio-theme/" + kw["filename"]
        if endpoint == "aio_theme"
        else (
            "/static/" + kw["filename"]
            if endpoint == "static"
            else (
                "/cover/" + str(kw["book_id"])
                if endpoint == "web.get_cover"
                else "/library/?" + urlencode(kw)
            )
        )
    ),
)
app.jinja_env.filters["get_cover_srcset"] = lambda b: ""
app.jinja_env.filters["last_modified"] = lambda b: ""
app.jinja_env.filters["music"] = lambda b: False
install_modern_theme(app)
books = []
scenario = sys.argv[2] if len(sys.argv) > 2 else "books"
for i, (title, author) in enumerate(
    [
        ("Der stille Garten", "Mara Winter"),
        ("Zwischen den Zeilen", "Paul Berger"),
        ("Das blaue Haus", "Lena Sommer"),
        ("Wege durch die Nacht", "Jonas Feld"),
        ("Am anderen Ufer", "Nora Stein"),
        ("Ein neuer Morgen", "Emil Weber"),
    ]
    * 3
):
    b = NS(
        id=i + 1,
        title=title,
        authors=[NS(id=i + 1, name=author)],
        series=[],
        ratings=[],
        data=[NS(format="EPUB")],
        pubdate="",
        last_modified="",
        tags=[],
    )
    books.append(NS(Books=b))
with app.test_request_context("/"):
    g.current_theme = 1
    g.allow_upload = True
    g.google_site_verification = ""
    g.allow_anonymous = False
    g.shelves_access = []
    g.magic_shelves_access = []
    g.config_authors_max = 0
    sidebar = [
        dict(
            id=id,
            page=id,
            public=True,
            visibility=1,
            link="web.books_list",
            glyph=icon,
            text=label,
        )
        for id, icon, label in [
            ("books", "glyphicon-book", "Bücher"),
            ("author", "glyphicon-user", "Autoren"),
            ("series", "glyphicon-list", "Serien"),
            ("tags", "glyphicon-tag", "Schlagwörter"),
        ]
    ]
    lists = {
        "authors": ("Authors", "authorlist", "author", ["Carnegie, Dale", "Christie, Agatha", "Ende, Michael", "Winter, Mara"]),
        "categories": ("Categories", "catlist", "category", ["Biografie", "Roman", "Sachbuch"]),
        "downloads": ("Downloads", "downloadlist", "download", []),
        "downloads-filled": ("Downloads", "downloadlist", "download", ["Alex", "Mara"]),
        "languages": ("Languages", "langlist", "language", ["Deutsch", "English"]),
        "publishers": ("Publishers", "publisherlist", "publisher", ["Fischer", "Hanser"]),
        "series": ("Series", "serieslist", "series", ["Abenteuer", "Fantasie", "Geschichten"]),
    }
    title, page, data, names = lists.get(scenario, ("Bücher", "books", "", []))
    entries = [(NS(id=i + 1, name=name, sort=name.replace(', ', ' ') if data == 'author' else name,
                   format=None, rating=None), i + 1) for i, name in enumerate(names)]
    template = "list.html" if scenario in lists else "index.html"
    if scenario in ("series-grid", "series-grid-many"):
        title, page, data, template = "Series", "serieslist", "series", "grid.html"
        entries = []
        for i, book in enumerate(books[:7 if scenario == "series-grid-many" else 6]):
            book.Books.series = [NS(id=i+1, name=f"Sammlung {i+1}")]
            class SeriesRow(tuple):
                @property
                def count(self):
                    return 3
            entries.append(SeriesRow((book.Books,)))
    if scenario == "magic":
        title, page = "Sehr langer Name eines magischen Bücherregals", "magicshelf"
    duplicate_books = [NS(id=i+1, title="Der stille Garten", author_names="Mara Winter", timestamp=datetime(2026, 1, 1),
                          cover_url=f"/cover/{i+1}", series=[], data=[NS(format="EPUB")]) for i in range(2)]
    if scenario == "duplicates":
        title, page, template = "Duplicates", "duplicates", "duplicates.html"
    pagination = NS(page=6, pages=12, has_next=True, has_prev=True,
                    iter_pages=lambda: [1, None, 5, 6, 7, None, 12]) if scenario == "books-paged" else None
    html = render_template(
        template,
        current_user=user,
        instance="Calibre-Web",
        title=title,
        page=page,
        bodyClass="",
        entries=entries if scenario in lists or scenario.startswith("series-grid") else books,
        charlist=[(c,) for c in sorted({name[0] for name in names})] if not scenario.startswith("series-grid") else [NS(char="S")],
        data=data,
        random=[],
        order=1 if scenario in lists or scenario.startswith("series-grid") else (sys.argv[1] if len(sys.argv) > 1 else "abc"),
        accept=["epub", "pdf"],
        duplicate_groups=[NS(title="Der stille Garten", author="Mara Winter", count=2, group_hash="fixture", books=duplicate_books)],
        duplicate_index_needs_full_scan=False,
        shelf=NS(user_id=1),
        id=0,
        simple=True,
        sidebar=sidebar,
        cwa_settings={},
        magic_shelf_routes=NS(render=False, create=False),
        pagination=pagination,
        searchterm="",
        config=NS(),
    )
    print(html)

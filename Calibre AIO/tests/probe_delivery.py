"""Deliver a generated ebook through upstream Shelfmark's real output pipeline."""
from pathlib import Path
import sys
from threading import Event
from zipfile import ZipFile, ZIP_STORED

sys.path.insert(0, '/opt/ha-cwa')
import shelfmark_wsgi  # Apply the same deployment settings as the web service.
from shelfmark.core.models import DownloadTask
from shelfmark.download.outputs.folder import process_folder_output

source = Path('/data/shelfmark-staging/aio-smoke.epub')
with ZipFile(source, 'w') as epub:
    epub.writestr('mimetype', 'application/epub+zip', compress_type=ZIP_STORED)
    epub.writestr('META-INF/container.xml', '''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="book.opf" media-type="application/oebps-package+xml"/>
</rootfiles></container>''')
    epub.writestr('book.opf', '''<?xml version="1.0"?>
<package version="2.0" unique-identifier="id" xmlns="http://www.idpf.org/2007/opf">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="id">urn:uuid:aa00aa00-bb11-cc22-dd33-ee44ee44ee44</dc:identifier>
<dc:title>Calibre AIO Smoke Book</dc:title><dc:creator>Integration Test</dc:creator>
<dc:language>en</dc:language></metadata>
<manifest><item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>
<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/></manifest>
<spine toc="ncx"><itemref idref="chapter"/></spine></package>''')
    epub.writestr('chapter.xhtml', '''<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Integration Test</title></head><body><p>Generated test content.</p></body></html>''')
    epub.writestr('toc.ncx', '''<ncx version="2005-1" xmlns="http://www.daisy.org/z3986/2005/ncx/">
<head/><docTitle><text>Calibre AIO Smoke Book</text></docTitle><navMap>
<navPoint id="chapter" playOrder="1"><navLabel><text>Test</text></navLabel>
<content src="chapter.xhtml"/></navPoint></navMap></ncx>''')

events = []
result = process_folder_output(source, DownloadTask(
    task_id='aio-smoke', source='direct_download', title='Calibre AIO Smoke Book',
    author='Integration Test', format='epub', content_type='book (fiction)',
), Event(), lambda *event: events.append(event))
assert result and Path(result).is_file(), (result, events)
assert Path(result).resolve().is_relative_to(Path('/share/calibre-aio/ingest')), result
Path('/data/shelfmark-staging/probe-delivery-path').write_text(result)
print('Real Shelfmark output delivered the generated EPUB to persistent CWA ingest')

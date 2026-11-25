from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
from functools import partial
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
import re, runpy, threading, json
from playwright.sync_api import sync_playwright
root=(Path(__file__).resolve().parents[1]/'_build/html').resolve();parsed={};links=[]
class Page(HTMLParser):
 def __init__(self,path):super().__init__();self.path=path;self.ids=set()
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if 'id' in a:self.ids.add(a['id'])
  for key in ['href','src']:
   if key in a:links.append((self.path,a[key]))
for p in root.rglob('*.html'):
 if '_static' in p.relative_to(root).parts:continue
 page=Page(p);page.feed(p.read_text());parsed[p]=page.ids
broken=[];count=0
for source,url in links:
 u=urlsplit(url)
 if u.scheme or u.netloc:continue
 target=(source.parent/unquote(u.path)).resolve() if u.path else source
 if target.is_dir():target=target/'index.html'
 if not target.exists():broken.append((str(source.relative_to(root)),url,'missing file'));continue
 if u.fragment and target in parsed and unquote(u.fragment) not in parsed[target]:broken.append((str(source.relative_to(root)),url,'missing anchor'))
 count+=1
assert not broken,broken[:20]
print('HTML validation:',len(parsed),'pages;',count,'local references; no broken local links/anchors.')

repository = Path(__file__).resolve().parents[2]
app_version = runpy.run_path(str(repository / 'samstudio' / '__init__.py'))['__version__']
release_versions = re.findall(r'^# SAM Image Studio (\d+(?:\.\d+)+)$',
                              (repository / 'docs' / 'RELEASE_NOTES.md').read_text(), re.MULTILINE)
first_stable_version = '1.4.2'
assert release_versions[0] == app_version and first_stable_version in release_versions
visible_releases = {*release_versions[:5], '1.4.3', first_stable_version}
visible_versions = [version for version in release_versions if version in visible_releases]
legacy_archives = {
 path.name.removeprefix('SAM_Image_Studio_v').removesuffix('_CPU.zip'): path.name
 for path in (repository / 'uploads' / 'legacy-cpu').glob('SAM_Image_Studio_v*_CPU.zip')
}
archived_versions = sorted(
 (set(release_versions) | legacy_archives.keys()) - visible_releases,
 key=lambda version: tuple(map(int, version.split('.'))),
 reverse=True,
)


def check_version_table(table, versions):
 rows = table.locator('tbody tr')
 assert rows.count() == len(versions)
 for index, version in enumerate(versions):
  cells = rows.nth(index).locator('td')
  assert cells.nth(0).inner_text().split(' —', 1)[0] == version
  assert cells.nth(2).inner_text().strip(), version
  downloads = cells.nth(1)
  if version == first_stable_version:
   assert cells.nth(0).inner_text() == '1.4.2 — First stable version'
   stable = downloads.get_by_role('link', name='CPU ZIP', exact=True)
   assert stable.get_attribute('href').endswith('/uploads/SAM_Image_Studio_v1.4.2_CPU.zip')
  elif version in legacy_archives:
   archive = downloads.get_by_role('link', name='CPU ZIP', exact=True)
   assert archive.get_attribute('href').endswith(f'/uploads/legacy-cpu/{legacy_archives[version]}')
   if version == '1.4.0':
    assert cells.nth(0).inner_text() == '1.4.0 — ZIP filename'
    assert '1.5.0' in cells.nth(2).inner_text()
  else:
   docs_suffix = '-docs' if version == '1.4.5.1' else ''
   standard = downloads.get_by_role('link', name='Standard ZIP', exact=True)
   assert standard.get_attribute('href').endswith(f'/archive/refs/tags/v{version}{docs_suffix}.zip')
   if tuple(map(int, version.split('.'))) >= (1, 4, 4):
    offline = downloads.get_by_role('link', name='Offline CPU ZIP', exact=True)
    assert offline.get_attribute('href').endswith(f'/archive/refs/tags/v{version}-offline{docs_suffix}.zip')


class Quiet(SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(root)))
threading.Thread(target=server.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{server.server_port}'
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
 page=browser.new_page(viewport={'width':1440,'height':1050},device_scale_factor=1)
 errors=[];bad_resources=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('response',lambda r:bad_resources.append((r.status,r.url)) if r.status>=400 and r.url.startswith(base) else None)
 page.goto(base+'/index.html',wait_until='networkidle')
 assert page.locator('h1').inner_text()=='SAM Image Studio'
 for title in ['Installation','Image workflows','Documentation','Developer guide']:
  assert page.locator('.bd-header').get_by_role('link',name=title,exact=True).count()==1,title
 page.screenshot(path='/tmp/samstudio-website-desktop.png',full_page=True)
 page.get_by_role('link',name='SAM3.1 text & shape prompts',exact=True).click()
 page.wait_for_load_state('networkidle')
 assert 'sam31.html' in page.url
 assert page.get_by_role('heading',name='Text prompt recipe: black dots',exact=True).count()==1
 assert page.get_by_role('heading',name='Shape prompt recipe',exact=True).count()==1
 page.screenshot(path='/tmp/samstudio-website-sam31.png',full_page=False)
 page.goto(base+'/index.html',wait_until='networkidle')
 page.get_by_role('link',name='Download CPU versions',exact=True).click()
 page.wait_for_load_state('networkidle')
 assert page.url.endswith('/downloads.html')
 check_version_table(page.locator('article table').first, visible_versions)
 assert page.get_by_role('link', name='1.4.3', exact=True).is_visible()
 archive = page.locator('article details').filter(has_text='Show all versions')
 page.screenshot(path='/tmp/samstudio-downloads-desktop.png',full_page=True)
 if archived_versions:
  assert page.locator('#earlier-cpu-versions').count()==1
  assert not archive.locator('table').is_visible()
  archive.locator('summary').click()
  assert archive.locator('table').is_visible()
  check_version_table(archive.locator('table'), archived_versions)
  checksums = archive.get_by_role('link', name='SHA-256 checksums', exact=True)
  assert checksums.get_attribute('href').endswith('/uploads/legacy-cpu/SHA256SUMS')
  archive.locator('summary').click()
  assert not archive.locator('table').is_visible()
 page.goto(base+'/installation.html',wait_until='networkidle')
 headings=page.locator('article h2').all_text_contents()
 assert headings[0].startswith('First for every route:'),headings
 assert ':maxdepth:' not in page.locator('article').inner_text()
 assert 'conda activate sam-image-studio-gpu' in page.locator('article').inner_text()
 page.goto(base+'/installation-gpu.html',wait_until='networkidle')
 assert page.get_by_role('heading',name='1. Obtain the complete project first',exact=True).count()==1
 gpu_guide = page.locator('article')
 for command in ['cd /d "C:\\Work\\AI Projects\\', 'dir GPU\\install.py',
                 'nvidia-smi', 'conda env list', 'conda activate sam-image-studio-gpu',
                 'python GPU/install.py --current --sam3', 'python -m samstudio.selftest --device cuda']:
  assert command in gpu_guide.inner_text(), command
 assert 'CUDA UMD Version' in gpu_guide.inner_text()
 gpu_update = gpu_guide.locator('section#update-an-existing-installation')
 assert 'python GPU/install.py --current' in gpu_update.inner_text()
 assert 'conda create' not in gpu_update.inner_text()
 assert '{include}' not in gpu_guide.inner_text()
 page.goto(base+'/documentation/menus.html',wait_until='networkidle')
 assert page.get_by_role('heading',name='Processing',exact=True).count()==1
 assert page.get_by_text('Read pixel sizes from Excel…',exact=True).count()>=1
 assert page.get_by_text('Delete vertex',exact=True).count()>=1
 assert page.get_by_text('Delete objects',exact=True).count()>=1
 assert page.get_by_text('Filament → Draw filament connection…',exact=True).count()==1
 page.goto(base+'/user-manual.html#denoising-parameters',wait_until='networkidle')
 assert f'This manual covers SAM Image Studio {app_version}' in page.locator('article').inner_text()
 for section in ['denoising-parameters', 'target-size-range', 'scale-bars', 'distance-measurements',
                 'refine-disconnected-parts', 'mask-pusher', 'filaments-and-occluded-fragments',
                 'metric-colors-and-plot-groups', 'offline-cpu-edition', 'nvidia-gpu-with-conda',
                 'original-and-processed-input', 'model-manager-and-sam3-onnx', 'otsu-watershed',
                 'cleaning-and-reversible-image-records', 'local-plugins']:
  assert page.locator(f'article section#{section}').count()==1,section
 manual_versions = page.locator('article section#release-coverage tbody tr td:first-child').all_inner_texts()
 assert manual_versions == release_versions, manual_versions
 page.goto(base+'/features/annotation.html',wait_until='networkidle')
 assert page.get_by_role('heading',name='Push a mask boundary',exact=True).count()==1
 assert page.get_by_role('heading',name='Clean up disconnected mask parts',exact=True).count()==1
 page.goto(base+'/features/measurements.html',wait_until='networkidle')
 assert page.get_by_role('heading',name='Measure a line or curve',exact=True).count()==1
 assert page.get_by_role('heading',name='Share metric colors across a plot group',exact=True).count()==1
 assert page.locator('article').get_by_text('Histogram (mask colors)',exact=True).count()==1
 for path,heading in [('/features/cleaning.html','Data cleaning: remove, fill and restore'),('/segmentation/scopes.html','Seg scope: ROI, whole image and single object'),('/features/compressed-sensing.html','Compressed sensing: controls and suggested parameters'),('/segmentation/sam3-onnx.html','SAM3 ONNX: public text segmentation'),('/segmentation/watershed.html','Otsu + watershed: parameters and preview'),('/features/examples.html','Example microscopy images'),('/features/processing.html','Image restoration and processing')]:
  page.goto(base+path,wait_until='networkidle')
  assert page.get_by_role('heading',name=heading,exact=True).count()==1
  images=page.locator('article img').evaluate_all('(images) => images.map(i => ({src:i.src,loaded:i.complete && i.naturalWidth>0}))')
  assert images and all(i['loaded'] for i in images),images
 page.goto(base+'/installation-offline.html',wait_until='networkidle')
 assert 'offline-cache/READY' in page.locator('article').inner_text()
 assert 'SAM2.1 Base+' in page.locator('article').inner_text()
 page.goto(base+'/search.html?q=SAM3.1',wait_until='networkidle')
 page.wait_for_selector('.search li a',timeout=20000)
 print('Browser search returned:',page.locator('.search li a').count(),'result links.')
 mobile=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1,is_mobile=True,has_touch=True)
 mobile.goto(base+'/index.html',wait_until='networkidle')
 width=mobile.evaluate('({scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth})')
 assert width['scroll']<=width['client']+1,width
 mobile.screenshot(path='/tmp/samstudio-website-mobile.png',full_page=True)
 mobile.goto(base+'/downloads.html',wait_until='networkidle')
 width=mobile.evaluate('({scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth})')
 assert width['scroll']<=width['client']+1,width
 mobile.screenshot(path='/tmp/samstudio-downloads-mobile.png',full_page=True)
 assert mobile.get_by_role('link', name='1.4.3', exact=True).is_visible()
 assert mobile.get_by_text('1.4.2 — First stable version', exact=True).is_visible()
 if archived_versions:
  mobile_archive=mobile.locator('article details').filter(has_text='Show all versions')
  mobile_archive.locator('summary').click()
  assert mobile_archive.locator('table').is_visible()
  check_version_table(mobile_archive.locator('table'), archived_versions)
  width=mobile.evaluate('({scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth})')
  assert width['scroll']<=width['client']+1,width
 assert not errors,errors
 assert not bad_resources,bad_resources
 print('Browser validation passed: download list, shared source acquisition, readable GPU guide, desktop navigation, SAM3.1 guide, menu reference, search, mobile layout; no JS errors or missing local resources.')
 browser.close()
server.shutdown()

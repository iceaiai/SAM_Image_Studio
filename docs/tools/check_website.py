from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
from functools import partial
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
import threading,json
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
 downloads=page.locator('article').get_by_role('link',name='Download ZIP',exact=True)
 assert downloads.count()==2
 assert downloads.nth(0).get_attribute('href').endswith('/v1.4.3/SAM_Image_Studio_v1.4.3_CPU.zip')
 assert downloads.nth(1).get_attribute('href').endswith('/uploads/SAM_Image_Studio_v1.4.2_CPU.zip')
 page.screenshot(path='/tmp/samstudio-downloads-desktop.png',full_page=True)
 page.goto(base+'/installation.html',wait_until='networkidle')
 headings=page.locator('article h2').all_text_contents()
 assert headings[0].startswith('First for every route:'),headings
 assert ':maxdepth:' not in page.locator('article').inner_text()
 assert 'conda activate sam-image-studio-gpu' in page.locator('article').inner_text()
 page.goto(base+'/installation-gpu.html',wait_until='networkidle')
 assert page.get_by_role('heading',name='1. Obtain the complete project first',exact=True).count()==1
 assert 'python GPU/install.py --current --sam3' in page.locator('article').inner_text()
 assert '{include}' not in page.locator('article').inner_text()
 page.goto(base+'/documentation/menus.html',wait_until='networkidle')
 assert page.get_by_role('heading',name='Processing',exact=True).count()==1
 assert page.get_by_text('Read pixel sizes from Excel…',exact=True).count()>=1
 for path,heading in [('/features/cleaning.html','Data cleaning: remove, fill and restore'),('/segmentation/scopes.html','Seg scope: ROI, whole image and single object'),('/features/compressed-sensing.html','Compressed sensing: controls and suggested parameters'),('/segmentation/sam3-onnx.html','SAM3 ONNX: public text segmentation')]:
  page.goto(base+path,wait_until='networkidle')
  assert page.get_by_role('heading',name=heading,exact=True).count()==1
  images=page.locator('article img').evaluate_all('(images) => images.map(i => ({src:i.src,loaded:i.complete && i.naturalWidth>0}))')
  assert images and all(i['loaded'] for i in images),images
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
 assert not errors,errors
 assert not bad_resources,bad_resources
 print('Browser validation passed: download list, shared source acquisition, readable GPU guide, desktop navigation, SAM3.1 guide, menu reference, search, mobile layout; no JS errors or missing local resources.')
 browser.close()
server.shutdown()

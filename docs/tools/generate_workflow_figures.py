"""Reproduce documentation figures from public synthetic data and app algorithms.

No user image, token or downloaded model is used. Scope overlays are schematic
manual reference masks, explicitly not SAM predictions.
"""
from pathlib import Path
import json
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from scipy.ndimage import gaussian_filter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from samstudio.processing import neighbor_fill, patch_fill
from samstudio.image_processing import parameters
from samstudio.compressed_sensing import iterative_restore, sampling_mask

OUTPUT = ROOT / 'docs/source/_static/workflows'
OUTPUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.size': 11, 'axes.titlesize': 12, 'figure.facecolor': 'white'})

def save(fig, name):
    fig.savefig(OUTPUT / name, dpi=165, bbox_inches='tight')
    plt.close(fig)

rng = np.random.default_rng(7)
h, w = 192, 256
y, x = np.mgrid[:h, :w]
particles = [(42,48,15),(110,42,18),(191,50,16),(66,130,20),(145,123,17),(218,148,14)]
masks = [((x-cx)**2+(y-cy)**2 <= radius**2) for cx,cy,radius in particles]
base = .72 + .05*np.sin(x/37) + .02*np.cos(y/22)
reference = base.copy()
for mask in masks:
    reference[mask] = .16
reference = gaussian_filter(reference, .65)
image = np.clip(reference + rng.normal(0,.018,reference.shape),0,1)

def show(ax, a, title):
    ax.imshow(a, cmap='gray', vmin=0, vmax=1)
    ax.set_title(title)
    ax.set_xticks([]); ax.set_yticks([])

def outline(ax, mask, color='#13cba3'):
    if mask.any():ax.contour(mask.astype(float), levels=[.5], colors=[color], linewidths=1.6)

fig, axs = plt.subplots(1,4,figsize=(14,3.8),layout='constrained')
show(axs[0],image,'Draw an area prompt')
box=(19,25,48,48)
for ax in axs:
    ax.add_patch(Rectangle(box[:2],box[2],box[3],fill=False,edgecolor='#ffb020',linewidth=2))
show(axs[1],image,'Single object (native SAM)')
outline(axs[1],masks[0])
show(axs[2],image,'Inside ROI only + text')
roi=(x<128)&(y<160)
axs[2].patches[0].remove()
axs[2].add_patch(Rectangle((0,0),128,160,fill=False,edgecolor='#ffb020',linewidth=2))
for m in masks:outline(axs[2],m&roi)
axs[2].fill_betweenx([0,h],128,w,color='#ffffff',alpha=.4)
show(axs[3],image,'Prompt project, whole image')
for m in masks:outline(axs[3],m)
fig.suptitle('Scope comparison: manual reference-mask schematic, not model inference',fontsize=14)
fig.supxlabel('Amber = prompt / allowed region     Green = illustrative output masks',fontsize=11)
save(fig,'segmentation-scopes.png')

# Actual cleaning algorithms. The dark artificial contaminant is intentionally known.
contaminated=image.copy();target=((x-172)/21)**2+((y-153)/16)**2<1
contaminated[target]=.035
source=(x>174)&(x<214)&(y>79)&(y<105)
neighbor=neighbor_fill(contaminated,target)
patch=patch_fill(contaminated,target,[source])
assert np.array_equal(neighbor[~target],contaminated[~target])
assert np.array_equal(patch[~target],contaminated[~target])
fig,axs=plt.subplots(1,4,figsize=(14,3.9),layout='constrained')
for ax,a,title in zip(axs,[contaminated,contaminated,neighbor,patch],['1. Acquired + synthetic defect','2. Clean: select target / source','3. Fill from neighboring pixels','4. Fill with background patches']):show(ax,a,title)
outline(axs[1],target,'#ffb020');outline(axs[1],source,'#13cba3')
fig.suptitle('Data cleaning: real application algorithms on synthetic pixels',fontsize=14)
fig.supxlabel('Amber = removal target   Green = manual background patch   Original pixels are retained in native projects',fontsize=10)
save(fig,'cleaning-comparison.png')

# Scientific plots use the exact app implementation on normalized grayscale data.
noisy=np.clip(reference+rng.normal(0,.055,reference.shape),0,1).astype(np.float32)
p=parameters('DCT sparsity',{'task':'reconstruct','sample_fraction':.10,'iterations':40,'max_side':0})
observed=sampling_mask(noisy.shape,.10,'random',7)
recon=iterative_restore(noisy,'DCT sparsity',p)
tvparams=parameters('TV iterative (notebook)',{'task':'reconstruct','tv_step':.08,'max_side':0})
tv=iterative_restore(noisy,'TV iterative (notebook)',tvparams)
fig,axs=plt.subplots(1,5,figsize=(16,3.9),layout='constrained')
for ax,a,title in zip(axs,[reference,noisy,np.where(observed,noisy,np.nan),recon,tv],['Synthetic reference','Input + Gaussian noise','10% sampled pixels','DCT reconstruction, keep 8%','TV reconstruction, step 0.08']):show(ax,a,title)
fig.suptitle('Compressed sensing: simulated missing pixels, seed 7, 40 iterations, native 192 × 256 grid',fontsize=14)
fig.supxlabel('White sample gaps are unobserved; outputs are computed examples, not acquired specimen data.',fontsize=11)
save(fig,'compressed-sensing-overview.png')

fig,axs=plt.subplots(2,4,figsize=(14,7),layout='constrained')
show(axs[0,0],noisy,'Same noisy input')
show(axs[1,0],reference,'Synthetic reference')
for ax,fraction in zip(axs[0,1:],[.04,.08,.20]):
    out=iterative_restore(noisy,'DCT sparsity',parameters('DCT sparsity',{'sparsity_fraction':fraction,'iterations':40,'fidelity_step':.2,'max_side':0}))
    show(ax,out,f'DCT denoise: keep {fraction:.0%}')
for ax,step in zip(axs[1,1:],[.005,.01,.02]):
    out=iterative_restore(noisy,'TV iterative (notebook)',parameters('TV iterative (notebook)',{'tv_step':step,'iterations':40,'fidelity_step':.2,'max_side':0}))
    show(ax,out,f'TV denoise: step {step}')
fig.suptitle('Parameter comparison: denoise mode, all pixels, fixed input and display scale',fontsize=14)
fig.supxlabel('Inspect weak features, ringing and edge shape; these examples do not establish optimal settings for microscopy.',fontsize=10)
save(fig,'compressed-sensing-parameters.png')
(OUTPUT/'provenance.json').write_text(json.dumps({'data':'Synthetic particles, generated here; no user images or model predictions','seed':7,'scope_figure':'Manual reference-mask schematic','cleaning':'samstudio.processing.neighbor_fill and patch_fill; outside-target equality checked','restoration':'samstudio.compressed_sensing.iterative_restore; normalized float32; 192x256; 40 iterations; max_side=0'},indent=2)+'\n')
print(OUTPUT)

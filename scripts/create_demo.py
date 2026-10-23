"""Generate a reproducible, explicitly synthetic calibrated particle image."""
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter
import tifffile


def create(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(781)
    h,w=512,768;yy,xx=np.ogrid[:h,:w]
    image=1800+120*np.sin(xx/100)+rng.normal(0,90,(h,w))
    particles=[(120,115,34,31),(290,95,44,34),(480,110,29,38),(645,160,45,49),
               (150,325,46,37),(335,290,37,48),(525,330,52,36),(668,410,29,32),
               (310,435,23,22),(480,460,18,17)]
    for i,(x,y,rx,ry) in enumerate(particles):
        disk=((xx-x)/rx)**2+((yy-y)/ry)**2<=1
        image+=gaussian_filter(disk.astype(float),1.3)*(6500+i*300)
    image=np.rint(np.clip(image,0,65535)).astype(np.uint16)
    path=directory/"synthetic_particles.ome.tif"
    tifffile.imwrite(path,image,ome=True,metadata={"axes":"YX","PhysicalSizeX":.2,"PhysicalSizeXUnit":"nm",
        "PhysicalSizeY":.3,"PhysicalSizeYUnit":"nm","Description":"Synthetic test data, not an acquired microscopy image"})
    return path,particles


if __name__=="__main__":
    path,_=create(Path(__file__).resolve().parents[1]/"examples")
    print(path)

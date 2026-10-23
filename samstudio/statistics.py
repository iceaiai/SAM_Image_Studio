"""Deduplicated 2-D morphology measurements with explicit applicability."""
from __future__ import annotations
import math
import zlib
import cv2
import numpy as np
from scipy.ndimage import binary_fill_holes, binary_erosion, label
from scipy.spatial import ConvexHull, cKDTree, distance
from skimage.measure import find_contours
from .domain import LENGTH_UNITS

# dimension: 0 dimensionless, 1 length, 2 area, -1 degrees, -2 categorical
METRICS = {
 'area':('Projected area',2), 'diameter':('Equivalent circular diameter',1),
 'feret_max':('Maximum Feret diameter',1),'feret_min':('Minimum Feret diameter',1),
 'perimeter':('Perimeter',1),'centroid_x':('Centroid X',1),'centroid_y':('Centroid Y',1),
 'orientation':('Major-axis orientation',-1),'length':('Major-axis length',1),'width':('Minor-axis width',1),
 'aspect_ratio':('Aspect ratio',0),'circularity':('Circularity',0),'solidity':('Solidity',0),
 'side_length':('Regular-polygon side-length estimate',1),
 'corner_error':('Corner angle RMS error',-1),'edge_deviation':('Edge RMS deviation / ECD',0),
 'confidence':('Model confidence',0),'border_status':('Touches image border',0),
 'particle_count':('Particle count',0),'object_id':('Object ID',-2),
 'outer_size':('Outer-particle ECD',1),'core_size':('Core ECD',1),'shell_thickness':('Mean shell thickness',1),
 'center_displacement':('Core-center displacement',1),'normalized_displacement':('Displacement / outer ECD',0),
 'displacement_direction':('Core-displacement direction',-1),'shell_uniformity':('Shell thickness CV',0),
 'cavity_size':('Cavity ECD',1),'wall_thickness':('Mean wall thickness',1),
 'cavity_x':('Cavity centroid X',1),'cavity_y':('Cavity centroid Y',1),
 'wall_uniformity':('Wall thickness CV',0),
}


def boundary(mask, matrix, exterior_only=False):
    if exterior_only:
        mask=binary_fill_holes(mask)
    contours=find_contours(np.pad(mask,1).astype(np.uint8),.5,fully_connected='high')
    return [(c[:,::-1]-1)@matrix.T for c in contours]


def geometry(mask, matrix):
    yy,xx=np.nonzero(mask)
    if not len(xx):
        raise ValueError('Cannot measure an empty mask.')
    coords=np.column_stack([xx,yy]).astype(float)@matrix.T
    center=coords.mean(axis=0)
    area=float(len(xx)*abs(np.linalg.det(matrix)))
    # Add within-pixel covariance: a finite pixel has area, even when n=1.
    covariance=(coords-center).T@(coords-center)/len(coords)+(matrix@matrix.T)/12
    eigenvalues,eigenvectors=np.linalg.eigh(covariance)
    major=eigenvectors[:,-1]
    contours=boundary(mask,matrix)
    perimeter=sum(float(np.linalg.norm(np.diff(c,axis=0),axis=1).sum()) for c in contours)
    # Feret and convex area use pixel-cell corners, not only pixel centers.
    pixels=np.column_stack([xx,yy]).astype(np.float32)
    center_hull=cv2.convexHull(pixels).reshape(-1,2)
    corners=np.concatenate([center_hull+offset for offset in [(-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5)]])@matrix.T
    hull=ConvexHull(corners);vertices=corners[hull.vertices]
    max_feret=float(distance.pdist(vertices).max())
    edges=np.roll(vertices,-1,axis=0)-vertices
    normals=np.column_stack([-edges[:,1],edges[:,0]])/np.linalg.norm(edges,axis=1)[:,None]
    widths=np.ptp(vertices@normals.T,axis=0)
    major_length,minor_length=4*np.sqrt(np.maximum(eigenvalues[::-1],0))
    return {'area':area,'diameter':math.sqrt(4*area/math.pi),'feret_max':max_feret,'feret_min':float(widths.min()),
            'perimeter':perimeter,'centroid_x':float(center[0]),'centroid_y':float(center[1]),
            'orientation':float(math.degrees(math.atan2(major[1],major[0]))%180) if eigenvalues[-1]-eigenvalues[0]>1e-10*max(1,eigenvalues[-1]) else None,
            'length':float(major_length),'width':float(minor_length),
            'aspect_ratio':float(major_length/minor_length) if minor_length>0 else None,
            'circularity':float(4*math.pi*area/perimeter**2) if perimeter else None,
            'solidity':float(area/hull.volume),'border_status':int(mask[0].any() or mask[-1].any() or mask[:,0].any() or mask[:,-1].any())}


def polygon_metrics(mask, matrix, sides, result):
    n=int(sides)
    if not 3<=n<=20 or label(mask)[1]!=1 or not np.array_equal(binary_fill_holes(mask),mask):
        return 'Polygon metrics require one solid region and 3–20 expected sides.'
    result['side_length']=math.sqrt(4*result['area']*math.tan(math.pi/n)/n)
    contour=max(cv2.findContours(mask.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)[0],key=cv2.contourArea)
    poly=cv2.approxPolyDP(contour,.02*cv2.arcLength(contour,True),True).reshape(-1,2)@matrix.T
    if len(poly)!=n:
        return f'Corner/edge quality unavailable: outline does not fit {n} corners at 2% perimeter tolerance.'
    a=np.roll(poly,1,axis=0)-poly;b=np.roll(poly,-1,axis=0)-poly
    angles=np.degrees(np.arccos(np.clip(np.sum(a*b,axis=1)/(np.linalg.norm(a,axis=1)*np.linalg.norm(b,axis=1)),-1,1)))
    result['corner_error']=float(np.sqrt(np.mean((angles-(180-360/n))**2)))
    pts=contour.reshape(-1,2)@matrix.T
    nearest=np.full(len(pts),np.inf)
    for start,end in zip(poly,np.roll(poly,-1,axis=0)):
        v=end-start;t=np.clip((pts-start)@v/(v@v),0,1)
        nearest=np.minimum(nearest,np.linalg.norm(pts-start-t[:,None]*v,axis=1))
    result['edge_deviation']=float(np.sqrt(np.mean(nearest**2))/result['diameter'])
    return ''


def nested_metrics(document, obj, matrix, result):
    config=obj.provenance.get('morphology',{})
    kind=config.get('type','general')
    if kind=='polygon':
        return polygon_metrics(obj.mask,matrix,config.get('sides',4),result)
    if kind not in ('core-shell','hollow'):
        return ''
    inner=next((o for o in document.foreground_objects() if o.id==config.get('inner_id')),None)
    envelope=binary_fill_holes(obj.mask)
    if inner is None or inner.id==obj.id or inner.mask is None or not inner.mask.any():
        return 'Select a distinct inner area object for this morphology.'
    if label(envelope)[1]!=1 or label(inner.mask)[1]!=1 or (inner.mask & ~envelope).any():
        return 'Nested metrics require one connected inner region fully inside one outer envelope.'
    outer_boundary=np.concatenate(boundary(envelope,matrix,True))
    inner_boundary=np.concatenate(boundary(inner.mask,matrix,True))
    thickness=cKDTree(outer_boundary).query(inner_boundary)[0]
    if not len(thickness) or np.min(thickness)<=1e-8:
        return 'The inner boundary touches the outer boundary; thickness is unavailable.'
    outer=geometry(envelope,matrix);inside=geometry(inner.mask,matrix)
    result['outer_size']=outer['diameter']
    mean=float(thickness.mean());cv=float(thickness.std()/mean)
    if kind=='core-shell':
        dx=inside['centroid_x']-outer['centroid_x'];dy=inside['centroid_y']-outer['centroid_y']
        displacement=math.hypot(dx,dy)
        result.update(core_size=inside['diameter'],shell_thickness=mean,center_displacement=displacement,
                      normalized_displacement=displacement/outer['diameter'],
                      displacement_direction=math.degrees(math.atan2(dy,dx))%360 if displacement>1e-12 else None,
                      shell_uniformity=cv)
    else:
        result.update(cavity_size=inside['diameter'],wall_thickness=mean,cavity_x=inside['centroid_x'],
                      cavity_y=inside['centroid_y'],wall_uniformity=cv)
    return ''


def object_values(document,obj,matrix,origin=None):
    result={k:None for k in METRICS}
    result.update(geometry(obj.mask,matrix))
    score=obj.provenance.get('confidence_score')
    result['confidence']=float(score) if isinstance(score,(float,int)) and math.isfinite(score) else None
    result['object_id']=obj.id
    inner_ids=set()
    for outer in document.foreground_objects():
        config=outer.provenance.get('morphology',{})
        if config.get('type') not in ('core-shell','hollow') or outer.mask is None:continue
        inner=next((o for o in document.foreground_objects() if o.id==config.get('inner_id') and o.id!=outer.id),None)
        if inner is None or inner.mask is None or not inner.mask.any():continue
        envelope=binary_fill_holes(outer.mask)
        if label(envelope)[1]==1 and label(inner.mask)[1]==1 and not (inner.mask & ~binary_erosion(envelope)).any():inner_ids.add(inner.id)
    result['particle_count']=0 if obj.id in inner_ids else 1
    note=nested_metrics(document,obj,matrix,result)
    if origin is not None:
        for x,y in [('centroid_x','centroid_y'),('cavity_x','cavity_y')]:
            if result[x] is not None:
                result[x]+=float(origin[0]);result[y]+=float(origin[1])
    return result,note


def measurement_records(document,object_ids=None,group_names=None,unit=None):
    rows=[];excluded=0
    links=[]
    for item in document.foreground_objects():
        config=item.provenance.get('morphology',{})
        if config.get('type') in ('core-shell','hollow'):
            partner=next((o for o in document.objects if o.id==config.get('inner_id')),None)
            links.append((item.id,str(config),zlib.crc32(memoryview(np.ascontiguousarray(item.mask))) if item.mask is not None else None,
                          zlib.crc32(memoryview(np.ascontiguousarray(partner.mask))) if partner and partner.mask is not None else None))
    for obj in document.foreground_objects():
        group=document.get_group(obj.group_id).name
        if object_ids is not None and obj.id not in object_ids or group_names and group not in group_names:
            continue
        if obj.mask is None or not obj.mask.any():
            excluded+=1;continue
        # Include nested partners in cache key so edits to a core refresh outer metrics.
        config=obj.provenance.get('morphology',{})
        partner=next((o for o in document.objects if o.id==config.get('inner_id')),None)
        key=(zlib.crc32(memoryview(np.ascontiguousarray(obj.mask))),str(config),str(document.calibration),unit,
             zlib.crc32(memoryview(np.ascontiguousarray(partner.mask))) if partner and partner.mask is not None else None,
             obj.provenance.get('confidence_score'),tuple(links))
        cache=getattr(obj,'_statistics_cache',None)
        if cache is None or cache[0]!=key:
            pixel,note=object_values(document,obj,np.eye(2))
            physical,pnote=object_values(document,obj,document.calibration.matrix(unit),
              np.asarray(document.calibration.origin or [0.,0.])*(1 if not unit else LENGTH_UNITS[document.calibration.length_unit]/LENGTH_UNITS[unit])) if document.calibration.valid else ({k:None for k in METRICS},'')
            cache=(key,pixel,physical,note or pnote);obj._statistics_cache=cache
        _,pixel,physical,note=cache
        row={'object_id':obj.id,'name':obj.name,'group':group,'image':document.frame.source_path,'dataset':document.frame.dataset,
             'frame':document.frame.frame_index,'morphology':config.get('type','general'),'inner_object_id':config.get('inner_id',''),
             'calibrated':document.calibration.valid,'length_unit':unit or document.calibration.length_unit if document.calibration.valid else '',
             'applicability_note':note or ('Morphology-specific metrics require an explicit polygon or inner-region relationship.' if config.get('type','general') in ('general','rod') else ''),'confidence_note':'Backend mask score; not a calibrated probability.' if pixel['confidence'] is not None else 'No model confidence recorded (manual or legacy annotation).'}
        for k,(_,dim) in METRICS.items():
            if k=='object_id':continue
            row[k+'_px']=pixel[k]
            row[k+'_physical']=physical[k] if dim in (1,2,-1,0) else None
        rows.append(row)
    return rows,excluded


def summary_records(rows,metrics=None):
    output=[]
    for key in (metrics or METRICS):
        if key=='object_id':continue
        for suffix in ('px','physical'):
            cohorts={r['length_unit'] if suffix=='physical' else 'pixels' for r in rows if suffix=='px' or r['calibrated']}
            for unit in sorted(cohorts):
                for group in sorted({r['group'] for r in rows}):
                    values=[r.get(key+'_'+suffix) for r in rows if r['group']==group and (suffix=='px' or r['calibrated'] and r['length_unit']==unit)]
                    values=np.array([v for v in values if v is not None and np.isfinite(v)],float)
                    if not len(values):continue
                    dimension=METRICS[key][1]
                    display_unit=(unit+('²' if dimension==2 else '')) if dimension in (1,2) else ('degrees' if dimension==-1 else '1')
                    output.append({'group':group,'metric':key,'coordinate_system':suffix,'unit':display_unit,'n':len(values),
                                   'particle_count':float(values.sum()) if key=='particle_count' else '',
                                   'mean':float(values.mean()),'median':float(np.median(values)),'standard_deviation':float(values.std()),
                                   'min':float(values.min()),'max':float(values.max())})
    return output


def export_statistics(rows,path,metrics=None,bins=20):
    from .exports import write_measurement_csv
    from pathlib import Path
    keys=list(metrics or METRICS)
    if any(k not in METRICS for k in keys):raise ValueError('Unknown statistic selected.')
    metadata=['object_id','name','group','image','dataset','frame','morphology','inner_object_id','calibrated','length_unit','applicability_note','confidence_note']
    columns=metadata+[k+'_'+s for k in keys if k!='object_id' for s in ('px','physical')]
    write_measurement_csv([{k:r.get(k) for k in columns} for r in rows],path)
    summary=summary_records(rows,keys)
    summary_path=Path(path).with_name(Path(path).stem+'_summary.csv')
    if summary:write_measurement_csv(summary,summary_path)
    histograms=[]
    for key in keys:
        if key in ('object_id','particle_count'):continue
        for suffix in ('px','physical'):
            for group in sorted({r['group'] for r in rows}):
                for unit in sorted({r['length_unit'] if suffix=='physical' else 'pixels' for r in rows}):
                    values=[r.get(key+'_'+suffix) for r in rows if r['group']==group and (suffix=='px' or r['calibrated'] and r['length_unit']==unit)]
                    values=[v for v in values if v is not None and np.isfinite(v)]
                    if not values:continue
                    counts,edges=np.histogram(values,bins=int(bins))
                    for i,count in enumerate(counts):histograms.append({'group':group,'metric':key,'coordinate_system':suffix,'length_unit':unit,'bin_left':float(edges[i]),'bin_right':float(edges[i+1]),'count':int(count)})
    if histograms:write_measurement_csv(histograms,Path(path).with_name(Path(path).stem+'_histograms.csv'))
    import json
    from .domain import atomic_write
    atomic_write(Path(path).with_name(Path(path).stem+'_definitions.json'),json.dumps({
        'metrics':{k:METRIC_DEFINITIONS[k] for k in keys},'physical_units':'Length units are in length_unit; area uses their square. Dimensionless metrics use 1 and angles use degrees.',
        'summaries':'Population standard deviation (ddof=0). Angular means, medians and SD are arithmetic and must be interpreted with the 0/180 or 0/360 wrap in mind.',
        'missing_values':'Empty CSV cells mean not applicable or unavailable; see applicability_note and confidence_note.',
        'histogram_bins':int(bins)},indent=2).encode())
    return Path(path),summary_path if summary else None

METRIC_DEFINITIONS = {
 'area':'Number of accepted mask pixels times pixel area. Projected area and area use this single metric.',
 'diameter':'ECD = sqrt(4 × area / pi). Diameter and size-distribution requests use this definition.',
 'feret_max':'Largest distance between vertices of the convex hull of occupied pixel cells.',
 'feret_min':'Smallest width of that convex hull over its edge-normal directions.',
 'perimeter':'Length of all 0.5-level marching-square boundaries, including holes. Resolution affects small objects.',
 'centroid_x':'Mean X coordinate of occupied pixel centers; physical coordinates include the rotated basis and origin.',
 'centroid_y':'Mean Y coordinate of occupied pixel centers; image Y increases downward before rotation.',
 'orientation':'Major eigenvector angle from +X, modulo 180 degrees. Isotropic shapes have no unique orientation.',
 'length':'Major axis of the equivalent second-moment ellipse: 4 × sqrt(largest covariance eigenvalue).',
 'width':'Minor axis of the equivalent second-moment ellipse: 4 × sqrt(smallest covariance eigenvalue).',
 'aspect_ratio':'Major-axis length divided by minor-axis width.',
 'circularity':'4 × pi × area / perimeter². Pixel resolution can produce values above 1 for very small masks.',
 'solidity':'Accepted pixel-cell area divided by its convex-hull area.',
 'side_length':'Side of an equal-area regular n-gon: sqrt(4 × area × tan(pi/n) / n). Set expected sides in Morphology.',
 'corner_error':'RMS deviation from regular-polygon interior angles, in degrees. Requires a matching polygon fit at 2% perimeter tolerance; lower is better.',
 'edge_deviation':'RMS distance from boundary pixel centers to fitted polygon edges, divided by ECD; lower is better.',
 'confidence':'Recorded backend mask score. SAM1/2 use predicted mask quality; this is not a calibrated probability. Manual and legacy objects are blank.',
 'border_status':'1 if any accepted pixel touches an image edge, otherwise 0.',
 'particle_count':'1 for a particle annotation, 0 for a valid explicitly linked core/cavity. Point annotations are excluded.',
 'object_id':'Stable annotation UUID. The plot labels objects by name and short ID; CSV retains the full UUID.',
 'outer_size':'ECD of the hole-filled outer envelope; requires a valid linked core or cavity.',
 'core_size':'ECD of the explicitly linked core mask.',
 'shell_thickness':'Mean nearest outer-boundary distance from 0.5-level core-boundary samples; a 2-D estimate, not a radial or 3-D thickness.',
 'center_displacement':'Distance from outer-envelope centroid to core centroid.',
 'normalized_displacement':'Core-center displacement divided by outer-envelope ECD.',
 'displacement_direction':'Direction from outer centroid to core centroid from +X, modulo 360 degrees; undefined for coincident centers.',
 'shell_uniformity':'Coefficient of variation of sampled shell thickness (population standard deviation / mean); lower is more uniform.',
 'cavity_size':'ECD of the explicitly linked cavity mask.',
 'wall_thickness':'Mean nearest outer-boundary distance from cavity-boundary samples.',
 'cavity_x':'X centroid of the explicitly linked cavity mask.',
 'cavity_y':'Y centroid of the explicitly linked cavity mask.',
 'wall_uniformity':'Coefficient of variation of sampled wall thickness; lower is more uniform.',
}

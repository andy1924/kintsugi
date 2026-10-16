import hashlib
import io
import os
import warnings
from functools import lru_cache
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from . import config

Image.MAX_IMAGE_PIXELS = 24_000_000

def phash(image):
    a = np.asarray(image.convert('L').resize((32,32)), dtype=np.float32)
    d = cv2.dct(a)[:8,:8].flatten()[1:]
    bits = d > np.median(d)
    return f'{sum(int(b)<<i for i,b in enumerate(bits)):016x}'

def similar(a,b): return (int(a,16)^int(b,16)).bit_count() <= 5

def normalize(data):
    if len(data) > config.MAX_BYTES: raise ValueError('Photo must be smaller than 12 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.format not in ('JPEG','PNG','WEBP'): raise ValueError('Use a JPG, PNG or WebP photo.')
                source.load()
                image = ImageOps.exif_transpose(source).convert('RGB')
                if min(image.size) < 100: raise ValueError('Photo must be at least 100 pixels on each side.')
                image.thumbnail((1600,1600))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError('This photo cannot be read. Use a clear JPG, PNG or WebP.')
    output = io.BytesIO()
    image.save(output, format='JPEG', quality=92)  # discard EXIF and location metadata
    encoded = output.getvalue()
    return encoded, image.width, image.height, hashlib.sha256(encoded).hexdigest(), phash(image)

@lru_cache(maxsize=1)
def sam_predictor():
    import torch
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    checkpoint = os.environ.get('SAM2_CHECKPOINT', '')
    if not Path(checkpoint).is_file(): raise RuntimeError('SAM2 checkpoint is missing. Configure SAM2_CHECKPOINT.')
    return SAM2ImagePredictor(build_sam2(os.getenv('SAM2_CONFIG','configs/sam2.1/sam2.1_hiera_t.yaml'), checkpoint, device=os.getenv('MODEL_DEVICE','cpu')))

def validate_model():
    if config.MODEL == 'sam2': sam_predictor()
    elif config.MODEL != 'grabcut': raise RuntimeError('SEGMENTATION_MODEL must be grabcut or sam2.')

def detect_damage(image):
    """Propose a contrasting local defect, with an explicit uncertain fallback.

    This is a visual anomaly heuristic, not a trained textile classifier.
    Work at bounded resolution so large photos do not dominate processing.
    """
    h,w=image.shape[:2]
    factor=min(1,640/max(h,w))
    small=cv2.resize(image,(round(w*factor),round(h*factor)))
    lab=cv2.cvtColor(small,cv2.COLOR_RGB2LAB).astype(np.float32)
    background=cv2.GaussianBlur(lab,(0,0),7)
    contrast=np.linalg.norm(lab-background,axis=2)
    threshold=max(14,float(np.percentile(contrast,94)))
    mask=(contrast>threshold).astype(np.uint8)*255
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((7,7),np.uint8))
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    sh,sw=mask.shape
    candidates=[]
    for contour in contours:
        x,y,cw,ch=cv2.boundingRect(contour)
        area=cv2.contourArea(contour)
        if area<max(20,sw*sh*.0004) or cw*ch>sw*sh*.35:continue
        if x<sw*.03 or y<sh*.03 or x+cw>sw*.97 or y+ch>sh*.97:continue
        centre=((x+cw/2)/sw-.5)**2+((y+ch/2)/sh-.5)**2
        candidates.append((area/(1+4*centre),x,y,cw,ch))
    if not candidates:
        return [.15,.15,.85,.85], 'uncertain'
    _,x,y,cw,ch=max(candidates)
    pad=max(5,round(max(cw,ch)*.12))
    return [max(.005,(x-pad)/sw),max(.005,(y-pad)/sh),min(.995,(x+cw+pad)/sw),min(.995,(y+ch+pad)/sh)], 'suggested'

def segment(data, settings):
    image = np.array(Image.open(io.BytesIO(data)).convert('RGB'))
    height,width = image.shape[:2]
    automatic = settings.get('box') is None
    box, detection = detect_damage(image) if automatic else (settings['box'], 'user_adjusted')
    width_mm = settings.get('width_mm') or 35
    scale_source = 'user' if settings.get('width_mm') is not None else 'suggested'
    # Keep the uncalibrated suggested template within supported dimensions.
    if scale_source == 'suggested':
        width_mm = round(min(35,390*(box[2]-box[0])*width/((box[3]-box[1])*height)),1)
        width_mm = max(3,width_mm)
    x0,y0,x1,y1 = [int(v*n) for v,n in zip(box,[width,height,width,height])]
    x0,y0 = max(1,x0),max(1,y0)
    x1,y1 = min(width-1,x1),min(height-1,y1)
    mask = np.zeros((height,width),dtype=np.uint8)
    notes = ['Review the highlighted area and adjust it if any damaged edges are missing.']
    if automatic:
        notes.append('A visual contrast detector suggested this area; seams, prints and shadows can also be selected.')
    if detection == 'uncertain':
        notes.append('No distinct damage was found. A broad review area is shown; adjust it to your damage or try a closer photo.')
    if scale_source == 'suggested':
        notes.append('No physical scale reference was supplied. The size below is a suggested template size, not a measured damage width. Adjust it if needed and check coverage on the garment before cutting.')
    else:
        notes.append('Scale uses your entered width; photo perspective is not automatically corrected.')
    if config.MODEL == 'sam2':
        import torch
        predictor = sam_predictor()
        with torch.inference_mode():
            predictor.set_image(image)
            masks,scores,_ = predictor.predict(box=np.array([x0,y0,x1,y1]), point_coords=np.array([[(x0+x1)/2,(y0+y1)/2]]), point_labels=np.array([1]), multimask_output=True)
        mask = masks[int(np.argmax(scores))].astype(np.uint8)
        # User ROI is a hard constraint; outside foreground is never accepted.
        roi = np.zeros_like(mask); roi[y0:y1,x0:x1]=1; mask &= roi
        engine = 'SAM 2.1'
    else:
        labels = np.zeros_like(mask)
        try:
            cv2.grabCut(image,labels,(x0,y0,x1-x0,y1-y0),np.zeros((1,65),np.float64),np.zeros((1,65),np.float64),5,cv2.GC_INIT_WITH_RECT)
            mask = np.isin(labels,[cv2.GC_FGD,cv2.GC_PR_FGD]).astype(np.uint8)
        except cv2.error:
            notes.append('Automatic segmentation was inconclusive. Your marked area is used conservatively.')
        engine = 'OpenCV GrabCut (image-fitted GMM)'
    roi_area = (x1-x0)*(y1-y0)
    if mask.sum() < roi_area*.02:
        mask[y0:y1,x0:x1] = 1
        notes.append('Your complete marked rectangle is used because no reliable smaller boundary was found.')
    # Never shrink safety coverage to an uncertain algorithmic prediction.
    coverage = np.zeros_like(mask);coverage[y0:y1,x0:x1]=1
    px_mm = (x1-x0)/width_mm
    fabric = settings.get('fabric') or 'Other'
    margin = 12 if fabric in ('Knit','Other') else 10
    radius = min(300,max(1,round(margin*px_mm)))
    padded = cv2.dilate(coverage,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(2*radius+1,2*radius+1)))
    contours,_ = cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    outlines = []
    for c in sorted(contours,key=cv2.contourArea,reverse=True)[:20]:
        if cv2.contourArea(c)>5:
            outlines.append((cv2.approxPolyDP(c,1.5,True).reshape(-1,2)/[width,height]).round(5).tolist())
    if x0-radius<0 or y0-radius<0 or x1+radius>width or y1+radius>height:
        notes.append('The anchoring margin extends beyond this photo. Include more healthy fabric in a wider photo before sewing.')
    return {'provider':'local','fabric':fabric,'engine':engine,'outlines':outlines,'box':box,'width_mm':width_mm,'scale_source':scale_source,'detection':detection,'damage_width_px':x1-x0,'damage_height_px':y1-y0,'assessment':'Elongated damage candidate' if (x1-x0)/(y1-y0)>3 or (y1-y0)/(x1-x0)>3 else 'Localised damage candidate','height_mm':round((y1-y0)/px_mm,1),'margin_mm':margin,'coverage_mm2':round(padded.sum()/px_mm**2,1),'warnings':notes,'requires_confirmation':True}

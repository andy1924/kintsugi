"""Free, deterministic repair proposals when a photo-edit provider is unavailable.

These are clearly labelled stitch illustrations, never claimed as AI photographs.
The same paths and instructions feed the printable guide.
"""
import io
import math
from PIL import Image, ImageDraw, ImageStat
from .compiler import lines_for
from .creative import repair_rectangle
from .storage import store


def suggest_repair(analysis, seed):
    style=analysis.get('recommended_style') or 'sashiko'
    margin=analysis['margin_mm']
    width=analysis['width_mm']+2*margin
    height=analysis['height_mm']+2*margin
    lines=lines_for(style,width,height,margin,seed)
    paths=[[[x/width,y/height] for x,y in path] for path in lines]
    if style=='branch' and analysis['damage_width_px']>analysis['damage_height_px']:
        paths=[[[y,x] for x,y in path] for path in paths]
    paths.insert(0,[[.05,.05],[.95,.05],[.95,.95],[.05,.95],[.05,.05]])
    names={'branch':'A golden branch, a new beginning','sashiko':'A woven patch, made to keep','waves':'A little tide of golden stitches','constellation':'A constellation of small repairs'}
    steps=[
        {'title':'Check the damage and measure','body':'Lay the garment flat. Check that the highlighted area covers every damaged fibre. Measure the width on the real garment; use that width to adjust the printable template before cutting.','tip':'A photo alone does not establish a physical size.'},
        {'title':'Choose and cut the backing','body':f'Choose prewashed backing with similar weight, stretch and care needs. Check the template against the garment and include at least {margin} mm of healthy anchoring fabric around the damage.','tip':'Support all the damage before adding decoration.'},
        {'title':'Baste the layers','body':'Place the backing behind the tear, align the fabric without stretching it, then use loose temporary stitches to hold the layers together.','tip':'Avoid trapping folds or pulling the tear wider.'},
        {'title':'Practise a running stitch','body':'On a scrap, bring the needle up and down through both layers with small, evenly spaced stitches. Keep the thread relaxed enough for the fabric to move.','tip':'Match the needle and backing to the fabric; use a ballpoint needle for knits.'},
        {'title':'Secure the patch and follow the motif','body':'Secure the backing perimeter in healthy fabric, then transfer the supplied stitch lines with a washable marker. Sew the suggested design through both layers, keeping the tension relaxed.','tip':'The motif is decorative; the backing and perimeter support the tear.'},
        {'title':'Finish and check the movement','body':'Secure the thread ends on the inside, remove the basting, and inspect every edge. Gently flex the garment and check for pulling before wearing.','tip':'If healthy fabric is too weak to anchor the patch, ask a maker to assess it.'},
    ]
    backing={'Denim':'Prewashed denim backing of similar weight; match stretch for stretch denim','Cotton':'Prewashed cotton backing of similar weight','Linen':'Prewashed linen or light woven cotton backing','Knit':'Soft knit backing with comparable stretch; use a ballpoint needle','Other':'Prewashed backing matched to your fabric weight, stretch and care needs'}.get(analysis.get('fabric'),'Prewashed backing matched to your fabric weight, stretch and care needs')
    return {'name':names[style],'story':'A compatible backing supports the tear while warm-gold running stitches turn the worn area into an intentional detail. Keep the original garment, with a new chapter in thread.',
            'style':style,'thread_colour':'Warm gold embroidery floss',
            'materials':[backing,'Embroidery needle and warm gold floss','Scissors, ruler and washable marking pencil'],
            'steps':steps,'paths':paths}


def illustrated_preview(project, analysis):
    design=suggest_repair(analysis,project.image_hash)
    original=Image.open(io.BytesIO(store.get(project.image_key))).convert('RGB')
    x0,y0,x1,y1=repair_rectangle(original,analysis)
    bx0,by0,bx1,by1=[round(value*size) for value,size in zip(analysis['box'],[original.width,original.height]*2)]
    # A visible patch sketch covers the tear. The surrounding photo is retained.
    sample=original.crop((x0,y0,x1,y1))
    colour=tuple(round(value*.92) for value in ImageStat.Stat(sample).median)
    overlay=Image.new('RGBA',original.size,(0,0,0,0));draw=ImageDraw.Draw(overlay)
    pad=max(3,round((bx1-bx0)*.08))
    patch=(max(x0,bx0-pad),max(y0,by0-pad),min(x1,bx1+pad),min(y1,by1+pad))
    draw.rounded_rectangle(patch,radius=max(3,pad),fill=(*colour,242))
    for y in range(patch[1]+2,patch[3],4):
        draw.line((patch[0]+2,y,patch[2]-2,y),fill=(230,225,204,24),width=1)
    for path in design['paths']:
        points=[(x0+x*(x1-x0),y0+y*(y1-y0)) for x,y in path]
        distance=0
        for a,b in zip(points,points[1:]):
            length=math.dist(a,b)
            if length<.01:continue
            for step in range(math.ceil(length)):
                if int(distance+step)%9>=6:continue
                t=step/length;end=min(1,(step+1.5)/length)
                p=(a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t)
                q=(a[0]+(b[0]-a[0])*end,a[1]+(b[1]-a[1])*end)
                draw.line((p[0]+1,p[1]+1,q[0]+1,q[1]+1),fill=(38,30,18,160),width=3)
                draw.line((*p,*q),fill=(225,178,88,255),width=2)
            distance+=length
    repaired=Image.alpha_composite(original.convert('RGBA'),overlay).convert('RGB')
    stream=io.BytesIO();repaired.save(stream,format='PNG')
    return {'state':'ready','source_revision':project.revision,'style':design['style'],'design':design,
            'provider':'local','model':'stitch illustration','image_key':store.put(stream.getvalue(),'png'),
            'disclaimer':'Illustrated repair proposal, not a photograph of a finished repair. Check the damage area and measure the real garment before cutting.'}

"""Geometry-first compiler. Patterns are procedural vector art, not diffusion output."""
import io
import math
import random
import textwrap
import cv2
import numpy as np
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4
from .storage import store

STYLES = {'sashiko':'Quick rescue','branch':'Golden branch','constellation':'Constellation','waves':'Seigaiha waves'}

def lines_for(style, width, height, margin, seed):
    rng = random.Random(seed)
    lines=[]
    if style=='sashiko':
        for y in range(4,math.ceil(height),6): lines.append([[3,y],[width-3,y]])
        for x in range(4,math.ceil(width),8): lines.append([[x,3],[x,height-3]])
    elif style=='branch':
        trunk=[[width*.5+ rng.uniform(-.06,.06)*width, height*(.1+i*.13)] for i in range(7)]
        lines.append(trunk)
        for i in range(1,6):
            x,y=trunk[i]; side=1 if i%2 else -1
            lines.append([[x,y],[x+side*width*.16,y-height*.09],[x+side*width*.3,y-height*.21]])
    elif style=='constellation':
        points=[[width*rng.uniform(.15,.85),height*rng.uniform(.12,.88)] for _ in range(7)]
        points.sort(key=lambda p:p[1]);lines.append(points)
        for x,y in points:
            lines.extend([[[x-1.5,y],[x+1.5,y]],[[x,y-1.5],[x,y+1.5]]])
    elif style=='waves':
        for y in range(7,math.ceil(height),9):
            for x in range(0,math.ceil(width),16):
                lines.append([[max(2,min(width-2,x+8+7*math.cos(t*math.pi/20))),max(2,min(height-2,y-7*math.sin(t*math.pi/20)))] for t in range(21)])
    return [[[round(x,2),round(y,2)] for x,y in line] for line in lines]

def damage_paths(analysis):
    """Trace a coarse medial-axis graph of the confirmed segmentation in millimetres."""
    m=analysis['margin_mm'];w=analysis['width_mm']+2*m;h=analysis['height_mm']+2*m
    scale=min(4,480/max(w,h));gw,gh=math.ceil(w*scale)+1,math.ceil(h*scale)+1
    mask=np.zeros((gh,gw),dtype=np.uint8)
    x0,y0,x1,y1=analysis['box']
    for outline in analysis.get('outlines',[]):
        pts=np.array([[(x-x0)/(x1-x0)*analysis['width_mm']+m,(y-y0)/(y1-y0)*analysis['height_mm']+m] for x,y in outline])
        pts=np.round(pts*scale).astype(np.int32)
        if len(pts)>2:cv2.fillPoly(mask,[pts],255)
    if not mask.any():return []
    element=cv2.getStructuringElement(cv2.MORPH_CROSS,(3,3));skeleton=np.zeros_like(mask)
    for _ in range(500):
        eroded=cv2.erode(mask,element)
        skeleton=cv2.bitwise_or(skeleton,cv2.subtract(mask,cv2.dilate(eroded,element)))
        mask=eroded
        if not mask.any():break
    pixels=set(zip(*np.where(skeleton>0)))
    def adjacent(point):
        y,x=point
        return [(y+dy,x+dx) for dy in (-1,0,1) for dx in (-1,0,1) if (dy or dx) and (y+dy,x+dx) in pixels]
    graph={p:adjacent(p) for p in pixels};visited=set();paths=[]
    starts=sorted(pixels,key=lambda p:(len(graph[p])==2,p))
    for start in starts:
        for neighbor in graph[start]:
            edge=frozenset((start,neighbor))
            if edge in visited:continue
            path=[start,neighbor];visited.add(edge);previous,current=start,neighbor
            while len(graph[current])==2:
                nxt=next((p for p in graph[current] if p!=previous),None)
                if nxt is None or frozenset((current,nxt)) in visited:break
                visited.add(frozenset((current,nxt)));path.append(nxt);previous,current=current,nxt
            array=np.array([[x/scale,y/scale] for y,x in path],dtype=np.float32).reshape(-1,1,2)
            if cv2.arcLength(array,False)>3:
                simple=cv2.approxPolyDP(array,.6,False).reshape(-1,2)
                paths.append((cv2.arcLength(array,False),[[round(float(x),2),round(float(y),2)] for x,y in simple]))
    return [p for _,p in sorted(paths,key=lambda p:p[0],reverse=True)[:18]]

def make_plan(project):
    a=project.analysis;s=project.settings;m=a['margin_mm']
    w=round(a['width_mm']+2*m,1);h=round(a['height_mm']+2*m,1)
    style=s['style']
    material={'Denim':'Similar-weight denim backing; use a stretch backing for stretch denim.','Cotton':'Prewashed cotton backing of similar weight.','Linen':'Prewashed linen or light woven cotton backing.','Knit':'Soft knit backing with comparable stretch; use a ballpoint needle.','Other':'Match the weight, stretch and care requirements of the original textile.'}[s.get('fabric') or a.get('fabric') or 'Other']
    instructions=[f'Print pattern pages at 100% / actual size. Check the 20 mm bar with a ruler.',f'Cut backing {w:g} x {h:g} mm. The inner dashed rectangle represents the marked damage.',f'Place backing behind the damage. Baste gently into healthy fabric, at least {m} mm from damaged edges.','Secure the patch perimeter with relaxed running stitches about 3 mm apart. Avoid pulling the fabric tight.',f'Follow the {STYLES[style].lower()} motif with running stitches, keeping the backing secured across the damaged area.','Remove basting, inspect all edges and test movement before wearing. Follow your fabric care instructions.']
    motif_lines=lines_for(style,w,h,m,project.image_hash)
    traced=damage_paths(a) if style=='branch' else []
    if traced:motif_lines=traced
    plan={'generation':'Segmentation-derived medial-axis paths' if traced else 'Deterministic vector pattern fitted to your repair area','style':style,'name':STYLES[style],'width_mm':w,'height_mm':h,'margin_mm':m,'lines':motif_lines,'materials':[material,'Embroidery needle and scissors','Embroidery floss: DMC 3820 (straw) or a colour you already own','Ruler; optional washable marking pencil'],'instructions':instructions,'estimated_minutes':{'sashiko':30,'branch':60,'constellation':45,'waves':75}[style],'disclaimer':'Measured from your confirmed area, not automatic metrology. Check coverage and print scale before sewing. Suitable for textile mending, not load-bearing or protective equipment.'}
    plan['scale_source']=a.get('scale_source','user')
    if plan['scale_source']=='suggested':
        plan['disclaimer']='Suggested template size; physical damage size could not be measured from this photo. Check the template covers all damage plus the anchoring margin on the garment before cutting.'
        plan['instructions'].insert(0,plan['disclaimer'])
    pdf=pdf_bytes(plan,project.title)
    svg=svg_bytes(plan)
    plan['pdf_key']=store.put(pdf,'pdf');plan['svg_key']=store.put(svg,'svg')
    return plan

def svg_bytes(plan):
    w,h=plan['width_mm'],plan['height_mm'];m=plan['margin_mm']
    paths=''.join(f'<polyline points="{" ".join(f"{x},{y}" for x,y in line)}"/>' for line in plan['lines'])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" viewBox="0 0 {w} {h}"><title>Kintsugi - {plan["name"]}</title><rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="2" fill="#f1ead8" stroke="#736654" stroke-width=".3"/><rect x="{m}" y="{m}" width="{w-2*m}" height="{h-2*m}" fill="none" stroke="#a39a88" stroke-width=".25" stroke-dasharray="1 1"/><g fill="none" stroke="#aa7e2d" stroke-width=".45" stroke-linecap="round">{paths}</g></svg>').encode()

def pdf_bytes(plan,title):
    stream=io.BytesIO();c=canvas.Canvas(stream,pagesize=A4);c.setTitle('Kintsugi - Repair plan')
    pw,ph=A4
    def label(text,x,y,size=10):
        c.setFont('Helvetica',size);c.drawString(x,y,text.encode('latin-1','replace').decode('latin-1'))
    c.setFillColorRGB(.16,.15,.12);c.setFont('Times-Roman',36);c.drawString(20*mm,ph-28*mm,'Kintsugi.')
    label('YOUR REPAIR GUIDE',20*mm,ph-40*mm,9)
    label(title[:80],20*mm,ph-54*mm,14)
    label(f'{plan["name"]} / {plan["width_mm"]:g} x {plan["height_mm"]:g} mm / about {plan["estimated_minutes"]} minutes',20*mm,ph-64*mm)
    y=ph-80*mm
    for heading,rows in [('MATERIALS',plan['materials']),('METHOD',[f'{i+1}. {s}' for i,s in enumerate(plan['instructions'])]),('PLEASE CHECK',[plan['disclaimer']])]:
        label(heading,20*mm,y,9);y-=7*mm
        for row in rows:
            for line in textwrap.wrap(row,92):label(line,20*mm,y,10);y-=4.7*mm
            y-=2*mm
        y-=6*mm
    label('Print at actual size. Pattern follows on the next page(s).',20*mm,18*mm,9);c.showPage()
    # Tile at physical size, with 10 mm overlap. No fit-to-page scaling.
    tile_w,tile_h=170,210;stride_x,stride_y=160,200
    cols=max(1,math.ceil((plan['width_mm']-10)/stride_x));rows=max(1,math.ceil((plan['height_mm']-10)/stride_y))
    for row in range(rows):
        for col in range(cols):
            ox,oy=col*stride_x,row*stride_y
            label(f'KINTSUGI / PATTERN - row {row+1} of {rows}, column {col+1} of {cols}',20*mm,ph-18*mm,10)
            label('Actual size - 10 mm overlap between tiles. Match the grid coordinates.',20*mm,ph-25*mm,8)
            c.saveState();c.translate(20*mm,ph-35*mm);c.scale(mm,-mm)
            clip=c.beginPath();clip.rect(0,0,tile_w,tile_h);c.clipPath(clip,stroke=0,fill=0)
            c.translate(-ox,-oy);c.setLineWidth(.25);c.setStrokeColorRGB(.45,.4,.3)
            c.roundRect(.5,.5,plan['width_mm']-1,plan['height_mm']-1,2,stroke=1,fill=0)
            c.setDash(1,1);m=plan['margin_mm'];c.rect(m,m,plan['width_mm']-2*m,plan['height_mm']-2*m,stroke=1,fill=0);c.setDash()
            c.setStrokeColorRGB(.45,.28,.07);c.setLineWidth(.45)
            for line in plan['lines']:
                p=c.beginPath();p.moveTo(*line[0])
                for pt in line[1:]:p.lineTo(*pt)
                c.drawPath(p)
            c.restoreState()
            c.setStrokeColorRGB(.5,.5,.5);c.setLineWidth(.4);c.rect(20*mm,ph-245*mm,170*mm,210*mm,stroke=1,fill=0)
            label(f'Tile origin: x={ox} mm, y={oy} mm',20*mm,ph-252*mm,8)
            c.setStrokeColorRGB(0,0,0);c.setLineWidth(1);c.line(20*mm,23*mm,40*mm,23*mm)
            c.line(20*mm,21*mm,20*mm,25*mm);c.line(40*mm,21*mm,40*mm,25*mm)
            label('20 mm calibration bar - measure before sewing',45*mm,22*mm,8)
            c.showPage()
    c.save();return stream.getvalue()

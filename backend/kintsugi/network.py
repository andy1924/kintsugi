"""Paid craft work, consent-based matching and manually fulfilled two-way logistics."""
import time
import math
import os
from typing import Literal
from urllib.parse import urlparse
from pydantic import BaseModel,Field,field_validator,ConfigDict
from datetime import datetime,timezone,timedelta
from fastapi import APIRouter,Depends,HTTPException,Response,Query
from sqlalchemy import select,update,func,case,or_
from .db import get_db
from .auth import current_user,rate_limit
from .models import User,Project,Maker,RepairService,ServiceQuote,Shipment,MakerEarning,ServiceEvent
from .storage import store

router=APIRouter(prefix='/api/v1/network',tags=['repair network'])

def lock_account(db,user):db.execute(update(User).where(User.id==user.id).values(name=User.name))
def operator(user):
    if user.role!='operator':raise HTTPException(403,'An operator account is required.')
def profile(db,user):return db.scalar(select(Maker).where(Maker.user_id==user.id))
def event(db,service,user,message):
    service.updated_at=time.time()
    db.add(ServiceEvent(service_id=service.id,actor_id=user.id,message=message))
def quote_for(db,service):return db.scalar(select(ServiceQuote).where(ServiceQuote.service_id==service.id))

def service_for(db,user,service_id,lock=False):
    if lock:db.execute(update(RepairService).where(RepairService.id==service_id).values(updated_at=RepairService.updated_at))
    service=db.scalar(select(RepairService).where(RepairService.id==service_id).execution_options(populate_existing=True))
    maker=profile(db,user)
    if not service or (service.user_id!=user.id and user.role!='operator' and (not maker or maker.id!=service.maker_id)):
        raise HTTPException(404,'Repair service not found.')
    return service

def owner(service,user):
    if service.user_id!=user.id:raise HTTPException(403,'Only the customer can do this.')
def maker_access(db,service,user):
    maker=profile(db,user)
    if not maker or maker.id!=service.maker_id or maker.status!='approved':raise HTTPException(403,'This job is not assigned to your approved workroom.')
    return maker

def public_maker(m):return {'id':m.id,'name':m.name,'about':m.about,'city':m.city,'categories':m.categories,'community':m.community,'accepting_work':m.accepting_work,'status':m.status,'public_location':({'latitude':m.latitude,'longitude':m.longitude} if m.latitude is not None and m.longitude is not None else None)}

def serialize(db,service,user):
    project=db.get(Project,service.project_id);maker=db.get(Maker,service.maker_id) if service.maker_id else None;q=quote_for(db,service)
    quote=None
    if q:
        quote={k:getattr(q,k) for k in ['id','labour_minor','materials_minor','outbound_minor','return_minor','fee_minor','total_minor','days','notes','version','accepted_at','expires_at']}
        quote['maker_earns_minor']=q.labour_minor+q.materials_minor
        quote['saving_minor']=service.replacement_minor-q.total_minor if service.replacement_minor and q.total_minor>0 and service.status not in ('awaiting_quote','repair_priced') else None
        quote['currency']='INR'
    result={'id':service.id,'project_id':project.id,'title':project.title,'category':project.category,'status':service.status,'brief':service.brief,'design':({**{k:v for k,v in service.design_snapshot.items() if k not in ('pdf_key','svg_key','preview_key','lines')},'has_pattern':bool(service.design_snapshot.get('pdf_key')),'has_preview':bool(service.design_snapshot.get('preview_key'))} if service.design_snapshot else None),'maker':public_maker(maker) if maker else None,'quote':quote,'payment_status':service.payment_status,'replacement_minor':service.replacement_minor,'budget_minor':service.budget_minor,'created_at':service.created_at,'shipments':[{k:getattr(s,k) for k in ['id','leg','status','courier','tracking','tracking_url','pickup_at']} for s in db.scalars(select(Shipment).where(Shipment.service_id==service.id).order_by(Shipment.leg))],'events':[{'message':e.message,'created_at':e.created_at} for e in db.scalars(select(ServiceEvent).where(ServiceEvent.service_id==service.id).order_by(ServiceEvent.created_at))]}
    if service.user_id==user.id or user.role=='operator':result['return_address']=service.return_address
    if user.role=='operator':result['maker_address']=maker.address if maker else None;result['payment_reference']=service.payment_reference
    return result

class NetworkInput(BaseModel):
    model_config=ConfigDict(str_strip_whitespace=True)

class Address(NetworkInput):
    name:str=Field(min_length=2,max_length=100)
    phone:str=Field(min_length=8,max_length=20,pattern=r'^\+?[0-9 ()-]+$')
    line1:str=Field(min_length=5,max_length=200)
    city:str=Field(min_length=2,max_length=80)
    postal_code:str=Field(pattern=r'^\d{6}$')
    country:Literal['IN']='IN'

class PublicLocation(NetworkInput):
    latitude:float=Field(ge=-90,le=90,allow_inf_nan=False)
    longitude:float=Field(ge=-180,le=180,allow_inf_nan=False)
    @field_validator('latitude','longitude')
    @classmethod
    def approximate(cls,value):return round(value,2)

class MapLocationInput(NetworkInput):
    # Providing a point explicitly opts in to its public, approximate map pin.
    public_location:PublicLocation|None

class MakerApplication(NetworkInput):
    name:str=Field(min_length=2,max_length=100)
    about:str=Field(min_length=30,max_length=1000)
    city:str=Field(min_length=2,max_length=80)
    categories:list[Literal['textile','ceramic']]=Field(min_length=1,max_length=2)
    community:Literal['independent','women_led','community_enterprise']='independent'
    address:Address
    consent_to_list:Literal[True]
    public_location:PublicLocation|None=None

class ServiceInput(NetworkInput):
    project_id:str
    maker_id:str|None=None
    brief:str=Field(min_length=10,max_length=1000)
    replacement_minor:int|None=Field(default=None,ge=100,le=100_000_000)
    budget_minor:int|None=Field(default=None,ge=100,le=100_000_000)
    consent_to_share:Literal[True]

class QuoteInput(NetworkInput):
    labour_minor:int=Field(ge=100,le=10_000_000)
    materials_minor:int=Field(ge=0,le=10_000_000)
    days:int=Field(ge=1,le=90)
    notes:str=Field(min_length=10,max_length=1000)

class ShippingPrice(NetworkInput):
    version:int=Field(ge=1)
    outbound_minor:int=Field(ge=0,le=1_000_000)
    return_minor:int=Field(ge=0,le=1_000_000)

class Acceptance(NetworkInput):
    version:int=Field(ge=1)
    address:Address
    packaging_acknowledged:Literal[True]

class AssignInput(NetworkInput):maker_id:str
class ReviewInput(NetworkInput):decision:Literal['approved','rejected']
class Availability(NetworkInput):accepting_work:bool
class Reference(NetworkInput):reference:str=Field(min_length=5,max_length=120)
class MakerProgress(NetworkInput):status:Literal['repairing','ready_for_return','declined']
class ShippingUpdate(NetworkInput):
    status:Literal['scheduled','in_transit','delivered']
    courier:str=Field(min_length=2,max_length=80)
    tracking:str=Field(min_length=3,max_length=120)
    tracking_url:str|None=Field(default=None,max_length=500)
    pickup_at:str|None=Field(default=None,max_length=50)
    @field_validator('pickup_at')
    @classmethod
    def pickup_date(cls,value):
        if value:
            try:date=datetime.fromisoformat(value.replace('Z','+00:00'))
            except ValueError:raise ValueError('Use a valid ISO pickup date and time.')
            if date.tzinfo is None:date=date.replace(tzinfo=timezone(timedelta(hours=5,minutes=30)))
            return date.isoformat()
        return value
    @field_validator('tracking_url')
    @classmethod
    def safe_link(cls,value):
        if value:
            p=urlparse(value)
            if p.scheme!='https' or not p.hostname or p.username or p.password:raise ValueError('Use an HTTPS tracking URL without credentials.')
        return value

@router.get('/map-config')
def map_config():
    return {'tile_url':os.getenv('OSM_TILE_URL') or 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'}

@router.get('/makers')
def makers(category:Literal['textile','ceramic']|None=None,db=Depends(get_db),
           offset:int=Query(default=0,ge=0),latitude:float|None=Query(default=None,ge=-90,le=90),
           longitude:float|None=Query(default=None,ge=-180,le=180),radius_km:float=Query(default=50,ge=1,le=200)):
    if (latitude is None)!=(longitude is None):raise HTTPException(422,'Provide both latitude and longitude.')
    query=select(Maker).where(Maker.status=='approved',Maker.accepting_work.is_(True),Maker.consent_to_list.is_(True))
    if category:
        # JSON containment differs across databases; these are the only allowed categories.
        query=query.where(or_(Maker.categories[0].as_string()==category,Maker.categories[1].as_string()==category))
    if latitude is None:
        return [public_maker(m) for m in db.scalars(query.order_by(Maker.created_at,Maker.id).offset(offset).limit(50))]
    # Indexed latitude bounding band, followed by exact great-circle filtering, sorting and pagination in SQL.
    band=math.degrees(radius_km/6371.0088)
    query=query.where(Maker.latitude.between(max(-90,latitude-band),min(90,latitude+band)),Maker.longitude.is_not(None))
    cosine=(math.sin(math.radians(latitude))*func.sin(func.radians(Maker.latitude))+
            math.cos(math.radians(latitude))*func.cos(func.radians(Maker.latitude))*func.cos(func.radians(Maker.longitude-longitude)))
    distance=6371.0088*func.acos(case((cosine>1,1.0),(cosine < -1,-1.0),else_=cosine))
    rows=db.execute(query.add_columns(distance.label('distance_km')).where(distance<=radius_km).order_by(distance,Maker.id).offset(offset).limit(50))
    return [{**public_maker(m),'distance_km':round(km,1)} for m,km in rows]

@router.get('/profile')
def my_profile(user=Depends(current_user),db=Depends(get_db)):
    maker=profile(db,user)
    if not maker:return None
    return {**public_maker(maker),'address':maker.address}

@router.post('/profile',status_code=201)
def apply(body:MakerApplication,user=Depends(current_user),db=Depends(get_db)):
    lock_account(db,user)
    if profile(db,user):raise HTTPException(409,'Your application is already saved. Contact the operator for profile changes.')
    location=body.public_location
    maker=Maker(user_id=user.id,**body.model_dump(exclude={'address','public_location'}),address=body.address.model_dump(),latitude=location.latitude if location else None,longitude=location.longitude if location else None);db.add(maker);db.commit();return public_maker(maker)

@router.put('/profile/location')
def update_location(body:MapLocationInput,user=Depends(current_user),db=Depends(get_db)):
    maker=profile(db,user)
    if not maker:raise HTTPException(404,'Apply to the network first.')
    maker.latitude=body.public_location.latitude if body.public_location else None
    maker.longitude=body.public_location.longitude if body.public_location else None
    db.commit();return public_maker(maker)

@router.post('/profile/availability')
def availability(body:Availability,user=Depends(current_user),db=Depends(get_db)):
    maker=profile(db,user)
    if not maker:raise HTTPException(404,'Apply to the network first.')
    maker.accepting_work=body.accepting_work;db.commit();return public_maker(maker)

@router.get('/applications')
def applications(user=Depends(current_user),db=Depends(get_db)):
    operator(user);return [{**public_maker(m),'address':m.address} for m in db.scalars(select(Maker).where(Maker.status=='pending').limit(100))]

@router.post('/makers/{maker_id}/review')
def review(maker_id:str,body:ReviewInput,user=Depends(current_user),db=Depends(get_db)):
    operator(user);maker=db.get(Maker,maker_id)
    if not maker:raise HTTPException(404,'Maker not found.')
    if maker.status!='pending':raise HTTPException(409,'This application has already been reviewed.')
    maker.status=body.decision;db.commit();return public_maker(maker)

@router.post('/requests',status_code=201)
def create_service(body:ServiceInput,user=Depends(current_user),db=Depends(get_db)):
    rate_limit(db,'service:'+user.id,10,3600);lock_account(db,user)
    project=db.scalar(select(Project).where(Project.id==body.project_id,Project.user_id==user.id))
    if not project:raise HTTPException(404,'Piece not found.')
    existing=db.scalar(select(RepairService).where(RepairService.project_id==project.id,RepairService.status.notin_(['cancelled','delivered'])))
    if existing:raise HTTPException(409,'This piece already has an active service request.')
    maker=db.get(Maker,body.maker_id) if body.maker_id else None
    if body.maker_id and (not maker or maker.status!='approved' or not maker.accepting_work or project.category not in maker.categories):raise HTTPException(409,'This maker is not available for this kind of repair.')
    if maker and maker.user_id==user.id:raise HTTPException(422,'You cannot request your own workroom.')
    snapshot={**(project.plan or {'name':'Guided ceramic repair' if project.category=='ceramic' else 'Guided textile repair'}),'tutorial_completed_steps':project.tutorial_steps} if project.plan or project.tutorial_steps else None
    if project.preview and project.preview.get('state')=='ready':
        snapshot={**(snapshot or {}),'preview_key':project.preview['image_key'],'name':project.preview['design']['name'],'creative_steps':project.preview['design']['steps']}
    service=RepairService(user_id=user.id,design_snapshot=snapshot,**body.model_dump(),status='awaiting_quote' if maker else 'awaiting_match');db.add(service);db.flush();event(db,service,user,'Repair request received. No payment has been taken.');db.commit();return serialize(db,service,user)

@router.get('/requests')
def requests(scope:Literal['customer','maker','operator']='customer',user=Depends(current_user),db=Depends(get_db),offset:int=0):
    stmt=select(RepairService)
    if scope=='operator':operator(user)
    elif scope=='maker':
        maker=profile(db,user)
        if not maker:return []
        stmt=stmt.where(RepairService.maker_id==maker.id)
    else:stmt=stmt.where(RepairService.user_id==user.id)
    return [serialize(db,s,user) for s in db.scalars(stmt.order_by(RepairService.created_at.desc()).offset(max(0,offset)).limit(50))]

@router.get('/requests/{service_id}')
def get_service(service_id:str,user=Depends(current_user),db=Depends(get_db)):return serialize(db,service_for(db,user,service_id),user)

@router.get('/requests/{service_id}/image')
def service_image(service_id:str,user=Depends(current_user),db=Depends(get_db)):
    service=service_for(db,user,service_id)
    return Response(store.get(db.get(Project,service.project_id).image_key),media_type='image/jpeg')

@router.get('/requests/{service_id}/preview.png')
def shared_preview(service_id:str,user=Depends(current_user),db=Depends(get_db)):
    service=service_for(db,user,service_id)
    key=(service.design_snapshot or {}).get('preview_key')
    if not key:raise HTTPException(404,'No repair preview was shared with this request.')
    return Response(store.get(key),media_type='image/png')

@router.get('/requests/{service_id}/pattern.pdf')
def shared_pattern(service_id:str,user=Depends(current_user),db=Depends(get_db)):
    service=service_for(db,user,service_id)
    if not service.design_snapshot or not service.design_snapshot.get('pdf_key'):raise HTTPException(404,'No repair pattern was shared for this piece.')
    return Response(store.get(service.design_snapshot['pdf_key']),media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="kintsugi-shared-repair.pdf"'})

@router.post('/requests/{service_id}/assign')
def assign(service_id:str,body:AssignInput,user=Depends(current_user),db=Depends(get_db)):
    operator(user);service=service_for(db,user,service_id,True)
    if service.status!='awaiting_match':raise HTTPException(409,'Only unmatched requests can be assigned.')
    maker=db.get(Maker,body.maker_id);project=db.get(Project,service.project_id)
    if not maker or maker.status!='approved' or not maker.accepting_work or project.category not in maker.categories or maker.user_id==service.user_id:raise HTTPException(409,'Choose an available, approved maker for this category.')
    service.maker_id=maker.id;service.status='awaiting_quote';event(db,service,user,'Matched with '+maker.name+'. The maker will review the work.');db.commit();return serialize(db,service,user)

@router.post('/requests/{service_id}/quote')
def propose_quote(service_id:str,body:QuoteInput,user=Depends(current_user),db=Depends(get_db)):
    service=service_for(db,user,service_id,True);maker=maker_access(db,service,user)
    if service.status not in ('awaiting_quote','repair_priced'):raise HTTPException(409,'This quote can no longer be changed.')
    q=quote_for(db,service)
    if q:
        for k,v in body.model_dump().items():setattr(q,k,v)
        q.version+=1
    else:q=ServiceQuote(service_id=service.id,maker_id=maker.id,**body.model_dump());db.add(q)
    service.status='repair_priced';event(db,service,user,'Maker submitted labour and material costs. Shipping is being arranged.');db.commit();return serialize(db,service,user)

@router.post('/requests/{service_id}/shipping-price')
def shipping_price(service_id:str,body:ShippingPrice,user=Depends(current_user),db=Depends(get_db)):
    operator(user);service=service_for(db,user,service_id,True);q=quote_for(db,service)
    if service.status not in ('repair_priced','quoted') or not q or q.version!=body.version:raise HTTPException(409,'Refresh the repair quote before pricing shipping.')
    from .config import SERVICE_FEE_BPS
    q.outbound_minor=body.outbound_minor;q.return_minor=body.return_minor
    q.fee_minor=((q.labour_minor+q.materials_minor)*SERVICE_FEE_BPS+5000)//10000
    q.total_minor=q.labour_minor+q.materials_minor+q.outbound_minor+q.return_minor+q.fee_minor
    q.version+=1;q.expires_at=time.time()+7*86400;service.status='quoted';event(db,service,user,'Itemised quote is ready. Both shipping legs and the platform fee are included.');db.commit();return serialize(db,service,user)

@router.post('/requests/{service_id}/accept')
def accept(service_id:str,body:Acceptance,user=Depends(current_user),db=Depends(get_db)):
    service=service_for(db,user,service_id,True);owner(service,user);q=quote_for(db,service)
    if q and q.accepted_at:return serialize(db,service,user)
    if service.status!='quoted' or not q or q.version!=body.version or not q.expires_at or q.expires_at<time.time():raise HTTPException(409,'The quote changed or expired. Ask the operator to refresh it.')
    q.accepted_at=time.time();service.return_address=body.address.model_dump();service.status='accepted';service.payment_status='awaiting_payment'
    db.add_all([Shipment(service_id=service.id,leg='outbound'),Shipment(service_id=service.id,leg='return'),MakerEarning(service_id=service.id,maker_id=service.maker_id,amount_minor=q.labour_minor+q.materials_minor)])
    event(db,service,user,'Quote accepted. Payment and pickup are pending; no payment was taken in the app.');db.commit();return serialize(db,service,user)

@router.post('/requests/{service_id}/cancel')
def cancel(service_id:str,user=Depends(current_user),db=Depends(get_db)):
    service=service_for(db,user,service_id,True);owner(service,user)
    if service.status not in ('awaiting_match','awaiting_quote','repair_priced','quoted'):raise HTTPException(409,'Contact the operator about cancelling an accepted repair.')
    service.status='cancelled';event(db,service,user,'Customer cancelled before accepting the quote.');db.commit();return serialize(db,service,user)

@router.post('/requests/{service_id}/payment')
def payment(service_id:str,body:Reference,user=Depends(current_user),db=Depends(get_db)):
    operator(user);service=service_for(db,user,service_id,True)
    if service.status!='accepted':raise HTTPException(409,'An accepted quote is required.')
    if service.payment_status=='confirmed':return serialize(db,service,user)
    service.payment_status='confirmed';service.payment_reference=body.reference;event(db,service,user,'Operator confirmed an externally received payment. Pickup can be scheduled.');db.commit();return serialize(db,service,user)

@router.post('/requests/{service_id}/progress')
def progress(service_id:str,body:MakerProgress,user=Depends(current_user),db=Depends(get_db)):
    service=service_for(db,user,service_id,True);maker_access(db,service,user)
    if body.status=='declined':
        if service.status!='awaiting_quote':raise HTTPException(409,'Contact the operator about declining a priced or accepted repair.')
        service.maker_id=None;service.status='awaiting_match';event(db,service,user,'The maker declined this job. We will look for another available maker.')
    else:
        expected={'repairing':'with_maker','ready_for_return':'repairing'}[body.status]
        if service.status!=expected:raise HTTPException(409,'This repair is not ready for that step.')
        service.status=body.status;event(db,service,user,'Maker started the repair.' if body.status=='repairing' else 'Maker finished the repair. Return shipping can be arranged.')
    db.commit();return serialize(db,service,user)

@router.post('/requests/{service_id}/shipments/{leg}')
def shipping(service_id:str,leg:Literal['outbound','return'],body:ShippingUpdate,user=Depends(current_user),db=Depends(get_db)):
    operator(user);service=service_for(db,user,service_id,True)
    shipment=db.scalar(select(Shipment).where(Shipment.service_id==service.id,Shipment.leg==leg))
    if not shipment or service.payment_status!='confirmed':raise HTTPException(409,'Confirm payment before arranging shipping.')
    sequence={'pending':'scheduled','scheduled':'in_transit','in_transit':'delivered'}
    if sequence.get(shipment.status)!=body.status:raise HTTPException(409,'Follow shipment steps in order: scheduled, in transit, delivered.')
    expected={'outbound':{'scheduled':'accepted','in_transit':'pickup_scheduled','delivered':'on_way_to_maker'},'return':{'scheduled':'ready_for_return','in_transit':'return_scheduled','delivered':'on_way_home'}}
    if service.status!=expected[leg][body.status]:raise HTTPException(409,'The repair is not ready for this shipping step.')
    if body.status=='scheduled' and not body.pickup_at:raise HTTPException(422,'Record the pickup date/time from the carrier booking.')
    shipment.status=body.status;shipment.courier=body.courier;shipment.tracking=body.tracking;shipment.tracking_url=body.tracking_url
    if body.pickup_at:shipment.pickup_at=body.pickup_at
    status_map={'outbound':{'scheduled':'pickup_scheduled','in_transit':'on_way_to_maker','delivered':'with_maker'},'return':{'scheduled':'return_scheduled','in_transit':'on_way_home','delivered':'delivered'}}
    service.status=status_map[leg][body.status]
    event(db,service,user,('Pickup to maker' if leg=='outbound' else 'Return to customer')+': '+body.status.replace('_',' ')+'.')
    if service.status=='delivered':
        earning=db.scalar(select(MakerEarning).where(MakerEarning.service_id==service.id));earning.status='payable'
    db.commit();return serialize(db,service,user)

@router.get('/earnings')
def earnings(user=Depends(current_user),db=Depends(get_db)):
    maker=profile(db,user)
    if not maker:return []
    return [{k:getattr(e,k) for k in ['id','service_id','amount_minor','status','payout_reference','paid_at']} for e in db.scalars(select(MakerEarning).where(MakerEarning.maker_id==maker.id))]

@router.post('/requests/{service_id}/payout')
def payout(service_id:str,body:Reference,user=Depends(current_user),db=Depends(get_db)):
    operator(user);service=service_for(db,user,service_id,True);earning=db.scalar(select(MakerEarning).where(MakerEarning.service_id==service.id))
    if not earning or service.status!='delivered':raise HTTPException(409,'Delivery must be recorded before payout reconciliation.')
    if earning.status=='paid':return {'status':'paid','amount_minor':earning.amount_minor}
    earning.status='paid';earning.payout_reference=body.reference;earning.paid_at=time.time();event(db,service,user,'Operator recorded the maker payout with an external transfer reference.');db.commit();return {'status':'paid','amount_minor':earning.amount_minor}

# routers/bookmarks.py
from fastapi import APIRouter, HTTPException
from pyaida.core.data.entities.ResourceModel import ResourceModel
from pyaida.core.parsing.web import get_open_graph_data

router = APIRouter()

@router.get("/")
async def get():
    return [ResourceModel(id=str(i), title=f'test {i}', description='test it test it', uri="www.google.com").model_dump() for i in range(50)]

@router.post("/")
async def create(resource: ResourceModel):
    d =  resource.model_dump()
    d['description'] = "I will be adding a long description here"
    #d['uri'] = "https://kajabi-storefronts-production.global.ssl.fastly.net/kajabi-storefronts-production/blogs/18725/images/mM87l2ZsQRSawMLLRlFF_FallLandscape7-.jpg"
    
    try:
        data = get_open_graph_data(d['uri'])
        d['image'] = data['image']
        d['description'] = data['description']
    except Exception as ex:
        return {'error': repr(ex)}
    return d

@router.get("/{id}")
async def get_by_id(id: int):
    return {"message": f"Get ref {id}"}

@router.put("/{id}")
async def update(id: int, resource: ResourceModel):
    return {"message": f"Update ref {id}", "data": resource}

@router.delete("/{id}")
async def delete(id: int):
    return {"message": f"Delete reference {id}"}

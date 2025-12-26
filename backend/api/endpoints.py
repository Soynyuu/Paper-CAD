from fastapi import APIRouter

from api.routers.citygml import router as citygml_router
from api.routers.plateau import router as plateau_router
from api.routers.svg import router as svg_router
from api.routers.step import router as step_router
from api.routers.system import router as system_router

router = APIRouter()
router.include_router(step_router)
router.include_router(svg_router)
router.include_router(citygml_router)
router.include_router(plateau_router)
router.include_router(system_router)

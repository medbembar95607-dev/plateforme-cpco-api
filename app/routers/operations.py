from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..schemas import OperationOut

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("", response_model=list[OperationOut])
def list_operations(db: Session = Depends(get_db)):
    return db.query(models.Operation).all()

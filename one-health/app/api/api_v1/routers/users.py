import logging
from typing import Any, List

from app import crud, models, schemas
from app.api import deps
from app.api.deps import get_db
from app.constants.role import Role
from app.core.config import settings
from app.core import security
from fastapi import APIRouter, Body, Depends, HTTPException, Security, Query
from fastapi.encoders import jsonable_encoder
from pydantic.networks import EmailStr
from pydantic.types import UUID4
from sqlalchemy.orm import Session

from app.schemas import UserCreate
from app.schemas.user import UserLogin, UserLogOut, PaginatedItemList
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/users", tags=["users"])
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@router.get("/hello")
def get_hello():
    return "hello"


@router.get("", response_model=List[schemas.User])
def read_users(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Security(
        deps.get_current_active_user,
        scopes=[Role.ADMIN["name"], Role.SUPER_ADMIN["name"]],
    ),
) -> Any:
    """
    Retrieve all users.
    """
    users = crud.user.get_multi(db, skip=skip, limit=limit,)
    return users

@router.post("/user-login")
def create_user(user_dtl: UserLogin, db: Session = Depends(get_db)
) -> Any:
    """
    log in user.
    """
    logger.info("email id or phone no ------> %s", user_dtl.email_or_phone_no)
    try:
        user = crud.user.get_by_email_or_phone(db, email=user_dtl.email_or_phone_no,
                                               phone_number=user_dtl.email_or_phone_no)

        if user:
            if security.verify_password(user_dtl.password, user.password) is False:
                raise HTTPException(
                    status_code=409,
                    detail="Please check user credentials",
                )
            db_user = crud.user_role.get_by_user_id(db, user_id=user.user_id)
            if db_user.role_id != user_dtl.user_role:
                raise HTTPException(
                    status_code=409,
                    detail="User role does not match",
                )
        else:
            raise HTTPException(
                status_code=409,
                detail="User does not exist, please sign up.",
            )

        return JSONResponse(content={"message": "Login successful", "status": 200, "user_id": user.user_id}, status_code=200)
    except HTTPException as e:
        return JSONResponse(content={"detail": str(e.detail), "status": e.status_code}, status_code=e.status_code)


@router.post("/create-user")
def create_user(user_in: UserCreate, db: Session = Depends(get_db)
) -> Any:
    """
    Create new user.
    """
    try:
        user = crud.user.get_by_email(db, email=user_in.email_id)
        if user:
            raise HTTPException(
                status_code=409,
                detail="The user with this user email already exists in the system.",
            )
        user = crud.user.create(db, obj_in=user_in)
        return JSONResponse(content={"message": "User created successfully", "status": 200}, status_code=200)
    except HTTPException as e:
        return JSONResponse(content={"detail": str(e.detail), "status": e.status_code}, status_code=e.status_code)


@router.post("/user-logout")
def logout_user(user_dtl: UserLogOut, db: Session = Depends(get_db)
) -> Any:
    response = JSONResponse(content={"message": "Logout successful"})
    response.delete_cookie("session_token")
    return response


@router.put("/me", response_model=schemas.User)
def update_user_me(
    *,
    db: Session = Depends(deps.get_db),
    full_name: str = Body(None),
    phone_number: str = Body(None),
    email: EmailStr = Body(None),
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Update own user.
    """
    current_user_data = jsonable_encoder(current_user)
    user_in = schemas.UserUpdate(**current_user_data)
    if phone_number is not None:
        user_in.phone_number = phone_number
    if full_name is not None:
        user_in.full_name = full_name
    if email is not None:
        user_in.email = email
    user = crud.user.update(db, db_obj=current_user, obj_in=user_in)
    return user


@router.get("/me", response_model=schemas.User)
def read_user_me(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get current user.
    """
    if not current_user.user_role:
        role = None
    else:
        role = current_user.user_role.role.name
    user_data = schemas.User(
        id=current_user.id,
        email=current_user.email,
        is_active=current_user.is_active,
        full_name=current_user.full_name,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        role=role,
    )
    return user_data


@router.post("/open", response_model=schemas.User)
def create_user_open(
    *,
    db: Session = Depends(deps.get_db),
    password: str = Body(...),
    email: EmailStr = Body(...),
    full_name: str = Body(...),
    phone_number: str = Body(None),
) -> Any:
    """
    Create new user without the need to be logged in.
    """
    if not settings.USERS_OPEN_REGISTRATION:
        raise HTTPException(
            status_code=403,
            detail="Open user registration is forbidden on this server",
        )
    user = crud.user.get_by_email(db, email=email)
    if user:
        raise HTTPException(
            status_code=409,
            detail="The user with this username already exists in the system",
        )
    user_in = schemas.UserCreate(
        password=password,
        email=email,
        full_name=full_name,
        phone_number=phone_number,
    )
    user = crud.user.create(db, obj_in=user_in)
    return user


@router.get("/{user_id}", response_model=schemas.User)
def read_user_by_id(
    user_id: str,
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Get a specific user by id.
    """
    try:
        user = crud.user.get(db, id=user_id)
        if not user:
            raise HTTPException(
                status_code=404,
                detail="The user does not exist in the system",
            )
        return user
    except HTTPException as e:
        return JSONResponse(content={"detail": str(e.detail), "status": e.status_code}, status_code=e.status_code)


@router.put("/update-user")
def update_user(
    *,
    db: Session = Depends(deps.get_db),
    user_in: schemas.UserUpdate
) -> Any:
    """
    Update a user.
    """
    try:
        logger.info("user id ------> %s", user_in.user_id)
        user = crud.user.get_by_user_id(db, user_id=user_in.user_id)
        if not user:
            raise HTTPException(
                status_code=404,
                detail="The user does not exist in the system",
            )
        user = crud.user.update(db, db_obj=user, obj_in=user_in)
        return JSONResponse(content={"message": "Updated user details successfully", "status": 200}, status_code=200)
    except HTTPException as e:
        return JSONResponse(content={"detail": str(e.detail), "status": e.status_code}, status_code=e.status_code)


@router.get("/items/", response_model=PaginatedItemList)
def get_items(
        status: int,
        db: Session = Depends(get_db),
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=10, ge=1),
):
    # Calculate skip value based on page number and page size
    skip = (page - 1) * limit

    # Retrieve paginated items from the database
    items = crud.user.get_items(db, status=status, skip=skip, limit=limit)

    # Return paginated items along with metadata
    return PaginatedItemList(
        total=len(items),
        items=items,
        skip=skip,
        limit=limit,
    )



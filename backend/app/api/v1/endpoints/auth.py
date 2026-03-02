import logging

from fastapi import APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends

from app.core.security import authenticate_user, create_access_token, get_current_user
from app.models.schemas import LoginRequest, TokenResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login with panel admin credentials and receive a JWT bearer token."""
    logger.info("Login attempt for user '%s'", form_data.username)
    if not authenticate_user(form_data.username, form_data.password):
        logger.warning("Failed login attempt for user '%s'", form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(data={"sub": form_data.username})
    logger.info("User '%s' authenticated successfully", form_data.username)
    return TokenResponse(access_token=token)


@router.post("/login/json", response_model=TokenResponse)
async def login_json(req: LoginRequest):
    """Login via JSON body (alternative to form-based login)."""
    logger.info("JSON login attempt for user '%s'", req.username)
    if not authenticate_user(req.username, req.password):
        logger.warning("Failed JSON login attempt for user '%s'", req.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    token = create_access_token(data={"sub": req.username})
    logger.info("User '%s' authenticated successfully (JSON)", req.username)
    return TokenResponse(access_token=token)


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    """Return info about the currently authenticated panel user."""
    return {"username": current_user["username"], "role": "admin"}

